# Model card

Skeleton. Completed in Phase 12 from the evidence gathered in Phases 1 to 10.

## Intended use

## Out-of-scope use

## Components

## Assumptions

See [ASSUMPTIONS.md](ASSUMPTIONS.md).

## Limitations

See [LIMITATIONS.md](LIMITATIONS.md).

## Validation evidence

## Verification tolerance

Every number in an answer is checked against the engine before it is shown. A tagged number must equal the cited value's display string, or be that value correctly rounded to the printed precision and within 0.5% of it; an explicit sign must match. An untagged number must be a context number (a tool argument, tenor, shock size, hedge ratio, horizon or date). One failure blocks the answer.

Implemented in `tenorwise/agent/verifier.py`; the same text is returned with every AI answer (`verification_rule`) and shown in the interface. Verification proves each number came from the engine and was copied correctly, not that the sentence around it is right.

## Human review procedure
