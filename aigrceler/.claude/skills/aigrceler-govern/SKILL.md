---
name: aigrceler-govern
description: "GOVERN stage: draft the controls for a system from the catalog, get AI Governance's approval, confirm owners and send one message per person."
---

# AIGRCeler Govern

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Decide which controls apply, who owns each, and get the work requested. AI Governance approves; owners implement; AIGRCeler tracks and verifies.

## Steps

1. AI Governance starts the stage (`aig stage start --stage GOVERN ...`). Closing ASSESS first is required.
2. Curator: `aig control draft`. Controls are chosen by sourcing mode, lane and factors (for a customer-facing generative system that includes red-teaming, prompt-injection tests, output filtering and disclosure). Read the whole output: if it says the company's catalog is missing controls the product now ships with, tell AI Governance in the same turn, name the controls, and recommend adding them (`aig catalog sync-starter --by <id> --statement "<their words>"`, their decision); after they say yes, run `aig control draft` again so the new controls are drafted. Do not take the drafted set to approval before they have decided.
   Check what Assess left for Govern: `aig assess show` (each planned assessment must have a control on this system that carries it; the gate refuses otherwise, and `assess item` records the right controls for a purchased system, which are not the controls for one built in house), the concerns carried into Govern (`aig concern list`: one says what a lifted block was lifted over), and `aig risk gaps` (High and Critical risks with no catalog control need a system-specific answer: tailor a related control with `aig control tailor`, ask Curator to propose a new catalog control, or have the risk accepted by the right person in their own words).
3. Genesis prepares the approval package. AI Governance approves in one batch: `aig control approve --all-drafted --by <id> --statement "<their words>"`. They can decline individual drafts (`aig control decline`). Critical controls are marked.
4. Confirm owners with the company. The owner is a person who holds the control's role. Never AI Governance (a recorded exception is the only way). Every number you report about who owns how many controls comes from `aig control owners`, never from your own count; it also flags people who hold an AI Governance role and the people who would carry more than they can deliver. Never say what exceptions exist, who they cover or when they end from memory or from one file: `aig exception list` shows every exception (company-wide and for each system, with what each covers and when it ends), and a system's exception can share nothing with a company-wide one. Never claim there is none until you have run it.
5. Envoy assigns in batches so each person gets **one** message: `aig control assign --role <role> --owner <person> --due <date>` gives every approved, unassigned control of that role to that person. To split a role between people, name the controls instead: `aig control assign --ids HR-02,HR-03 --owner <person> --due <date>`, then assign the rest. Check `aig control owners` against what AI Governance decided before telling anyone the messages are ready. To move a control that already has an owner, run `aig control assign --ids ... --owner <new person>`: the old message is withdrawn (moved to a `withdrawn` folder) and one new message goes to each person whose list changed; if the old message was already sent, tell that person by hand. The message appears in that person's folder under the system. Tell AI Governance where; they send it by email, chat or ticket; record it with `aig control mark-sent`.
6. For legal-mapped controls use the catalog's legal references as the traceability line when AI Governance asks "which law needs this?".
7. `aig stage gate --stage GOVERN`, then `aig stage close --stage GOVERN`.

## Gate in plain words

No draft controls left; every approved control has an owner; critical controls decided.

## Before Govern closes

Govern cannot close while a concern carried into it is open: settle it (`aig concern resolve` with a note) or pass it on to a later stage with the reason (`aig concern carry`). Say which messages are sent only from the waiting page or `aig request list`: each line says "marked as sent" or "not marked as sent yet". "Not marked" can mean the person has sent it and nobody has told you, so ask; never say none went out unless the records say so.

## Controls that look missing

Before saying a catalog control was left out by mistake, run `aig control applies --ids MD-04,EA-03`: it says whether the control is on the system and, if not, which fact keeps it off (for example, it is only for systems built or adapted in house). A control that applies to a different sourcing mode is not missing; if a card lists it as a dependency, the control that covers the same work for this system carries it. Raise a concern only when the engine says the control applies and is not there.

## Whose words

When you record a person's decision (`--statement`), use their own words, quoted from what they typed to you. If an action follows from something they already asked for (release the catalog after they asked for a control to be added), quote that request. Never write a statement yourself and record it under their name; if you have no words of theirs for a step, ask for them first.
