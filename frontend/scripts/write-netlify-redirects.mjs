import { mkdirSync, writeFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'

const rawApiUrl = (
  process.env.RENDER_API_URL
  || process.env.VITE_API_BASE_URL
)?.trim()

if (!rawApiUrl) {
  throw new Error(
    'Netlify build requires RENDER_API_URL or VITE_API_BASE_URL',
  )
}

const apiUrl = new URL(rawApiUrl)
if (apiUrl.protocol !== 'https:' || apiUrl.username || apiUrl.password) {
  throw new Error('The Render API URL must be public HTTPS without credentials')
}

const apiOrigin = apiUrl.origin
const distDirectory = fileURLToPath(new URL('../dist/', import.meta.url))
mkdirSync(distDirectory, { recursive: true })
writeFileSync(
  `${distDirectory}/_redirects`,
  `/api/*  ${apiOrigin}/:splat  200\n/*  /index.html  200\n`,
  'utf8',
)
