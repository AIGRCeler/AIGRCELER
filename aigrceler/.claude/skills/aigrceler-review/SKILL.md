---
name: aigrceler-review
description: "Recurring review inside OPERATE: periodic and post-incident review of one AI system from its records, on a schedule. Not a stage."
---

# AIGRCeler Review

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Look back at one AI system from its records and say what holds. A review is something done on a schedule or after an incident; it is not a stage and nothing closes when it ends.

## Steps

1. When: `aig review due` shows the date. AI Governance sets the rhythm with `aig review schedule --days N --by <id> --statement "..."`; the default follows the lane (full 90, standard 180, light 365 days). A closed high or critical incident also calls for one.
2. Herald reads only the records, not memory of earlier conversations: `aig operate chase`, `aig operate readiness`, the status views, findings, overruled findings, incidents, late requests, expiries, acceptances and their end dates, obligations and the journal.
3. Herald writes the review and says what is verified, what has lapsed, what is accepted and until when, what is still open, and what each dated obligation needs. A review that is read first writes nothing until the decision-maker says to record it.
4. Warden checks the record: `aig check run`. To show the check works, copy the journal somewhere outside the records, change one line in the copy, and show it is noticed; never touch the real journal.
5. The decision-maker records the review: `aig review add --kind periodic|post-incident|audit --summary "..."`. The next date is shown.
6. The yearly audit control (EA-05) brings in outside eyes.

Catalog improvement across companies is not part of a review. Lessons stay in the project's own records.
