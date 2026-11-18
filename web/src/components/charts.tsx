// SVG charts in the design's chart frame: plot area on the surface fill, y labels at the top and
// bottom of a left column, x ticks beneath, zero rules only, labels on the lines, no legends.
import type { ReactNode } from 'react'
import { linear } from '../lib/scales'
import { useWidth } from '../lib/useWidth'

export interface Series {
  points: [number, number][]
  tone: 'ink' | 'grey'
  dashed?: boolean
  label?: string
}
export interface Marker { x: number; y: number; label: string }
export interface Note { x: number; y: number; text: string }

export interface LineChartProps {
  title: string
  height: number
  x: { domain: [number, number]; map?: (v: number) => number; ticks: { value: number; label: string }[] }
  y: { domain: [number, number]; format: (v: number) => string }
  series: Series[]
  markers?: Marker[]
  notes?: Note[]
  zeroX?: boolean
  zeroY?: boolean
  caption?: ReactNode
}

const GUTTER = 48
const AXIS = 22

export function LineChart(p: LineChartProps) {
  const [ref, width] = useWidth()
  const mapX = p.x.map ?? ((v: number) => v)
  const plotW = Math.max(60, width - GUTTER - 8)
  const sx = linear([mapX(p.x.domain[0]), mapX(p.x.domain[1])], [GUTTER, GUTTER + plotW])
  const X = (v: number) => sx(mapX(v))
  const Y = linear(p.y.domain, [p.height, 0])
  const color = (t: Series['tone']) => (t === 'ink' ? 'var(--ink)' : 'var(--grey-2)')
  return (
    <figure className="chart" ref={ref}>
      <svg width={width} height={p.height + AXIS} role="img" aria-label={p.title}>
        <rect className="plot" x={GUTTER} y={0} width={plotW} height={p.height} />
        <text x={GUTTER - 6} y={10} textAnchor="end">{p.y.format(p.y.domain[1])}</text>
        <text x={GUTTER - 6} y={p.height} textAnchor="end">{p.y.format(p.y.domain[0])}</text>
        {p.zeroY && p.y.domain[0] < 0 && p.y.domain[1] > 0 && (
          <line className="zero" x1={GUTTER} x2={GUTTER + plotW} y1={Y(0)} y2={Y(0)} />
        )}
        {p.zeroX && p.x.domain[0] < 0 && p.x.domain[1] > 0 && (
          <line className="zero" x1={X(0)} x2={X(0)} y1={0} y2={p.height} />
        )}
        {p.x.ticks.map((t) => (
          <text key={t.value} x={X(t.value)} y={p.height + 15} textAnchor="middle">{t.label}</text>
        ))}
        {p.series.map((s, i) => (
          <polyline
            key={i}
            fill="none"
            stroke={color(s.tone)}
            strokeWidth={s.dashed ? 1.5 : 2}
            strokeDasharray={s.dashed ? '5 4' : undefined}
            points={s.points.map(([x, y]) => `${X(x)},${Y(y)}`).join(' ')}
          />
        ))}
        {p.series.filter((s) => s.label).map((s, i) => {
          const [x, y] = s.points[s.points.length - 1]
          return (
            <text key={i} className="series-label" x={X(x) - 4} y={Y(y) - 6} textAnchor="end">{s.label}</text>
          )
        })}
        {(p.markers ?? []).map((m, i) => {
          const mx = X(m.x)
          const right = mx > GUTTER + plotW * 0.6
          return (
            <g key={i}>
              <circle cx={mx} cy={Y(m.y)} r={4} fill="var(--ink)" />
              <text className="series-label" x={right ? mx - 8 : mx + 8} y={Y(m.y) - 8} textAnchor={right ? 'end' : 'start'}>{m.label}</text>
            </g>
          )
        })}
        {(p.notes ?? []).map((n, i) => {
          const nx = X(n.x)
          const anchor = nx > GUTTER + plotW - 30 ? 'end' : nx < GUTTER + 30 ? 'start' : 'middle'
          return <text key={i} className="series-label" x={nx} y={Y(n.y) - 8} textAnchor={anchor}>{n.text}</text>
        })}
      </svg>
      {p.caption && <figcaption className="caption">{p.caption}</figcaption>}
    </figure>
  )
}
