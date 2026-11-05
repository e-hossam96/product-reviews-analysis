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
} from 'recharts'
import type { AspectResult } from '../api'
import { scoreColor, truncate } from '../format'

interface Datum {
  aspect: string
  mean: number | null
  mentions: number
  label: string
}

const MAX_TICK_CHARS = 16

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
  const data: Datum[] = aspects.map((item) => ({
    aspect: item.aspect,
    mean: item.mean_score,
    mentions: item.mention_count,
    label: item.mean_score === null ? '' : item.mean_score.toFixed(1),
  }))

  return (
    <div className="chart" role="img" aria-label="Average score for each aspect, from 1 to 5">
      <ResponsiveContainer width="100%" height={360}>
        <BarChart data={data} margin={{ top: 24, right: 16, bottom: 8, left: 0 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} />
          <XAxis
            dataKey="aspect"
            interval={0}
            tickFormatter={(text: string) => truncate(text, MAX_TICK_CHARS)}
          />
          <YAxis domain={[0, 5]} ticks={[0, 1, 2, 3, 4, 5]} allowDecimals={false} width={32} />
          <Tooltip content={ChartTooltip} cursor={{ fillOpacity: 0.08 }} />
          <Bar dataKey="mean" radius={[4, 4, 0, 0]} maxBarSize={72} isAnimationActive={false}>
            {data.map((datum) => (
              <Cell key={datum.aspect} fill={scoreColor(datum.mean)} />
            ))}
            <LabelList dataKey="label" position="top" />
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
