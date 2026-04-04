import { useState } from 'react'
import { TRANCHES_CLIENT, getTranche, getDelaiLivraison } from '@/utils/forfaits'

interface TarifForfaitProps {
  /** Nombre de pages final ou estimé — met en surbrillance la tranche applicable */
  pages?: number | null
  /** Durée audio en minutes — affiche le délai de livraison recommandé */
  dureeAudioMinutes?: number | null
}

/**
 * Affiche la grille tarifaire forfaitaire A2C avec mise en évidence de la tranche
 * applicable selon le nombre de pages.
 */
export function TarifForfait({ pages, dureeAudioMinutes }: TarifForfaitProps) {
  const [open, setOpen] = useState(false)
  const tranche = pages ? getTranche(pages) : null
  const delai = dureeAudioMinutes ? getDelaiLivraison(dureeAudioMinutes) : null

  return (
    <div style={{ marginBottom: 12 }}>
      {/* Forfait applicable — mise en évidence */}
      {tranche && (
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: 12,
            background: '#f0fdf4',
            border: '1px solid #86efac',
            borderRadius: 'var(--radius)',
            padding: '10px 14px',
            marginBottom: 8,
          }}
        >
          <span style={{ fontSize: 20 }}>✓</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 11, color: '#15803d', fontWeight: 600, textTransform: 'uppercase', marginBottom: 2 }}>
              Forfait applicable — {tranche.label}
            </div>
            <div style={{ fontSize: 22, fontWeight: 700, color: '#15803d' }}>
              {tranche.montant} €
            </div>
          </div>
          {delai && (
            <div style={{ textAlign: 'right', fontSize: 12, color: '#15803d' }}>
              <div style={{ fontWeight: 600 }}>Délai recommandé</div>
              <div style={{ fontSize: 15, fontWeight: 700 }}>{delai}</div>
            </div>
          )}
        </div>
      )}

      {/* Toggle grille complète */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          fontSize: 12,
          color: 'var(--color-text-muted)',
          padding: 0,
          textDecoration: 'underline',
        }}
      >
        {open ? '▲ Masquer la grille tarifaire' : '▼ Voir la grille tarifaire complète'}
      </button>

      {open && (
        <table
          style={{
            width: '100%',
            fontSize: 12,
            borderCollapse: 'collapse',
            marginTop: 8,
          }}
        >
          <thead>
            <tr style={{ borderBottom: '1px solid var(--color-border)' }}>
              <th style={{ textAlign: 'left', padding: '6px 8px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                Tranche
              </th>
              <th style={{ textAlign: 'right', padding: '6px 8px', fontWeight: 600, fontSize: 11, color: 'var(--color-text-muted)', textTransform: 'uppercase' }}>
                Forfait client
              </th>
            </tr>
          </thead>
          <tbody>
            {TRANCHES_CLIENT.map((t) => {
              const isActive = tranche?.label === t.label
              return (
                <tr
                  key={t.label}
                  style={{
                    borderBottom: '1px solid var(--color-border-light)',
                    background: isActive ? '#f0fdf4' : undefined,
                    fontWeight: isActive ? 600 : undefined,
                  }}
                >
                  <td style={{ padding: '6px 8px' }}>
                    {isActive && <span style={{ marginRight: 6, color: '#15803d' }}>◀</span>}
                    {t.label}
                  </td>
                  <td style={{ padding: '6px 8px', textAlign: 'right', color: isActive ? '#15803d' : undefined }}>
                    {t.montant} €
                  </td>
                </tr>
              )
            })}
          </tbody>
          <tfoot>
            <tr>
              <td colSpan={2} style={{ padding: '8px 8px 2px', fontSize: 11, color: 'var(--color-text-muted)' }}>
                Format : interligne simple, Times New Roman 12. Au-delà de 100 pages, tarif sur devis.
              </td>
            </tr>
          </tfoot>
        </table>
      )}
    </div>
  )
}
