import { createContext, useContext, useState } from 'react'

interface HintsContextType {
  enabled: boolean
  dismissedHints: Set<string>
  toggle: () => void
  dismiss: (hintId: string, forever: boolean) => void
}

const HintsContext = createContext<HintsContextType>({
  enabled: true,
  dismissedHints: new Set(),
  toggle: () => {},
  dismiss: () => {},
})

/** Charge depuis localStorage l'ensemble des hints dismissés définitivement */
function loadDismissed(): Set<string> {
  const dismissed = new Set<string>()
  for (const key of Object.keys(localStorage)) {
    if (key.startsWith('ux_hint_dismissed_')) {
      dismissed.add(key.replace('ux_hint_dismissed_', ''))
    }
  }
  return dismissed
}

export function HintsProvider({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(
    () => localStorage.getItem('ux_hints_enabled') !== 'false',
  )
  // dismissedHints centralise TOUS les états de fermeture (session + permanent)
  const [dismissedHints, setDismissedHints] = useState<Set<string>>(loadDismissed)

  function toggle() {
    const next = !enabled
    localStorage.setItem('ux_hints_enabled', next ? 'true' : 'false')
    if (next) {
      // Réactiver = effacer tous les dismissals permanents + la session en cours
      Object.keys(localStorage)
        .filter((k) => k.startsWith('ux_hint_dismissed_'))
        .forEach((k) => localStorage.removeItem(k))
      setDismissedHints(new Set())
    }
    setEnabled(next)
  }

  function dismiss(hintId: string, forever: boolean) {
    if (forever) {
      localStorage.setItem(`ux_hint_dismissed_${hintId}`, '1')
    }
    setDismissedHints((prev) => new Set([...prev, hintId]))
  }

  return (
    <HintsContext.Provider value={{ enabled, dismissedHints, toggle, dismiss }}>
      {children}
    </HintsContext.Provider>
  )
}

export function useHints() {
  return useContext(HintsContext)
}
