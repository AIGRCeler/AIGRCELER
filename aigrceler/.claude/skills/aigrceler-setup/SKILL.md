---
name: aigrceler-setup
description: "Sets up a company workspace: names AI Governance, adds people and roles, adopts the starter control catalog. Use once per company, or when people or roles change."
---

# AIGRCeler setup

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Purpose

Create the company workspace and make the first decisions that everything else rests on.

## Who decides

AI Governance (the person or group that runs AIGRCeler for the company and approves controls). It never implements controls.

## Steps

1. Ask in plain words: company name; who will act as AI Governance (a person or a small group, with a contact); on what authority (charter, board note, engagement letter).
2. Create the workspace: `aig ws init --company "..." --governance-name "..." --governance-contact "..." --basis "..."`.
3. Add the people who will own work and the role each holds: `aig person add --name ...`, then `aig role assign --person <id> --role <role> --by <ai-governance id> --basis "org chart"`. Default roles: AI Governance, legal and compliance, engineering and data science, security, operations, executive leadership. Edit with `aig role add` / `aig role set`. One person may hold several roles in a small company; AI Governance must not also own controls (record an exception if there is truly nobody else: `aig exception add`).
4. Adopt the starter catalog as the company's own: `aig catalog adopt-starter --by <id> --statement "<their words>"`. From then on AI Governance owns every change.
5. Agree who may accept which residual risk (default: AI Governance up to High, executive leadership for Critical): `aig ws thresholds-set` only if they want something different.
6. Write the AI principles statement with them (template: `.claude/shared/templates/ai-principles-starter.md`): `aig ws principles-set --by <id> --text "<their words>"`.
7. Record company-level risks if they know of any: `aig orgrisk add`.
8. `aig views regenerate`. Show them `00-status/`.

## Done when

`aig ws status` shows the catalog version, roles have people, and AI Governance can say in one sentence what they approve and what they never do.
