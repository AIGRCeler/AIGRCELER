---
name: aigrceler-prove
description: "Prove lane of OPERATE: owners put controls in place and send proof; Verifier checks it; risk credit appears only for verified controls. Works control by control, with no stage to close."
---

# AIGRCeler Prove

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Prove that controls really exist. Owners do the work. AIGRCeler requests, receives, verifies and records. This is one of two ways of working inside the OPERATE stage (the other is Watch, skill `aigrceler-watch`). Each control is proved on its own timetable; nothing waits for the others.

## Steps

1. Operate has started (`aig stage start --stage OPERATE ...`, AI Governance only). Every control has an owner and a due date.
2. Envoy keeps owners moving: `aig operate chase` shows what is owed, by whom, how late, and the next step. Write what is missing; AIGRCeler cannot send, so say "written, not sent" and let the person send it and report it (`aig control mark-sent`). Answer questions and file replies with `aig request answer`.
3. Verifier works the evidence loop (see the `aigrceler-evidence-loop` skill): intake, finding, follow-up, repeat. Name the request each file answers (`--request`).
4. Meridian reads the risk view after every finding. Credit appears only for verified controls.
5. Waivers: only AI Governance, with a reason and an end date for critical controls: `aig control waive`.
6. Readiness is live: `aig operate readiness`. `aig views launch-status` writes `00-status/launch-status.json` so the company's own release process can check it (control DO-12). The framework publishes; the company's engineers enforce.
7. The go decision is recorded with `aig operate signoff` (see the `aigrceler-operate` skill). It is not a stage close.

## Evidence strength

Strong: a tool report tied to the model version. Moderate: a document a person produced, dated. Weak: a statement. Weak never verifies a control on its own.
