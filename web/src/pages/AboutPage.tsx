// About page (Phase 10): the strategy artifacts, rendered from docs/strategy/.
// Placeholder styling; the real design arrives in Phase 11.
import type { ReactNode } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { EFFORT_TIMINGS_CSV, STRATEGY_DOCS } from '../strategy/docs'
import { parseTimings } from '../strategy/effort'

function Doc({ markdown }: { markdown: string }) {
  return (
    <Markdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Links into the repository have no page on the site: show them as text.
        a: ({ href, children }: { href?: string; children?: ReactNode }) =>
          href && /^https?:\/\//.test(href)
            ? <a href={href} target="_blank" rel="noreferrer">{children}</a>
            : <span>{children}</span>,
      }}
    >
      {markdown}
    </Markdown>
  )
}

export function EffortTimings({ csv }: { csv: string }) {
  const { rows, errors } = parseTimings(csv)
  return (
    <div>
      <h2>Recorded timings</h2>
      <p>Operator: one non-expert (the author, with no finance background). The timings describe this operator only.</p>
      {rows.length === 0
        ? <p><strong>Timings not yet recorded.</strong> The owner records them in docs/strategy/effort-timings.csv.</p>
        : (
          <table>
            <thead>
              <tr><th>Task</th><th>Method</th><th>Date</th><th>Start</th><th>End</th><th>Minutes</th><th>Completed</th><th>Matches engine</th><th>Notes</th></tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <tr key={i}>
                  <td>{r.task_id}</td><td>{r.method}</td><td>{r.date}</td><td>{r.start_time}</td><td>{r.end_time}</td>
                  <td>{r.minutes}</td><td>{r.completed}</td><td>{r.matches_engine}</td><td>{r.notes}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      {errors.length > 0 && (
        <div role="alert">
          <p>Rows not shown because they are malformed:</p>
          <ul>{errors.map((e) => <li key={e}>{e}</li>)}</ul>
        </div>
      )}
    </div>
  )
}

export function AboutPage() {
  return (
    <div>
      <p>
        Why Tenorwise exists, how its AI is governed, and what the evidence shows. Each section is rendered from the
        same file in the repository's docs/strategy/ folder.
      </p>
      <nav aria-label="About sections">
        <ul>
          {STRATEGY_DOCS.map((d) => <li key={d.id}><a href={`#${d.id}`}>{d.label}</a></li>)}
        </ul>
      </nav>
      {STRATEGY_DOCS.map((d) => (
        <section key={d.id} id={d.id}>
          <Doc markdown={d.markdown} />
          {d.id === 'effort' && <EffortTimings csv={EFFORT_TIMINGS_CSV} />}
        </section>
      ))}
    </div>
  )
}
