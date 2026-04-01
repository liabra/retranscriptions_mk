import type { StatutDossier } from '@/types'
import { STATUT_LABELS, STATUT_COLOR } from '@/utils/statuts'

interface Props {
  statut: StatutDossier
}

export function StatusBadge({ statut }: Props) {
  return (
    <span className={`badge ${STATUT_COLOR[statut]}`}>
      {STATUT_LABELS[statut]}
    </span>
  )
}

interface UrgentBadgeProps {
  estUrgent: boolean
  estRetard?: boolean
}

export function UrgentBadge({ estUrgent, estRetard }: UrgentBadgeProps) {
  if (estRetard) return <span className="badge badge-red">⏰ Retard</span>
  if (estUrgent) return <span className="badge badge-red">🚨 Urgent</span>
  return null
}
