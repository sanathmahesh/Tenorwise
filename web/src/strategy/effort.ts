// Effort timings (PLAN.md section 11, item 2): parsed from docs/strategy/effort-timings.csv.
// Only the owner records timings. This code never fills or estimates one; it only
// computes minutes from the recorded start and end times, and reports bad rows.

export const EFFORT_COLUMNS = [
  'task_id', 'method', 'date', 'start_time', 'end_time', 'completed', 'matches_engine', 'notes',
] as const

export interface TimingRow {
  task_id: string
  method: 'manual' | 'tool'
  date: string
  start_time: string
  end_time: string
  minutes: number
  completed: 'yes' | 'no'
  matches_engine: 'yes' | 'partly' | 'no' | 'n/a'
  notes: string
}

export interface Timings {
  rows: TimingRow[]
  errors: string[]
}

/** Minimal RFC 4180 CSV: quoted fields, doubled quotes, CRLF or LF; blank lines skipped. */
export function parseCsv(text: string): string[][] {
  const records: string[][] = []
  let field = ''
  let record: string[] = []
  let quoted = false
  for (let i = 0; i < text.length; i++) {
    const c = text[i]
    if (quoted) {
      if (c === '"' && text[i + 1] === '"') { field += '"'; i++ }
      else if (c === '"') quoted = false
      else field += c
    } else if (c === '"' && field === '') quoted = true
    else if (c === ',') { record.push(field); field = '' }
    else if (c === '\n' || c === '\r') {
      if (c === '\r' && text[i + 1] === '\n') i++
      record.push(field); field = ''
      if (record.some((f) => f !== '')) records.push(record)
      record = []
    } else field += c
  }
  record.push(field)
  if (record.some((f) => f !== '')) records.push(record)
  return records
}

function clockMinutes(hhmm: string): number | null {
  const m = /^([01]\d|2[0-3]):([0-5]\d)$/.exec(hhmm)
  return m ? Number(m[1]) * 60 + Number(m[2]) : null
}

function checkRow(r: string[]): string | TimingRow {
  if (r.length !== EFFORT_COLUMNS.length) return `expected ${EFFORT_COLUMNS.length} fields, found ${r.length}`
  const [task_id, method, date, start_time, end_time, completed, matches_engine, notes] = r.map((f) => f.trim())
  if (!/^T\d+$/.test(task_id)) return `task_id "${task_id}" is not like T1`
  if (method !== 'manual' && method !== 'tool') return `method "${method}" must be manual or tool`
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return `date "${date}" must be YYYY-MM-DD`
  const start = clockMinutes(start_time)
  const end = clockMinutes(end_time)
  if (start === null || end === null) return 'start_time and end_time must be HH:MM (24-hour)'
  if (end < start) return 'end_time is before start_time'
  if (completed !== 'yes' && completed !== 'no') return `completed "${completed}" must be yes or no`
  if (!['yes', 'partly', 'no', 'n/a'].includes(matches_engine)) return `matches_engine "${matches_engine}" must be yes, partly, no or n/a`
  return {
    task_id, method, date, start_time, end_time, minutes: end - start, completed,
    matches_engine: matches_engine as TimingRow['matches_engine'], notes,
  }
}

export function parseTimings(text: string): Timings {
  const records = parseCsv(text)
  if (records.length === 0 || records[0].map((h) => h.trim()).join(',') !== EFFORT_COLUMNS.join(',')) {
    return { rows: [], errors: [`the header must be: ${EFFORT_COLUMNS.join(',')}`] }
  }
  const rows: TimingRow[] = []
  const errors: string[] = []
  records.slice(1).forEach((r, i) => {
    const out = checkRow(r)
    if (typeof out === 'string') errors.push(`row ${i + 2}: ${out}`)
    else rows.push(out)
  })
  return { rows, errors }
}
