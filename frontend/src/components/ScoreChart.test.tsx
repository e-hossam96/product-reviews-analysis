import { render } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'
import type { AspectResult } from '../api'
import { ScoreChart } from './ScoreChart'

const original = globalThis.ResizeObserver

// jsdom does no layout, so tell the chart's container how big it is.
beforeEach(() => {
  globalThis.ResizeObserver = class {
    private readonly callback: ResizeObserverCallback
    constructor(callback: ResizeObserverCallback) {
      this.callback = callback
    }
    observe(target: Element) {
      const entry = { target, contentRect: { width: 640, height: 360 } } as ResizeObserverEntry
      this.callback([entry], this as unknown as ResizeObserver)
    }
    unobserve() {}
    disconnect() {}
  } as unknown as typeof ResizeObserver
})

afterEach(() => {
  globalThis.ResizeObserver = original
})

const aspect = (name: string, mean: number | null, mentions: number): AspectResult => ({
  aspect: name,
  mean_score: mean,
  mention_count: mentions,
  distribution: { '1': 0, '2': 0, '3': 0, '4': 0, '5': 0 },
})

describe('ScoreChart', () => {
  it('draws a bar for every aspect that was mentioned, and none for the others', () => {
    const { container } = render(
      <ScoreChart
        aspects={[aspect('battery life', 4.5, 4), aspect('screen', 2, 3), aspect('price', null, 0)]}
      />,
    )
    expect(container.querySelectorAll('.recharts-bar-rectangle')).toHaveLength(2)
  })

  it('labels each bar with its average', () => {
    const { container } = render(
      <ScoreChart aspects={[aspect('battery life', 4.5, 4), aspect('screen', 2, 3)]} />,
    )
    const labels = [...container.querySelectorAll('.recharts-label')].map((el) => el.textContent)
    expect(labels).toEqual(expect.arrayContaining(['4.5', '2.0']))
  })

  it('has one tick per aspect on the x axis and 0 to 5 on the y axis', () => {
    const { container } = render(
      <ScoreChart aspects={[aspect('battery life', 4.5, 4), aspect('screen', 2, 3)]} />,
    )
    expect(
      container.querySelectorAll('.recharts-xAxis .recharts-cartesian-axis-tick'),
    ).toHaveLength(2)
    expect(
      container.querySelectorAll('.recharts-yAxis .recharts-cartesian-axis-tick'),
    ).toHaveLength(6)
  })
})
