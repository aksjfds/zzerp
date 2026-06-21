import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

if (import.meta.env.PROD && !import.meta.env.VITE_API_BASE_URL) {
  throw new Error('Missing VITE_API_BASE_URL for production build')
}

export const service = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10000,
})
