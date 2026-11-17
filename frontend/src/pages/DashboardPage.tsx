import { Link, useNavigate } from 'react-router-dom'
import {
  AlarmClock, AudioLines, BadgeCheck, CircleDollarSign, ClipboardCheck, FileCheck2, FileClock, FileInput,
  FilePen, HandCoins, Inbox, ListChecks, PenLine, PlayCircle, Receipt, Wallet, type LucideIcon,
} from 'lucide-react'
import { api } from '@/lib/api'
import { useAuth } from '@/lib/session'
import { fMoney, fDateTime } from '@/lib/format'
import { ErrorBox, PageLoader } from '@/components/ui'
import { useLoad } from '@/lib/hooks'
import { DossierTable } from '@/pages/DossiersPage'

interface Tile { key: string; label: string; icon: LucideIcon; tone: string; to: string; alertIfAny?: boolean; sub?: string }

const PRODUCTION: Tile[] = [
  { key: 'nouveaux_audios', label: 'Nouveaux audios', icon: AudioLines, tone: 'primary', to: '/audios' },
  { key: 'a_qualifier', label: 'Dossiers à qualifier', icon: ListChecks, tone: 'gray', to: '/dossiers?production=a_qualifier' },
  { key: 'a_attribuer', label: 'Missions à attribuer', icon: Inbox, tone: 'amber', to: '/dossiers?production=a_attribuer' },
  { key: 'en_cours', label: 'Missions en cours', icon: PlayCircle, tone: 'blue', to: '/dossiers?production=attribue,en_cours' },
  { key: 'en_retard', label: 'Dossiers en retard', icon: AlarmClock, tone: 'red', to: '/dossiers?retard=1', alertIfAny: true },
  { key: 'pv_recus', label: 'PV reçus', icon: FileInput, tone: 'violet', to: '/dossiers?production=livre' },
  { key: 'a_relire', label: 'PV à relire', icon: FilePen, tone: 'violet', to: '/dossiers?production=a_relire' },
  { key: 'corrections_demandees', label: 'Corrections demandées', icon: PenLine, tone: 'amber', to: '/dossiers?production=correction_demandee' },
  { key: 'a_controler', label: 'PV à contrôler', icon: ClipboardCheck, tone: 'violet', to: '/dossiers?production=a_controler' },
  { key: 'valides', label: 'PV validés', icon: BadgeCheck, tone: 'green', to: '/dossiers?production=valide' },
]

const FINANCE: Tile[] = [
  { key: 'factures_a_etablir', label: 'Factures à établir', icon: FileClock, tone: 'amber', to: '/finance?vue=a_etablir' },
  { key: 'encaissements_attendus', label: 'Encaissements attendus', icon: Receipt, tone: 'blue', to: '/finance?vue=attente', sub: 'montant_attendu' },
  { key: 'encaissements_recus_mois', label: 'Encaissements reçus (mois)', icon: CircleDollarSign, tone: 'green', to: '/finance?vue=reglees', sub: 'montant_encaisse_mois' },
  { key: 'paiements_a_effectuer', label: 'Paiements prestataires à effectuer', icon: HandCoins, tone: 'amber', to: '/finance?vue=paiements', sub: 'montant_a_payer' },
  { key: 'paiements_effectues', label: 'Paiements effectués', icon: Wallet, tone: 'green', to: '/finance?vue=paiements_effectues' },
]

function Tiles({ tiles, values }: { tiles: Tile[]; values: Record<string, number | null> }) {
  const navigate = useNavigate()
  return (
    <div className="kpis">
      {tiles.filter((t) => values[t.key] !== null && values[t.key] !== undefined).map((t) => {
        const v = Number(values[t.key] ?? 0)
        return (
          <button key={t.key} className={`kpi${t.alertIfAny && v > 0 ? ' alert' : ''}${v === 0 ? ' zero' : ''}`}
            onClick={() => navigate(t.to)} aria-label={`${t.label} : ${v}`}>
            <span className={`kpi-icon tone-${t.tone}`}><t.icon size={18} /></span>
            <span className="kpi-value">{v}</span>
            <span className="kpi-label">{t.label}</span>
            {t.sub && values[t.sub] != null && <span className="kpi-sub">{fMoney(values[t.sub] as number)}</span>}
          </button>
        )
      })}
    </div>
  )
}

export function DashboardPage() {
  const { user, can } = useAuth()
  const dash = useLoad(() => api.dashboard())
  const prioritaires = useLoad(() => can('dossiers.voir')
    ? api.dossiers({ limit: 8, production: 'a_attribuer,attribue,en_cours,livre,a_relire,correction_demandee,a_controler' })
    : Promise.resolve({ total: 0, items: [] }))

  const heure = new Date().getHours()
  const salut = heure < 18 ? 'Bonjour' : 'Bonsoir'

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>{salut} {user?.nom.split(' ')[0]}</h1>
          <p>Voici l'état de l'activité{dash.data ? ` · mis à jour ${fDateTime(dash.data.genere_le)}` : ''}.</p>
        </div>
      </div>
      <ErrorBox error={dash.error} />
      {dash.loading && !dash.data ? <PageLoader /> : dash.data && (
        <>
          {Object.keys(dash.data.production).length > 0 && (
            <section className="stack" data-tour="kpi-production">
              <h2 className="section-title">Production</h2>
              <Tiles tiles={PRODUCTION} values={dash.data.production} />
            </section>
          )}
          {dash.data.finance && (
            <section className="stack" data-tour="kpi-finance">
              <h2 className="section-title">Facturation & règlements</h2>
              <Tiles tiles={FINANCE} values={dash.data.finance} />
            </section>
          )}
        </>
      )}
      {can('dossiers.voir') && (
        <section className="card">
          <div className="card-header">
            <div>
              <h2 className="card-title">Dossiers en production</h2>
              <p className="small muted">Retards et urgences en premier</p>
            </div>
            <Link className="btn btn-secondary btn-sm" to="/dossiers"><FileCheck2 size={16} />Tous les dossiers</Link>
          </div>
          {prioritaires.loading && !prioritaires.data ? <PageLoader /> :
            <DossierTable items={prioritaires.data?.items ?? []} compact />}
        </section>
      )}
    </div>
  )
}
