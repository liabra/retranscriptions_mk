import { createContext, useContext, useState } from 'react'

interface HintsContextType {
  enabled: boolean
  toggle: () => void
}

const HintsContext = createContext<HintsContextType>({ enabled: true, toggle: () => {} })

export function HintsProvider({ children }: { children: React.ReactNode }) {
  const [enabled, setEnabled] = useState(
    () => localStorage.getItem('ux_hints_enabled') !== 'false',
  )

  function toggle() {
    const next = !enabled
    localStorage.setItem('ux_hints_enabled', next ? 'true' : 'false')
    setEnabled(next)
  }

  return <HintsContext.Provider value={{ enabled, toggle }}>{children}</HintsContext.Provider>
}

export function useHints() {
  return useContext(HintsContext)
}
