# AIGRCeler v2 architecture

## Idea in one paragraph

AI Governance (a person or a small group at the company) runs AIGRCeler to govern each AI system. AIGRCeler drafts controls, asks the people who own them for proof, checks the proof, re-scores risk and keeps the record. Owners implement. AI Governance approves and finalizes, and never implements. Scripts own all state.

## Two levels

- **Workspace** = the company's engagement. It holds the control catalog, roles, people directory, risk-acceptance thresholds, company-level risks, the AI principles statement, the import-format registry and the company-level decision journal.
- **Project** = one AI system. It holds that system's controls, risks, evidence, incidents, decision journal and one folder per person.

## Who does what

| Who | Does | Never |
|---|---|---|
| AI Governance | Approves and finalizes controls, owns the catalog, starts stages, decides lanes, overrules findings, accepts risks within its threshold, grants exceptions | Implements a control (only as a recorded exception) |
| Owners (people in roles) | Implement, send proof | Approve their own control |
| Executive leadership | Accepts the highest residual risks | |
| AIGRCeler (agents and engine) | Drafts, requests, analyzes, scores, records | Approves a control, accepts risk, starts a stage |

## Seven areas (what is governed)

Governance and organization (GO), Data (DG), Model, built or adapted in-house (MD), Third party (TP), Deployment and operations (DO), Human oversight and rights (HR), Evidence and audit (EA). Model and third-party controls switch on or off by sourcing mode.

## Sourcing modes

Built in-house; adapted from a third-party base; third-party service; self-hosted open-source; embedded in a vendor product.

## Four stages (when the work happens)

DISCOVER, ASSESS, GOVERN, OPERATE. The first three run in order and close at a gate. OPERATE starts by an AI Governance decision once Govern has closed, and it never closes: from the day a control is assigned it moves on its own (assigned, evidenced, verified, monitored), and two ways of working run side by side inside it, Prove (owners deliver, someone else verifies, credit) and Watch (indicators, expiry, incidents, obligations, temporary measures). The go decision is an event recorded by AI Governance (`operate signoff`), not a stage; reviews are a recurring activity on a schedule, not a stage. The words ASSURE, MONITOR and REVIEW from earlier versions are still accepted and mean OPERATE; project records made by earlier versions are read as four stages without changing the journal. A stage starts only by an AI Governance decision, per system, in their own words, and Discover, Assess and Govern close only when the gate passes. The light lane runs the first three as one pass. A stage block (a possible legal hard stop) lets Discover and Assess start and run, because that is where the facts are found and the risks rated, but holds Assess from closing and every later stage from starting until AI Governance lifts it with a reason in their own words; closing over a block is not possible.

Assess leaves four things behind besides the ratings, and its gate checks them: every concern carried into Assess is rated, explained or passed on to a later stage on purpose with a reason; the specialist assessments the system's facts point to (fairness analysis, rights impact, data-protection impact, a read of its documents, an affected-people view) are each recorded as done, planned under a control, or not needed (a named person says so for rights and data protection, in their own words); risks specific to the system are added with `risk add`; and `risk gaps` lists each High and Critical risk with the controls that would address it, so Govern starts from a list. The number of standard scenarios opened depends on the system (a catalog of 32, each with its own rule for sourcing mode and facts).

DISCOVER gathers a structured discovery profile (77 questions in eleven sections, depth by lane, every answer with its source). Answers feed the factors, the screening, the risk scenarios (unknowns start one step worse) and the choice of controls. A cap of 20 percent on unknown answers keeps the record honest. The regulatory map (ISO/IEC 42001, EU AI Act, NIST AI RMF) connects every item to controls, product mechanisms and profile questions.

## Views (generated, never edited)

1. Area by control state (the AI Governance status screen, with evidence strength).
2. Area by role (the accountability matrix).
3. Area by stage (framework coverage checks).
4. Trust property by control state.
Plus: risk view, "what is waiting" view, decision journal table, per-person timeline, launch-status feed.

## Dashboard (generated, one fixed template)

`dashboard/index.html` at the company root shows every AI system on one page and each system in full: stages and the go decision, controls by area and state, risk before and after controls, evidence and its fingerprints, incidents and indicators, review dates, who owes what, discovery progress, the regulatory view and the recent decisions. It is built by the engine (`dashboard build`, and automatically after any change) from a template that ships inside `.claude\shared\templates\dashboard\`. The page shape is part of the framework and changes only when the template is changed and its version raised; a company's records stay outside `.claude\`, so updating the framework gives the new look to the existing data. It only reads, works offline in any browser, and is rebuilt from the records at any time. It is not a source of truth, a certification or legal advice.

## Folder layout

```
<workspace>/
  .claude/             agents, skills, engine, templates
  CLAUDE.md
  00-status/           roll-up views across systems
  catalog/             current/<area>/, versions/, proposals/
  decisions/           company journal.jsonl and texts/
  data/                script-owned records (roles, people, thresholds, scenarios, ...)
  projects/<system>/
    00-status/  controls/<area>/  evidence/  incidents/  decisions/
    people/<person>/{to-person,from-person}/  working-papers/  logs/  data/
```

## Agents

Genesis (orchestrate), Atlas (discover), Meridian (rate), Curator (curate), Envoy (engage), Verifier (verify), Guardian (watch), Warden (audit), Herald (improve), Prism and Auditor on call. Separate agents give role discipline and a clear audit trail; they run on the same model, so they are not independent assurance.
