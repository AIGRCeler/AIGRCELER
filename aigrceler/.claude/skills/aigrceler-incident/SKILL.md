---
name: aigrceler-incident
description: "Handle an AI incident: classify, start the response clock, notify, contain, report to authorities when required, close with a retrospective that feeds the catalog."
---

# AIGRCeler incident

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Steps

1. **Open** (Guardian): `aig incident open --title ... --severity low|medium|high|critical --description ... --controls ... [--reportable]`. Run it without `--by`: the journal then says AIGRCeler opened it, which is true, and AI Governance is told at once with their options (confirm only, or confirm and decide on a temporary measure). Use `--by <id> --statement "<their words>"` only when AI Governance asked you to open it; the engine refuses a named person's incident without their words. Describe facts, not conclusions: write what happened and what was found, and "whether this is unlawful or discriminatory is for counsel", never the conclusion itself (operating rule 14). Severity guide: critical = serious harm or legal reporting likely; high = significant harm to people or major business impact; medium = contained error with some impact; low = minor, no harm. When unsure, pick the higher.
2. **Clock**: AI Governance and the response owner must be told within 1 hour (critical), 4 hours (high), 1 business day (medium), 5 business days (low). Provisional; adjust in `data/workspace.json` with AI Governance's agreement. `aig incident clocks`.
3. **Notify** (Envoy): `aig incident escalate --id INC-0xx --to <people>`. AI Governance confirms: `aig incident ack --id INC-0xx --by <id>`.
4. **Contain**: AI Governance decides stopgaps (`aig containment add --title ... --ends <date> --request REQ-xxx --by <id> --statement "..."`). The measure is decided, not yet in place: when the owner says it is, `aig containment confirm --id CT-xxx --source "<who said it>"`. Until then say "asked", never "done". The circuit-breaker control DO-09 is how a system is stopped quickly.
5. **Obligations**: for each regulator or customer notice add `aig obligation add --title ... --authority ... --due ...`; close with `obligation close --note`.
6. **Update**: `aig incident update --id ... --note "..."` with facts only.
7. **Close** (AI Governance): `aig incident close --id ... --by <id> --statement "..." --retrospective "<what happened, why, what changes>" --outcome "..." --lesson "<what the catalog should learn>"`. Open obligations block closure. The lesson becomes a catalog proposal.
8. Herald writes the lessons-learned note (EA-10) and, if a control failed, proposes the change.
