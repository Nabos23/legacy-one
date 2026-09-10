import { api } from './client'

export type ServiceHealth = {
  name: string
  status: 'active' | 'warning' | 'down'
}

/**
 * Probe the backend's public health endpoints and report real service status.
 * `GET /` confirms the API is up; `GET /mongo-check` confirms the database.
 * Anything that throws (network error / 5xx) is reported as `down`.
 */
export const healthApi = {
  check: async (): Promise<ServiceHealth[]> => {
    const probe = async (name: string, fn: () => Promise<unknown>): Promise<ServiceHealth> => {
      try {
        await fn()
        return { name, status: 'active' }
      } catch {
        return { name, status: 'down' }
      }
    }
    return Promise.all([
      probe('API Gateway', () => api.get('/')),
      probe('Database', () => api.get('/mongo-check')),
    ])
  },
}
