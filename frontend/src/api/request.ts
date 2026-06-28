import axios from 'axios'

const apiBaseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'

if (import.meta.env.PROD && !import.meta.env.VITE_API_BASE_URL) {
  throw new Error('Missing VITE_API_BASE_URL for production build')
}

export const service = axios.create({
  baseURL: apiBaseUrl,
  timeout: 10000,
  withCredentials: true,
})

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
