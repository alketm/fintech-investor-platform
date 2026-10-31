const usd = new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD' })

export const money = (n: number) => usd.format(n)

export const pct = (n: number | null | undefined, digits = 2) => {
  if (n == null) return '—'
  const rounded = Number(n.toFixed(digits)) || 0 // `|| 0` turns -0 into 0
  return `${rounded > 0 ? '+' : ''}${rounded.toFixed(digits)}%`
}

export const weight = (n: number) => `${n.toFixed(1)}%`

export const tone = (n: number | null | undefined) =>
  n == null || n === 0 ? '' : n > 0 ? 'pos' : 'neg'
