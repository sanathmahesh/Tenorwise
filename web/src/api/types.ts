// Contract types, generated from docs/api/openapi.json (npm run gen:types).
import type { components } from './schema'

type S = components['schemas']
export type Meta = S['Meta']
export type AssumptionItem = S['AssumptionItem']
export type Curve = S['Curve']
export type CurvePoint = S['CurvePoint']
export type Portfolio = S['Portfolio']
export type SectorRow = S['SectorRow']
export type GroupRow = S['GroupRow']
export type PositionRow = S['PositionRow']
export type KeyRateDV01 = S['PortfolioSummary']['key_rate_dv01']
export type Mbs = S['Mbs']
export type Scenarios = S['Scenarios']
export type ScenarioEntry = S['ScenarioEntry']
export type Hedges = S['Hedges']
export type StrategyRow = S['StrategyRow']
export type GridRow = S['GridRow']
export type Methods = S['Methods']
export type Evidence = S['Evidence']
export type ScenarioRequest = S['ScenarioRequest']
export type ScenarioResponse = S['ScenarioResponse']
export type AgentResponse = S['AgentResponse']
export type ValueOut = S['ValueOut']

/** The static snapshot files the screens read (GET /data/v1/<name>.json). */
export interface Files {
  meta: Meta
  curve: Curve
  portfolio: Portfolio
  mbs: Mbs
  scenarios: Scenarios
  hedges: Hedges
  methods: Methods
  evidence: Evidence
}
export type FileName = keyof Files
