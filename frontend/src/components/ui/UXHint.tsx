import { useState } from 'react'
import { useHints } from '@/contexts/HintsContext'

interface UXHintProps {
  /** Identifiant unique du hint — persiste le "Ne plus afficher" dans localStorage */
  hintId: string
  children: React.ReactNode
}

/**
 * Conseil contextuel UX.
 *
 * Rendu conditionnel :
 *   - Masqué si les conseils sont désactivés globalement (toggle dans l'interface)
 *   - Masqué si l'utilisateur a cliqué "Ne plus afficher" (stocké en localStorage)
 *   - Bouton ✕ masque pour la session en cours (state local)
 *   - Bouton "Ne plus afficher" persiste en localStorage
 *
 * Usage :
 *   <UXHint hintId="dossier_qualification">
 *     La qualification permet de saisir les critères tarifaires...
 *   </UXHint>
 *
 * Pour ajouter un nouveau hint : placer ce composant avec un hintId unique
 * à l'endroit voulu dans l'UI. Aucune configuration centrale nécessaire.
 */
export function UXHint({ hintId, children }: UXHintProps) {
  const { enabled } = useHints()
  const storageKey = `ux_hint_dismissed_${hintId}`
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(storageKey) === '1')

  if (!enabled || dismissed) return null

  function close() {
    setDismissed(true)
  }

  function dismissForever() {
    localStorage.setItem(storageKey, '1')
    setDismissed(true)
  }

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
          onClick={close}
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
          onClick={dismissForever}
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
