interface Series {
  label: string
  values: number[]
  className: string
}

interface Props {
  dates: string[]
  series: Series[]
  format: (n: number) => string
  height?: number
}

const W = 600
const PAD = { top: 10, right: 12, bottom: 22, left: 64 }

/** Minimal responsive SVG line chart for a few series sharing one x axis. */
export function LineChart({ dates, series, format, height = 220 }: Props) {
  const all = series.flatMap((s) => s.values)
  if (dates.length < 2 || all.length === 0) return null
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const innerW = W - PAD.left - PAD.right
  const innerH = height - PAD.top - PAD.bottom
  const x = (i: number) => PAD.left + (i / (dates.length - 1)) * innerW
  const y = (v: number) => PAD.top + (1 - (v - min) / span) * innerH
  const ticks = [min, min + span / 2, max]

  return (
    <figure className="chart">
      <svg viewBox={`0 0 ${W} ${height}`} role="img" aria-label={series.map((s) => s.label).join(' vs ')}>
        {ticks.map((t) => (
          <g key={t}>
            <line className="chart-grid" x1={PAD.left} x2={W - PAD.right} y1={y(t)} y2={y(t)} />
            <text className="chart-axis" x={PAD.left - 6} y={y(t) + 4} textAnchor="end">
              {format(t)}
            </text>
          </g>
        ))}
        <text className="chart-axis" x={PAD.left} y={height - 4}>
          {dates[0]}
        </text>
        <text className="chart-axis" x={W - PAD.right} y={height - 4} textAnchor="end">
          {dates[dates.length - 1]}
        </text>
        {series.map((s) => (
          <polyline
            key={s.label}
            className={`chart-line ${s.className}`}
            points={s.values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(' ')}
          />
        ))}
      </svg>
      <figcaption className="chart-legend">
        {series.map((s) => (
          <span key={s.label}>
            <i className={`swatch ${s.className}`} /> {s.label}
          </span>
        ))}
      </figcaption>
    </figure>
  )
}
