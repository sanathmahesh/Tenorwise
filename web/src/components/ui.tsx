// Shared pieces from the design spec: tags, figure blocks, assumption callouts, page states,
// the side panel and the Markdown renderer.
import { X } from '@phosphor-icons/react'
import { useEffect, useRef, type ReactNode } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import type { AssumptionItem } from '../api/types'
import { valueTagFromHref } from '../lib/tags'

export function Tag({ children }: { children: ReactNode }) {
  return <span className="tag tag-mark">{children}</span>
}

export function Stylized() {
  return <Tag>Stylized</Tag>
}

export function ScreenTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <header>
      <h1 className="title">{title}</h1>
      {children}
    </header>
  )
}

export function Figure({ label, value, unit, caption, tone }: {
  label: string; value: string; unit?: string; caption?: ReactNode; tone?: string
}) {
  return (
    <div>
      <h6 className="figure-label">{label}</h6>
      <div className={`figure-value ${tone ?? ''}`}>{value}{unit && <span className="figure-unit">{unit}</span>}</div>
      {caption && <div className="figure-caption">{caption}</div>}
    </div>
  )
}

/** An ASSUMPTION callout with the text of a meta.assumptions[] entry. */
export function Assumption({ assumptions, id, prefix }: { assumptions: AssumptionItem[]; id: string; prefix?: string }) {
  const a = assumptions.find((x) => x.id === id)
  if (!a) return null
  return (
    <div className="assumption">
      <Tag>Assumption</Tag>
      <p>{prefix}{a.text} <span className="sub" style={{ fontStyle: 'normal' }}>({a.id})</span></p>
    </div>
  )
}

export function Loading() {
  return (
    <div aria-busy="true">
      <div className="skeleton" style={{ height: 46, width: 260 }} />
      <p className="sub" style={{ marginTop: 15 }}>Loading precomputed results.</p>
      <div className="figures" style={{ marginTop: 30 }}>
        {[0, 1, 2, 3].map((i) => <div key={i} className="skeleton" style={{ height: 70 }} />)}
      </div>
      <div className="skeleton" style={{ height: 220, marginTop: 40 }} />
    </div>
  )
}

export function LoadError({ title, error, retry }: { title: string; error: string; retry: () => void }) {
  return (
    <div role="alert">
      <p className="state-label loss">Could not load</p>
      <h1 className="title">{title}</h1>
      <p className="intro">This screen's data did not arrive, so no numbers are shown rather than old or partial ones. ({error})</p>
      <button className="btn btn-secondary" onClick={retry}>Retry</button>
    </div>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty-block">
      <strong>Nothing to show yet.</strong> {children}
    </div>
  )
}

export function Progress({ label }: { label: string }) {
  return <div className="progress" role="progressbar" aria-label={label} />
}

/** Right-hand side panel: closes on its button or Escape. */
export function SidePanel({ title, heading, onClose, children }: {
  title: string; heading: string; onClose: () => void; children: ReactNode
}) {
  const closeRef = useRef<HTMLButtonElement>(null)
  useEffect(() => {
    closeRef.current?.focus()
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  return (
    <aside className="panel" role="dialog" aria-label={title}>
      <div className="panel-head">
        <h2>{heading}</h2>
        <button ref={closeRef} className="btn btn-secondary panel-close" onClick={onClose} aria-label="Close">
          <X weight="duotone" size={18} />
        </button>
      </div>
      {children}
    </aside>
  )
}

/** Markdown with the design's table frame. Links to "#value-vN" become number links when onValue is given. */
export function Md({ children, onValue }: { children: string; onValue?: (tag: string) => void }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        table: ({ children: c }) => <div className="md-table" tabIndex={0}><table>{c}</table></div>,
        a: ({ href, children: c }) => {
          const tag = valueTagFromHref(href)
          if (tag && onValue) {
            return <button type="button" className="number-link" onClick={() => onValue(tag)}>{fixMinus(c)}</button>
          }
          if (href && /^https?:\/\//.test(href)) return <a href={href} target="_blank" rel="noreferrer">{c}</a>
          return <span>{c}</span> // links into the repository have no page on the site
        },
      }}
    >
      {children}
    </Markdown>
  )
}

/** Typographic minus for a leading hyphen in a number link; the verified text is otherwise unchanged. */
function fixMinus(children: ReactNode): ReactNode {
  return typeof children === 'string' ? children.replace(/^(\(?)-/, '$1−') : children
}
