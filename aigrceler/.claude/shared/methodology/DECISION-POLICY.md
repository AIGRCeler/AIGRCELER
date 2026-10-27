# Decision policy v2: decide, do not ask

Before asking anyone anything, classify it.

**Class A: authority.** Reserved to a named person. Never done by the tool. Batch everything one person must decide into one ready-to-read message, with a recommendation and the exact outcome of each answer.
Examples: approve controls (in their own words); verify a document or statement as evidence; start a stage; confirm or change a lane; accept residual risk; overrule a finding; approve or decline a catalog proposal; release a catalog version; waive or retire a control; grant an exception; close an incident; start containment.

**Class B: analysis or judgment.** The agent decides, records the reason and how to reverse it, and reports afterward.
Examples: choosing the verdict on a piece of evidence; how to rate a scenario; which owner role fits a control; wording a message; what to put in a retrospective.

**Class C: routing and file mechanics.** Just do it.
Examples: regenerating views, filing a reply, running the gate, running the expiry check.

## Rules

1. Never end a turn with "do you want me to...?" about work inside the current stage. Do it and report.
2. Ask only if the step is irreversible or external, needs authority you cannot hold, needs a fact only a human has, or is truly ambiguous with material impact.
3. After AI Governance starts a stage, run it straight through until you need a person. Then give one batched message per person and stop.
4. Close Discover, Assess and Govern with `stage gate` then `stage close`. Operate never closes; the go decision is `operate signoff`, in the decision-maker's own words. Only AI Governance starts a stage.
5. Never write a person's own words and record them as theirs. A decision's `--statement` is what the decision-maker wrote or said in this conversation, verbatim. If they only said "yes", record "yes" and what it referred to.
6. Who is speaking: unless told otherwise, the person in the conversation is the AI Governance lead. If they say they are someone else, use that person's id; the engine checks their role.
7. Each person records their own decision. A risk acceptance, an approval, an exception or a waiver is never entered on someone else's behalf; if two people must decide, each runs the command with their own `--by` and words. Exceptions have an end date and name what they cover.
8. If the engine refuses, report the refusal in plain words. Never work around a refusal by editing a file.
