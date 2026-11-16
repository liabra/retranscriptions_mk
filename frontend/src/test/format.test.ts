import { describe, expect, it } from 'vitest'
import { etapeIndex, fDuree, fMoney, fSize, relative } from '@/lib/format'

describe('formatage', () => {
  it('formate les montants en euros', () => {
    expect(fMoney('100')).toMatch(/100,00\s?€/)
    expect(fMoney(null)).toBe('—')
  })
  it('formate tailles et durées', () => {
    expect(fSize(2048)).toBe('2 Ko')
    expect(fSize(5 * 1024 * 1024)).toBe('5,0 Mo')
    expect(fDuree(95)).toBe('1 h 35')
    expect(fDuree(null)).toBe('—')
  })
  it('signale une échéance dépassée', () => {
    const hier = new Date(Date.now() - 2 * 86400000).toISOString()
    expect(relative(hier).tone).toBe('red')
    expect(relative(null).texte).toBe('Sans échéance')
    const loin = new Date(Date.now() + 10 * 86400000).toISOString()
    expect(relative(loin).tone).toBe('green')
  })
  it('place les étapes dans la frise', () => {
    expect(etapeIndex('a_qualifier')).toBe(0)
    expect(etapeIndex('valide')).toBeGreaterThan(etapeIndex('a_relire'))
  })
})
