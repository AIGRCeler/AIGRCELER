---
name: aigrceler-assess
description: "ASSESS stage: open the standard risk scenarios for a system, rate each with reasons, add risks specific to the system, answer which specialist assessments it needs, deal with every concern carried in, and show which controls Govern should draft. Produces inherent risk by dimension and the baseline for later credit."
---

# AIGRCeler Assess

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Say what could go wrong before any control is counted, and say what is still unknown, what other assessments the system needs, and where each one stands. Assess does not design controls (Govern does) and does not do the specialist assessments itself; it makes sure none is silently skipped.

## What Assess must leave behind

1. Every risk scenario rated, with reasons that rest on discovery facts.
2. Risks specific to this system added to the list.
3. Every concern carried into Assess dealt with: rated as a risk, explained, or passed on to a later stage on purpose, with the reason.
4. An answer for each assessment the system may need: done, planned (under which control), or not needed (with a reason, and for rights and data-protection assessments a named person's own words).
5. A list of the High and Critical risks with the controls that would address them, and the risks no catalog control addresses.

The gate checks 1, 3 and 4. It does not close over any of them.

## Steps

1. AI Governance starts the stage (`aig stage start --stage ASSESS --by <id> --statement "..."`). It cannot start until DISCOVER is closed. The engine prints the concerns carried in from earlier stages (`aig concern list` shows them again), including each "not known after asking" from Discover.
2. Meridian: `aig risk init`. The standard scenarios that fit the system's sourcing mode and factors are opened. They cover six dimensions: accuracy, fairness, data quality, security and misuse, human oversight, regulatory and governance. The number differs per system. Scenarios that rest on something Discover could not find out start one step worse on likelihood, with the reason on screen. This is deliberate: not knowing is treated as a reason for care, not as good news.
3. Rate each one from the discovery record, not from memory: `aig profile for --scenario R-001` lists the facts Discover recorded for that scenario, with their sources, and the ones still unknown. Then `aig risk set --id R-001 --likelihood N --impact N --reason "..."`. 1 to 5 each, before controls. The reason names the facts it rests on and who said them; take the source from the record, never from memory. Use `aig risk set --all-defaults --reason "..."` only when the standard rating truly fits and say why. If a fact turns out to be findable after all, record it with `aig profile set` (the concern closes by itself) and the scenario can be re-rated.
4. Add what the standard list misses. Read the concerns and the discovery facts for harm specific to this system (a capacity limit, a particular dependency, a local rule) and add each: `aig risk add --title "..." --dimension accuracy|fairness|data|security|oversight|regulatory --likelihood N --impact N --reason "..." --like S-XXX-NN`. `--like` links standard scenarios whose controls should also count against it; add or change the link later with `aig risk set --id R-0xx --likelihood N --impact N --reason "..." --like S-XXX-NN` (only on risks added for this system). Always link the standard scenarios that fit, so Govern drafts the right controls for it. If the risk would help every company, also propose it to Curator (`aig catalog propose`).
5. Deal with every concern carried into Assess. For each one: if it is a risk, rate or add it and resolve the concern with a note naming the risk (`aig concern resolve --id CON-xxx --note "..."`); if it is not a risk, resolve it and say why; if it cannot be settled now, pass it on on purpose (`aig concern carry --id CON-xxx --to GOVERN --reason "..."`). A concern about an unknown fact closes by itself when someone answers the question. A recorded concern cannot be edited; if its source is wrong, resolve it and say in the note what the correct source is.
6. Answer the assessment list: `aig assess show` lists the specialist assessments that fit this system's facts (fairness analysis, rights impact, data-protection impact, a read of the system's documents, an affected-people view), with the helper for each (Prism, Auditor, Verifier). The list says which fit; it never says what the law requires (operating rule 14). For each one record where it stands: `aig assess item --item fairness|rights|dpia|docs|affected --status done|planned|not-needed --note "..."`. Planned means a control will carry it (the engine names it). "Not needed" for rights or data protection is for a named person in AI Governance to say, in their own words, after counsel's view if there is one (`--by <id> --statement "<their words>"`); never record it yourself. Auditor writes the affected-people note for any system that decides about people.
7. Company-level risks go to the workspace: `aig orgrisk add`.
8. If a stage block is in force, send at once the requests for the evidence that AI Governance said would lift it (to the vendor contact, the owner, counsel) and say who was asked (operating rule 13). The block holds Assess from closing; it does not hold the rating.
9. `aig risk recompute`, read `00-status/5-risk.md`, run `aig risk gaps` and show AI Governance the High and Critical risks with the controls that would address them, and any risk with no catalog control. Then `aig stage gate --stage ASSESS` and, when AI Governance decides, `aig stage close --stage ASSESS`.

## Reading the score

Inherent and residual are scores out of 100 by six dimensions (20, 20, 15, 15, 15, 15), shown with the Green, Yellow, Orange, Red bands. Before any control is verified the residual score equals the inherent score; that is normal. Every move has a reason on screen.

## Closing over open items

If AI Governance wants to close Assess while the gate lists something, that is an informed override (operating rule 12): list exactly what stays open and why it matters, recommend against it where it affects people or the law, and ask for their confirming reason in their own words. Say what the reply must cover; never offer a sample sentence. A stage block cannot be closed over.
