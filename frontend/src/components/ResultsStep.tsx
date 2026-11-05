import { lazy, Suspense } from 'react'
import { exportUrl, type Results } from '../api'
import { ChartBoundary } from './ChartBoundary'
import { loadChart } from './lazyChart'

const ScoreChart = lazy(loadChart)

interface Props {
  sessionId: string
  results: Results
  onEdit: () => void
  onRestart: () => void
}

const SCORES = ['1', '2', '3', '4', '5']

export function ResultsStep({ sessionId, results, onEdit, onRestart }: Props) {
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
          <Suspense
            fallback={
              <div className="chart-placeholder" role="status" aria-label="Loading chart">
                <div className="spinner" />
              </div>
            }
          >
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
          <button type="button" className="secondary" onClick={onRestart}>
            Upload another file
          </button>
        </div>
      </section>

      <section className="card">
        <h2>Numbers</h2>
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
              {results.aspects.map((item) => (
                <tr key={item.aspect}>
                  <th scope="row">{item.aspect}</th>
                  <td>{item.mention_count}</td>
                  <td>{item.mean_score === null ? '–' : item.mean_score.toFixed(2)}</td>
                  {SCORES.map((score) => (
                    <td key={score}>{item.distribution[score] ?? 0}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  )
}
