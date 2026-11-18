// The eight screens and the selection shared between them.
export const SCREENS = ['Overview', 'Curve', 'Portfolio', 'Scenarios', 'Hedging', 'Analyst', 'Evidence', 'About'] as const
export type Screen = (typeof SCREENS)[number]

export interface Shared {
  go: (screen: Screen) => void
  scenarioId: string
  setScenarioId: (id: string) => void
  strategyId: string
  setStrategyId: (id: string) => void
}
