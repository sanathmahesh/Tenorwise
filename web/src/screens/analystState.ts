// The analyst's request state. It lives in App so an answer survives moving between screens.
import { useCallback, useRef, useState } from 'react'
import { askAnalyst, draftCommentary, type ApiResult, type Turn } from '../api/client'
import type { AgentResponse } from '../api/types'

export const SUGGESTED = [
  'How much does the portfolio lose if rates rise 100 bp?',
  'What would a repeat of 2022 do to AOCI?',
  'How much carry does the full DV01 hedge give up in the base case?',
  'What is the stylized mortgage pool’s price if rates fall 200 bp?',
  'What is the DV01 of the held-to-maturity book?',
  'Where will the 10-year Treasury yield be next year?',
]

type Status = 'idle' | 'loading' | 'answered' | 'cannot_answer' | 'blocked' | 'limit' | 'error'

export interface AnalystState {
  status: Status
  question: string | null
  isCommentary: boolean
  response: AgentResponse | null
  detail: string | null
  startedAt: number | null
  ask: (q: string) => void
  commentary: () => void
  retry: () => void
}

/** Lives in App so an answer survives moving between screens. */
export function useAnalyst(): AnalystState {
  const [status, setStatus] = useState<Status>('idle')
  const [question, setQuestion] = useState<string | null>(null)
  const [isCommentary, setIsCommentary] = useState(false)
  const [response, setResponse] = useState<AgentResponse | null>(null)
  const [detail, setDetail] = useState<string | null>(null)
  const [startedAt, setStartedAt] = useState<number | null>(null)
  const history = useRef<Turn[]>([])
  const last = useRef<() => void>(() => {})

  const settle = useCallback((r: ApiResult<AgentResponse>, q: string | null) => {
    if (!r.ok) {
      setResponse(null); setDetail(r.detail); setStatus(r.status === 429 ? 'limit' : 'error')
      return
    }
    const body = r.body
    setResponse(body); setDetail(body.error ?? null)
    setStatus(body.status === 'error' ? 'error' : body.status)
    if (q && (body.status === 'answered' || body.status === 'cannot_answer')) {
      history.current = [...history.current, { role: 'user' as const, content: q }, { role: 'assistant' as const, content: body.answer_md }].slice(-10)
    }
  }, [])

  const ask = useCallback((q: string) => {
    const run = async () => {
      setStatus('loading'); setStartedAt(Date.now()); setQuestion(q); setIsCommentary(false); setResponse(null); setDetail(null)
      settle(await askAnalyst(q, history.current), q)
    }
    last.current = run
    void run()
  }, [settle])

  const commentary = useCallback(() => {
    const run = async () => {
      setStatus('loading'); setStartedAt(Date.now()); setQuestion(null); setIsCommentary(true); setResponse(null); setDetail(null)
      settle(await draftCommentary(), null)
    }
    last.current = run
    void run()
  }, [settle])

  const retry = useCallback(() => last.current(), [])
  return { status, question, isCommentary, response, detail, startedAt, ask, commentary, retry }
}
