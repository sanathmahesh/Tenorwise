// The strategy artifacts, rendered on the About page from the same files in docs/strategy/
// (PLAN.md section 11). Imported as raw text at build time; nothing is copied by hand.
import decisionLog from '../../../docs/strategy/decision-log.md?raw'
import effort from '../../../docs/strategy/effort.md?raw'
import effortTimings from '../../../docs/strategy/effort-timings.csv?raw'
import modelMemo from '../../../docs/strategy/model-memo.md?raw'
import opportunityMap from '../../../docs/strategy/opportunity-map.md?raw'
import riskControls from '../../../docs/strategy/risk-controls.md?raw'
import rolloutPlan from '../../../docs/strategy/rollout-plan.md?raw'

export interface StrategyDoc {
  id: string
  label: string
  markdown: string
}

export const STRATEGY_DOCS: StrategyDoc[] = [
  { id: 'opportunity-map', label: 'Opportunity map', markdown: opportunityMap },
  { id: 'effort', label: 'Effort', markdown: effort },
  { id: 'model-memo', label: 'Model memo', markdown: modelMemo },
  { id: 'risk-controls', label: 'Risks and controls', markdown: riskControls },
  { id: 'rollout-plan', label: 'Rollout plan (proposal)', markdown: rolloutPlan },
  { id: 'decision-log', label: 'Decision log', markdown: decisionLog },
]

export const EFFORT_TIMINGS_CSV = effortTimings
