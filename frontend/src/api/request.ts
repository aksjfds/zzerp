import axios from 'axios'
import type { ApiErrorDetail } from './types'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

if (import.meta.env.PROD && !import.meta.env.VITE_API_BASE_URL) {
  throw new Error('Missing VITE_API_BASE_URL for production build')
}

export const service = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10000,
  withCredentials: true,
})

export function getApiErrorDetail(error: unknown): ApiErrorDetail | null {
  if (!axios.isAxiosError(error)) return null
  const detail = error.response?.data?.detail
  if (!detail || typeof detail !== 'object') return null
  if (typeof detail.code !== 'string' || typeof detail.message !== 'string') return null
  return {
    code: detail.code,
    message: detail.message,
    path: typeof detail.path === 'string' ? detail.path : undefined,
    element_id: typeof detail.element_id === 'string' ? detail.element_id : undefined,
  }
}

let csrfToken: string | undefined

service.interceptors.request.use((config) => {
  const method = config.method?.toUpperCase()

  if (method && ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
    if (csrfToken) {
      config.headers.set('X-CSRF-Token', csrfToken)
    }
  }

  return config
})

service.interceptors.response.use(
  (response) => {
    const responseCsrfToken = response.data?.csrfToken
    if (typeof responseCsrfToken === 'string') {
      csrfToken = responseCsrfToken
    }

    return response
  },
  (error) => {
    const status = error.response?.status

    if (status === 401) {
      window.dispatchEvent(new CustomEvent('zzerp:unauthorized'))
    } else if (status === 403) {
      window.dispatchEvent(
        new CustomEvent('zzerp:forbidden', {
          detail: error.response?.data?.detail,
        }),
      )
    }

    return Promise.reject(error)
  },
)
