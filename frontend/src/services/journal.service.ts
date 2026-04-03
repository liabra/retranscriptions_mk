import { apiClient } from './api'
import type { JournalEntry } from '@/types'

export const journalService = {
  getDossier(dossierId: string, limit = 30): Promise<JournalEntry[]> {
    return apiClient
      .get(`/dossiers/${dossierId}/journal`, { params: { limit } })
      .then((r) => r.data)
  },

  getGlobal(limit = 100, offset = 0, type_action?: string): Promise<JournalEntry[]> {
    return apiClient
      .get('/journal', { params: { limit, offset, type_action } })
      .then((r) => r.data)
  },
}
