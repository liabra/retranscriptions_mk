import axios, { type AxiosError } from 'axios'

// Jeton conservé pour la durée de l'onglet uniquement (pas de persistance longue durée)
const TOKEN_KEY = 'a2c_token'

export const tokenStore = {
  get: (): string | null => {
    try { return sessionStorage.getItem(TOKEN_KEY) } catch { return null }
  },
  set: (t: string) => {
    try { sessionStorage.setItem(TOKEN_KEY, t) } catch { /* stockage indisponible */ }
  },
  clear: () => {
    try { sessionStorage.removeItem(TOKEN_KEY); localStorage.removeItem('access_token'); localStorage.removeItem('user') } catch { /* */ }
  },
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '/api/v1',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const token = tokenStore.get()
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

apiClient.interceptors.response.use(
  (res) => res,
  (error: AxiosError) => {
    if (error.response?.status === 401 && !String(error.config?.url).includes('/auth/login')) {
      tokenStore.clear()
      if (window.location.pathname !== '/login') window.location.assign('/login')
    }
    return Promise.reject(error)
  },
)

type ErrorBody = { detail?: string | { msg: string }[] }

export function getApiErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const data = error.response?.data as ErrorBody | Blob | undefined
    if (!error.response) return 'Serveur injoignable. Vérifiez votre connexion.'
    if (data && !(data instanceof Blob)) {
      if (typeof data.detail === 'string') return data.detail
      if (Array.isArray(data.detail)) return data.detail.map((d) => d.msg).join(', ')
    }
    if (error.response.status === 403) return "Vous n'avez pas les droits pour cette action."
    if (error.response.status === 413) return 'Fichier trop volumineux.'
    return `Erreur ${error.response.status}`
  }
  if (error instanceof Error) return error.message
  return 'Erreur inconnue'
}

/** Téléchargement authentifié : le fichier transite par l'API, aucun lien de stockage n'est exposé. */
export async function downloadFile(url: string, fallbackName: string): Promise<void> {
  const res = await apiClient.get(url, { responseType: 'blob' })
  const dispo = String(res.headers['content-disposition'] ?? '')
  const match = /filename\*=UTF-8''([^;]+)/.exec(dispo) ?? /filename="([^"]+)"/.exec(dispo)
  const name = match ? decodeURIComponent(match[1]) : fallbackName
  const href = URL.createObjectURL(res.data as Blob)
  const a = document.createElement('a')
  a.href = href
  a.download = name
  document.body.appendChild(a)
  a.click()
  a.remove()
  setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/** Ouvre un document HTML authentifié (ex. facture) dans un nouvel onglet, sans exposer le jeton dans l'URL. */
export async function openHtml(url: string): Promise<void> {
  const res = await apiClient.get(url, { responseType: 'blob' })
  const href = URL.createObjectURL(new Blob([res.data as Blob], { type: 'text/html' }))
  window.open(href, '_blank', 'noopener')
  setTimeout(() => URL.revokeObjectURL(href), 60000)
}
