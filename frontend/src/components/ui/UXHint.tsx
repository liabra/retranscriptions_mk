import { useHints } from '@/contexts/HintsContext'

interface UXHintProps {
  /** Identifiant unique du hint — persiste le "Ne plus afficher" dans localStorage */
  hintId: string
  children: React.ReactNode
}

/**
 * Conseil contextuel UX.
 *
 * - Masqué si les conseils sont désactivés globalement (toggle sidebar)
 * - Masqué si dismissé dans la session (✕) ou définitivement ("Ne plus afficher")
 * - L'état dismissal est géré dans HintsContext, pas en state local — le toggle
 *   global "Afficher les conseils" réinitialise tous les hints immédiatement.
 *
 * Pour ajouter un nouveau hint :
 *   <UXHint hintId="section_contexte">Texte du conseil</UXHint>
 * Aucune configuration centrale nécessaire.
 */
export function UXHint({ hintId, children }: UXHintProps) {
  const { enabled, dismissedHints, dismiss } = useHints()

  if (!enabled || dismissedHints.has(hintId)) return null

  return (
    <div
      style={{
        background: '#fffbeb',
        border: '1px solid #fde68a',
        borderRadius: 'var(--radius)',
        padding: '10px 14px',
        marginBottom: 12,
        display: 'flex',
        alignItems: 'flex-start',
        gap: 10,
        fontSize: 13,
        lineHeight: '1.5',
      }}
    >
      <span style={{ fontSize: 15, flexShrink: 0, marginTop: 1 }}>💡</span>
      <div style={{ flex: 1, color: 'var(--color-text)' }}>{children}</div>
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: 4, flexShrink: 0 }}>
        <button
          onClick={() => dismiss(hintId, false)}
          title="Fermer"
          aria-label="Fermer ce conseil"
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 14,
            color: 'var(--color-text-muted)',
            padding: '0 2px',
            lineHeight: 1,
          }}
        >
          ✕
        </button>
        <button
          onClick={() => dismiss(hintId, true)}
          style={{
            background: 'none',
            border: 'none',
            cursor: 'pointer',
            fontSize: 10,
            color: 'var(--color-text-muted)',
            whiteSpace: 'nowrap',
            padding: 0,
            textDecoration: 'underline',
          }}
        >
          Ne plus afficher
        </button>
      </div>
    </div>
  )
}
