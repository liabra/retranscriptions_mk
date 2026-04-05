import { apiClient, getApiErrorMessage } from './api'
import type { FichierDossier } from '@/types'

export const uploadService = {
  /**
   * Upload un fichier sur un dossier.
   * Gère automatiquement le Content-Type multipart via FormData.
   */
  async uploadFichier(
    dossierId: string,
    file: File,
    commentaire = '',
  ): Promise<FichierDossier> {
    const form = new FormData()
    form.append('file', file)
    form.append('commentaire', commentaire)
    const response = await apiClient.post(`/dossiers/${dossierId}/upload`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
  },

  /**
   * Liste les fichiers d'un dossier (endpoint sécurisé par rôle).
   */
  async listFichiers(dossierId: string): Promise<FichierDossier[]> {
    const response = await apiClient.get(`/dossiers/${dossierId}/fichiers`)
    return response.data
  },

  /**
   * Télécharge un fichier — retourne un Blob (gère OneDrive redirect et stockage local).
   * Si le serveur redirige vers OneDrive, ouvre dans un nouvel onglet.
   */
  async downloadFichier(fichierId: string, nomFichier: string): Promise<void> {
    try {
      const response = await apiClient.get(`/fichiers/${fichierId}/download`, {
        responseType: 'blob',
        maxRedirects: 5,
      })
      const blob = new Blob([response.data], {
        type: response.headers['content-type'] || 'application/octet-stream',
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = nomFichier
      a.click()
      URL.revokeObjectURL(url)
    } catch (err) {
      throw new Error(getApiErrorMessage(err))
    }
  },
}
