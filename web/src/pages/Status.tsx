import type { Loaded } from '../api/useJson'

export function Status<T>({ loaded }: { loaded: Loaded<T> }) {
  return <p>{loaded.state === 'error' ? `Could not load the snapshot: ${loaded.error}` : 'Loading…'}</p>
}
