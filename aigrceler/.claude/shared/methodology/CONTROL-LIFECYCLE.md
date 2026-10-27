# Control lifecycle

States: **drafted, approved, assigned, implementing, evidenced, verified, monitored.** Side states: **rejected, waived, retired, expired.**

| Step | Who | Command |
|---|---|---|
| Drafted | Curator | `control draft` |
| Approved | AI Governance | `control approve` (one batch decision in the journal) |
| Assigned | Envoy | `control assign` (one message per person) |
| Implementing | Owner | (starts when work starts; `control state --to implementing`) |
| Evidenced | Owner sends proof | `evidence intake` |
| Verified | Verifier on strong machine reports; a named reviewer in AI Governance for documents and statements (AI Governance may overrule) | `finding record` / `finding overrule` |
| Monitored | Guardian | `indicator set` |
| Expired | Automatic | `evidence expire-check`, or a model version change |
| Rejected | Verifier finding "not satisfied" | back to implementing with reasons |
| Waived | AI Governance | `control waive` (critical controls need an end date) |
| Retired | AI Governance | `control retire` |

## Never allowed

AI Governance owning a control (unless a recorded exception); an owner approving or judging their own control; AIGRCeler approving a control or accepting risk; a state change by hand.

## Pinned versions

A control is a catalog definition pinned to the version AI Governance approved. A catalog change does not alter existing controls. `catalog impact` lists who is affected; `control upgrade` is an AI Governance decision, and a verified control moves back to "evidenced" so it is verified again against the new text.

## Dependencies

A definition may depend on others (for example the post-market plan depends on production monitoring). If a control depends on one not yet verified, the status view warns. In this version it has no effect on scores.

## Statement-only evidence

A statement alone leaves a control at "evidenced". AI Governance can overrule with their own recorded reason; the credit it earns is still none.
