// The three API calls. HTTP errors come back as { detail } (429 limit, 503 unavailable, 422 invalid input).
import type { AgentResponse, ScenarioRequest, ScenarioResponse } from './types'

export type ApiResult<T> =
  | { ok: true; body: T }
  | { ok: false; status: number; detail: string }

function detailText(detail: unknown): string {
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail)) {
    return detail.map((d) => (d && typeof d === 'object' && 'msg' in d ? String((d as { msg: unknown }).msg) : String(d))).join('; ')
  }
  return 'The request failed.'
}

async function post<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  let r: Response
  try {
    r = await fetch(path, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  } catch {
    return { ok: false, status: 0, detail: 'The network request failed. Check your connection and try again.' }
  }
  let parsed: unknown = null
  try { parsed = await r.json() } catch { /* empty or non-JSON body */ }
  if (r.ok && parsed) return { ok: true, body: parsed as T }
  const detail = parsed && typeof parsed === 'object' && 'detail' in parsed ? detailText((parsed as { detail: unknown }).detail) : `HTTP ${r.status}`
  return { ok: false, status: r.status, detail }
}

export const priceScenario = (req: ScenarioRequest) => post<ScenarioResponse>('/api/scenario', req)

export interface Turn { role: 'user' | 'assistant'; content: string }

export const askAnalyst = (question: string, history: Turn[]) =>
  post<AgentResponse>('/api/agent/ask', { question, history })

export const draftCommentary = () => post<AgentResponse>('/api/agent/commentary', {})
