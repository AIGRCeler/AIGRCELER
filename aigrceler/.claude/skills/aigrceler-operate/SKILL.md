---
name: aigrceler-operate
description: "OPERATE stage: the fourth and last stage. Every control is proved and watched on its own, owners are chased, AI Governance records the go decision, and the system is reviewed on a schedule. Start here after Govern closes."
---

# AIGRCeler Operate

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Operate is not a room to pass through. It is how the AI system is run once the controls are chosen and assigned. It never closes. Each control lives its own life from the day it is assigned, and two ways of working run side by side inside it:

- **Prove** (skill `aigrceler-prove`): is each control proved? Owners deliver, someone else verifies, credit appears only for verified controls.
- **Watch** (skill `aigrceler-watch`): is the AI system still within tolerance? Indicators, expiry, incidents with response clocks, obligations and temporary measures. Incidents have their own skill (`aigrceler-incident`).

Review (skill `aigrceler-review`) is a recurring activity of Operate, on a schedule, not a stage.

## Steps

1. Only AI Governance starts Operate, once Govern has closed: `aig stage start --stage OPERATE --by <id> --statement "..."`. The word ASSURE, MONITOR or REVIEW still works and means OPERATE.
2. Every control gets an owner and a due date at assignment. With no date given, the date follows how much the control matters: critical 14 days, required before launch 21, others 60. Move one with `aig control set-due --id <control> --due YYYY-MM-DD --why "..."`.
3. Chase. `aig operate chase` (or `--person <id>`) lists, from the records only, what is owed, by whom, how late, and the next step. It separates three kinds of waiting: on us (a message to write, or written but not marked sent), on a verifier, and on owners. It writes `00-status/7-chase-list.md`. Run it at least weekly and before every review. It sends nothing: AIGRCeler cannot send; a message counts as sent only when a person says so (`aig control mark-sent`).
4. When evidence expires, the chase list says so and why. Ask the owner again with a new request.
5. Readiness. `aig operate readiness` shows, live, how many required controls are verified (every critical or launch-required control that applies) and any high or critical incident still open.
6. The go decision. `aig operate signoff --by <AI Governance person> --statement "<their words>"`. It is an event, not a stage: it can be recorded at any time and more than once. If something still stands in the way, the decision-maker must give their reasons in their own words (a full sentence or two); the open items are written into the journal line and kept as a concern until dealt with. Never write the words for them.
7. Reviews. `aig review due` shows when the next is due; `aig review schedule --days N --by <id> --statement "..."` sets how often (default by lane: full 90, standard 180, light 365 days). A closed high or critical incident also calls for a review.

## What stays the same

Authority, the journal, evidence strength, the rule that the person who owns a control or sent its evidence cannot verify it, risk acceptance levels, and the rule that AIGRCeler writes things for people but never sends them.
