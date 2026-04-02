import { apiClient } from './api'
import type { FichierDossier, FichierCreate } from '@/types'

export const fichiersService = {
  list(dossierId: string): Promise<FichierDossier[]> {
    return apiClient.get(`/dossiers/${dossierId}/fichiers`).then((r) => r.data)
  },

  create(dossierId: string, payload: FichierCreate): Promise<FichierDossier> {
    return apiClient.post(`/dossiers/${dossierId}/fichiers`, payload).then((r) => r.data)
  },

  update(fichierId: string, payload: Partial<Pick<FichierDossier, 'nom_fichier' | 'version' | 'statut' | 'commentaire'>>): Promise<FichierDossier> {
    return apiClient.patch(`/fichiers/${fichierId}`, payload).then((r) => r.data)
  },
}
