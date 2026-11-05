// The chart library is about two thirds of the app, and only the results page needs it.
// It is loaded on demand, and fetched early (see App) so it is ready when the results are.
export const loadChart = () =>
  import('./ScoreChart').then((module) => ({ default: module.ScoreChart }))
