// Number tags in the analyst's verified text: "falls by -$370.6M[[v11]]".
// Each tagged number becomes a Markdown link "[-$370.6M](#value-v11)" that the page renders as a
// button opening that value's provenance. The text itself is unchanged: it was verified as written.

const NUMBER =
  String.raw`\(?[+\-−–]?\$?\d[\d,]*(?:\.\d+)?(?:\s?(?:thousand|million|billion|bn|mn|[KkMB]))?` +
  String.raw`(?:\s?(?:%|bps?|basis points?|years?|yrs?|months?|per bp|\/bp))?\)?`
const TAGGED = new RegExp(`(${NUMBER})\\[\\[(v\\d+)\\]\\]`, 'g')
const BARE_TAG = /\[\[(v\d+)\]\]/g

export function linkNumbers(markdown: string): string {
  return markdown
    .replace(TAGGED, (_m, number: string, tag: string) => `[${number}](#value-${tag})`)
    .replace(BARE_TAG, (_m, tag: string) => ` [source](#value-${tag})`)
}

export function valueTagFromHref(href: string | undefined): string | null {
  const m = /^#value-(v\d+)$/.exec(href ?? '')
  return m ? m[1] : null
}
