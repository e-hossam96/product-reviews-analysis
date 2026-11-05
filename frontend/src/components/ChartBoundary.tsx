import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  failed: boolean
}

/** If the chart's code cannot be loaded (for example after a new release replaced the
 *  old files while the page was open), say so instead of crashing the whole page. */
export class ChartBoundary extends Component<Props, State> {
  state: State = { failed: false }

  static getDerivedStateFromError(): State {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return (
        <p className="banner warn" role="alert">
          The chart could not be loaded. Reload the page to try again. The table below has the same
          numbers.
        </p>
      )
    }
    return this.props.children
  }
}
