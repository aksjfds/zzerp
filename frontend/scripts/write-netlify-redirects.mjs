import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const rawApiUrl = process.env.RENDER_API_URL?.trim()

if (!rawApiUrl) {
  throw new Error('Netlify build requires the RENDER_API_URL environment variable')
}

const apiUrl = new URL(rawApiUrl)
if (apiUrl.protocol !== 'https:' || apiUrl.username || apiUrl.password) {
  throw new Error('RENDER_API_URL must be a public HTTPS URL without credentials')
}

const apiOrigin = apiUrl.origin
const distDirectory = fileURLToPath(new URL('../dist/', import.meta.url))
mkdirSync(distDirectory, { recursive: true })
writeFileSync(
  `${distDirectory}/_redirects`,
  `/api/*  ${apiOrigin}/:splat  200\n/*  /index.html  200\n`,
  'utf8',
)
