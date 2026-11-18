# Manual against tool-assisted effort

How long do typical rate-risk tasks take by hand, and how long with Tenorwise?

**Status:**
- The owner records the timings in `docs/strategy/effort-timings.csv`.
- Until that file has rows, this page says the timings are not yet recorded.
- No one else enters or estimates a timing.

**Operator:** one non-expert, the author: a master's student with no finance background. The timings describe this one operator only. They are not a productivity estimate for professionals, who would be faster by hand.

## Methods

- **Manual:** without Tenorwise. Allowed:
  - a spreadsheet and its built-in finance functions;
  - the FRED website;
  - the positions list (`data/portfolio/positions.json`);
  - a calculator;
  - web searches for definitions.

  No AI assistants.
- **Tool-assisted:** Tenorwise, including any page and the Analyst, plus anything allowed in the manual method.

## Rules

1. **Times:** record the start and end time of each attempt as HH:MM on a 24-hour clock, local time, on the same day. The page computes the minutes.
2. **Cap:** stop at 60 minutes. Record `completed` as `no` and note how far you got.
3. **Order:** alternate which method goes first, so the learning effect is spread across both methods.
   - Manual first: T1, T3 and T5.
   - Tool-assisted first: T2 and T4.
4. **`matches_engine`:**
   - for calculation tasks, after both attempts compare each answer with Tenorwise and record `yes` (equal at the precision you wrote), `partly` or `no`;
   - for the writing task, record `n/a`.
5. **`notes`:** anything that changed the time, such as an interruption, a shortcut, or the method you used.

## Tasks

### T1. Curve lookup

Find the 2-year and the 10-year Treasury par yields on Tenorwise's market data date, and the 10-year minus 2-year spread.

- **Done when:** both yields and the spread are written down.
- **Manual:** the FRED series DGS2 and DGS10, plus a calculator.

### T2. One bond's price and DV01

For position UST-A3, find the price per 100 of face and the DV01: how much its value changes when yields rise by one basis point, a hundredth of a percentage point.

- **Done when:** both figures are written down.
- **Manual:**
  - take the coupon, maturity and face from the positions list;
  - price the bond off the Treasury curve by any reasonable method, then reprice it with yields one basis point higher;
  - note the method you used.

### T3. Portfolio change in value for a +100 bp parallel rise

Estimate how much the whole portfolio's market value changes if every Treasury yield rises by one percentage point.

- **Done when:** you have one dollar figure for the portfolio.
- **Manual:** a spreadsheet over the positions list, for example modified duration × market value × 1%. You may treat mortgage positions as plain bonds; note it if you do.

### T4. Hedge trade-off at +200 bp

For a +200 bp parallel rise, how much of the AOCI loss does the full DV01 hedge avoid, and how much one-year carry does it give up?

- **Done when:** both figures are written down.
- **Manual:**
  - size a 5-year pay-fixed swap so that its DV01 offsets the AFS book's DV01;
  - value the swap after the shock;
  - work out the carry the swap gives up.

  The cap applies.

### T5. Committee note

Write a note of about 150 words for an investment committee on the +100 bp scenario: the change in value, the AOCI impact, and one hedge option with its cost in carry.

- **Done when:** you would send the note.
- **Manual:**
  - use your own T3 and T4 results, and say so if those tasks were not completed;
  - count only the writing time.
- **Tool-assisted:**
  - draft the note with the Analyst (a question or the commentary);
  - open the provenance link of every figure;
  - edit the draft until you would sign it.

## Recording

Add one row per attempt to `docs/strategy/effort-timings.csv`. The columns are:

- `task_id`: T1 to T5.
- `method`: `manual` or `tool`.
- `date`: YYYY-MM-DD.
- `start_time` and `end_time`: HH:MM.
- `completed`: `yes` or `no`.
- `matches_engine`: `yes`, `partly`, `no` or `n/a`.
- `notes`: put the note in double quotes if it contains a comma.
