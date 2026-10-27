---
name: aigrceler-catalog
description: "Manage the control catalog: AI Governance owns it. Use to propose, approve, version, retire or check legal coverage of controls."
---

# AIGRCeler catalog

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## Principles

- The catalog lives in the workspace (`catalog/current/<area>/`). The company adopted the starter and owns it.
- Every change begins as a **proposal**: `aig catalog propose --kind add|edit|retire|review --id ... --reason ... --source ... --ref ...`. Anyone may propose, including AIGRCeler. Only AI Governance decides.
- Approving applies the change and raises the control's own version; releasing snapshots a new catalog version. Systems keep the version they were approved under; `aig catalog impact --id X` lists which systems a change touches.
- A control with a legal mapping needs a written reason to edit or retire. `aig catalog coverage` shows what legal references are covered; the engine warns when a change leaves one uncovered.
- Proposals arrive from: reviews, audits, incidents, overruled findings, regulatory changes, AI Governance.

## A control definition has

An ID with area prefix, title, trust properties, objective, requirement, legal references (indicative, not advice), where it applies (sourcing modes, lanes, factors), the risk scenarios it addresses, type, most risk steps it can remove, critical or not, acceptance criteria, evidence types, how long evidence stays valid, default owner role, dependencies, and a playbook (suggested tools, a how-to, accepted evidence formats). Write requirement, objective and acceptance criteria in plain words an owner can act on.
