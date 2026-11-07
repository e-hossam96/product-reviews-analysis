import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  type XAxisTickContentProps,
} from 'recharts'
import type { AspectResult } from '../api'
import { SCORE_STOPS, scoreColor, wrapLabel } from '../format'
import { useColorScheme } from '../theme'

interface Datum {
  aspect: string
  mean: number | null
  mentions: number
  label: string
}

const TICK_FONT_PX = 12
const TICK_LINE_PX = 15
const TICK_MAX_LINES = 3
const CHAR_PX = TICK_FONT_PX * 0.58 // average width of a character in the UI font
const TICK_GAP_PX = 8 // space kept between neighbouring labels

/** An x-axis label that wraps onto several lines to fit the width of its bar's slot. */
function AspectTick({ x, y, payload, width, visibleTicksCount }: XAxisTickContentProps) {
  const slot = Number(width) / Math.max(visibleTicksCount, 1)
  const lines = wrapLabel(String(payload.value), (slot - TICK_GAP_PX) / CHAR_PX, TICK_MAX_LINES)
  return (
    <text
      x={Number(x)}
      y={Number(y)}
      textAnchor="middle"
      fontSize={TICK_FONT_PX}
      className="recharts-cartesian-axis-tick-value"
    >
      <title>{String(payload.value)}</title>
      {lines.map((line, index) => (
        <tspan key={index} x={Number(x)} dy={index === 0 ? '0.9em' : TICK_LINE_PX}>
          {line}
        </tspan>
      ))}
    </text>
  )
}

function ChartTooltip({
  active,
  payload,
}: {
  active?: boolean
  payload?: ReadonlyArray<{ payload?: Datum }>
}) {
  const datum = payload?.[0]?.payload
  if (!active || !datum) {
    return null
  }
  return (
    <div className="chart-tooltip">
      <strong>{datum.aspect}</strong>
      <div>
        {datum.mean === null ? 'Not mentioned' : `Average ${datum.mean.toFixed(2)} out of 5`}
      </div>
      <div>
        {datum.mentions} mention{datum.mentions === 1 ? '' : 's'}
      </div>
    </div>
  )
}

export function ScoreChart({ aspects }: { aspects: AspectResult[] }) {
  const scheme = useColorScheme()
  const data: Datum[] = aspects.map((item) => ({
    aspect: item.aspect,
    mean: item.mean_score,
    mentions: item.mention_count,
    label: item.mean_score === null ? '' : item.mean_score.toFixed(1),
  }))

  return (
    <>
      <div className="chart" role="img" aria-label="Average score for each aspect, from 1 to 5">
        <ResponsiveContainer width="100%" height={380}>
          <BarChart data={data} margin={{ top: 24, right: 16, bottom: 4, left: 0 }}>
            <CartesianGrid vertical={false} />
            <XAxis
              dataKey="aspect"
              interval={0}
              height={TICK_MAX_LINES * TICK_LINE_PX + 12}
              tickLine={false}
              tick={AspectTick}
            />
            <YAxis
              domain={[0, 5]}
              ticks={[0, 1, 2, 3, 4, 5]}
              allowDecimals={false}
              width={32}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={ChartTooltip}
              cursor={{ fill: 'var(--accent-soft)', fillOpacity: 0.6 }}
            />
            <Bar dataKey="mean" radius={[4, 4, 0, 0]} maxBarSize={64} isAnimationActive={false}>
              {data.map((datum) => (
                <Cell key={datum.aspect} fill={scoreColor(datum.mean, scheme)} />
              ))}
              <LabelList dataKey="label" position="top" />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <div className="score-legend">
        <span>1 · Negative</span>
        <span
          className="score-legend-bar"
          style={{ background: `linear-gradient(to right, ${SCORE_STOPS[scheme].join(', ')})` }}
        />
        <span>5 · Positive</span>
      </div>
    </>
  )
}
