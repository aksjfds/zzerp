import { readdirSync, readFileSync } from 'node:fs'
import { dirname, isAbsolute, relative, resolve, sep } from 'node:path'
import { fileURLToPath } from 'node:url'
import ts from 'typescript'

const sourceRoot = fileURLToPath(new URL('../src/', import.meta.url))

function sourceFiles(directory) {
  return readdirSync(directory, { withFileTypes: true }).flatMap(entry => {
    const path = resolve(directory, entry.name)
    if (entry.isDirectory()) return sourceFiles(path)
    return /\.(?:ts|vue)$/.test(entry.name) ? [path] : []
  })
}

function importsIn(script, path) {
  const source = ts.createSourceFile(path, script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
  const imports = []
  function visit(node) {
    if ((ts.isImportDeclaration(node) || ts.isExportDeclaration(node))
      && node.moduleSpecifier && ts.isStringLiteralLike(node.moduleSpecifier)) {
      imports.push(node.moduleSpecifier.text)
    }
    if (ts.isCallExpression(node) && node.expression.kind === ts.SyntaxKind.ImportKeyword
      && node.arguments[0] && ts.isStringLiteralLike(node.arguments[0])) {
      imports.push(node.arguments[0].text)
    }
    ts.forEachChild(node, visit)
  }
  visit(source)
  return imports
}

function boundaryError(path, imported) {
  const target = imported.startsWith('@/') ? resolve(sourceRoot, imported.slice(2))
    : imported.startsWith('.') ? resolve(dirname(path), imported) : undefined
  if (!target) return undefined
  const targetRelative = relative(sourceRoot, target)
  const parts = targetRelative.split(sep)
  const source = relative(sourceRoot, path).split(sep)
  if (parts[0] === '..' || isAbsolute(targetRelative)) return 'import outside frontend/src'
  if (source[0] === 'shared' && parts[0] === 'features') return 'shared imports business feature'
  if (source[0] === 'features' && parts[0] === 'features' && source[1] !== parts[1]
    && !(parts.length === 2 || (parts.length === 3 && /^index(?:\.ts)?$/.test(parts[2])))) {
    return `bypasses ${parts[1]}/index.ts`
  }
  return undefined
}

const files = sourceFiles(sourceRoot)
const errors = []
for (const path of files) {
  const content = readFileSync(path, 'utf8')
  const scripts = path.endsWith('.vue')
    ? [...content.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script\s*>/g)].map(match => match[1])
    : [content]
  for (const script of scripts) {
    for (const imported of importsIn(script, path)) {
      const error = boundaryError(path, imported)
      if (error) errors.push(`${relative(sourceRoot, path)}: ${error}: ${imported}`)
    }
  }
}
if (errors.length) {
  errors.forEach(error => console.error(error))
  process.exitCode = 1
} else {
  console.log(`Frontend import boundaries passed (${files.length} files)`)
}
