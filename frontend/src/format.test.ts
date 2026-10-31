import { describe, expect, it } from 'vitest'
import { money, pct, tone, weight } from './format'

describe('format', () => {
  it('formats money', () => {
    expect(money(1234.5)).toBe('$1,234.50')
  })

  it('signs percentages and handles missing values', () => {
    expect(pct(12.345)).toBe('+12.35%')
    expect(pct(-3)).toBe('-3.00%')
    expect(pct(null)).toBe('—')
    expect(pct(-0.001)).toBe('0.00%')
  })

  it('formats weights and tones', () => {
    expect(weight(33.333)).toBe('33.3%')
    expect(tone(1)).toBe('pos')
    expect(tone(-1)).toBe('neg')
    expect(tone(0)).toBe('')
  })
})
