import { lazy, Suspense } from 'react'
import { exportUrl, type AspectResult, type Results } from '../api'
import { formatScore } from '../format'
import { ChartBoundary } from './ChartBoundary'
import { loadChart } from './lazyChart'

const ScoreChart = lazy(loadChart)

const SCORES = ['1', '2', '3', '4', '5']

interface Props {
  sessionId: string
  results: Results
  onEdit: () => void
}

export function ResultsStep({ sessionId, results, onEdit }: Props) {
  return (
    <>
      <section className="card">
        <h2>{results.product_name}</h2>
        <p className="muted">
          {results.analyzed_count} of {results.review_count} reviews analyzed.
          {results.failed_count > 0 &&
            ` ${results.failed_count} could not be scored and are marked as failed in the CSV.`}
        </p>
        <ChartBoundary>
          <Suspense fallback={<ChartPlaceholder />}>
            <ScoreChart aspects={results.aspects} />
          </Suspense>
        </ChartBoundary>
        <div className="actions">
          <a className="button" href={exportUrl(sessionId)} download>
            Download CSV
          </a>
          <button type="button" className="secondary" onClick={onEdit}>
            Edit the aspects
          </button>
        </div>
      </section>

      <section className="card">
        <h2>Numbers</h2>
        <ScoreTable aspects={results.aspects} />
      </section>
    </>
  )
}

function ChartPlaceholder() {
  return (
    <div className="chart-placeholder" role="status" aria-label="Loading chart">
      <div className="spinner" />
    </div>
  )
}

function ScoreTable({ aspects }: { aspects: AspectResult[] }) {
  return (
    <div className="table-wrap">
      <table>
        <caption className="visually-hidden">Scores per aspect</caption>
        <thead>
          <tr>
            <th scope="col">Aspect</th>
            <th scope="col">Mentions</th>
            <th scope="col">Average</th>
            {SCORES.map((score) => (
              <th key={score} scope="col" title={`Reviews that gave ${score}`}>
                {score}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {aspects.map((item) => (
            <tr key={item.aspect}>
              <th scope="row">{item.aspect}</th>
              <td>{item.mention_count}</td>
              <td>{formatScore(item.mean_score)}</td>
              {SCORES.map((score) => (
                <td key={score}>{item.distribution[score] ?? 0}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
