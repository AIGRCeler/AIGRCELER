---
name: aigrceler-watch
description: "Watch lane of OPERATE: indicators on verified controls, expiry of evidence, incidents with response clocks, obligations and containment. Runs all the time, with no stage to close."
---

# AIGRCeler Watch

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Keep what was proven true, and notice quickly when it stops being true. This is one of two ways of working inside the OPERATE stage (the other is Prove, skill `aigrceler-prove`). It works at two levels: a control's own indicator and evidence expiry, and the whole system (incidents, obligations, temporary measures, the risk score and its acceptances).

## Steps

1. Guardian: `aig indicator set` for controls that can drift (accuracy, fairness, red-team success rate, access reviews). Feed readings with `aig indicator update`. Out of tolerance suspends that control's credit and prompts the incident question.
2. Run `aig evidence expire-check` weekly. An expired control goes back to its owner: the chase list (`aig operate chase`) says why and what to ask.
3. Incidents: see the `aigrceler-incident` skill.
4. Model or vendor changes: `aig project set --model-version <new>` expires old evidence tied to the old version and asks for new. Treat it as a material change and re-assess.
5. Obligations and temporary measures: `aig obligation add`, `aig containment add`. Say plainly which are reported and which are checked.
6. There is no monitor gate. What is wrong right now shows on the waiting page and the chase list; the go decision (`aig operate signoff`) looks at the required controls and open high incidents.
