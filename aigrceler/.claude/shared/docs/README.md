# AIGRCeler v2

An AI-governance framework for small and medium companies, delivered as Claude Code agents, skills and a small engine.

## The delivery has three items, the same as before

```
<company root>\
  .claude\          the framework: agents, skills, engine, catalog, templates, methodology
  CLAUDE.md         operating rules
  aigrceler.ps1     the menu: pick an AI system, work at company level, or add a system
```

Copy those three into a company's root folder and run `powershell -ExecutionPolicy Bypass -File aigrceler.ps1`. The first run sets up the company. The company's records are created next to them (`data\`, `catalog\`, `decisions\`, `00-status\`, `projects\<AI system>\`) and are never inside `.claude\`, so updating the framework means replacing `.claude\` and `CLAUDE.md` and nothing else.

Each AI system gets its own folder under `projects\`, and the menu links the company's one `.claude\` into it (a junction), so Claude Code started there has every agent and skill. Started in a system's folder, the engine knows which system is meant.

## What AIGRCeler does

- **AI Governance approves, owners implement.** AIGRCeler drafts controls, asks the people who own them for proof, checks the proof, re-scores risk and keeps the record. It never approves a control or accepts risk.
- **A control catalog the company owns.** 104 starter controls across seven areas, each with acceptance criteria, evidence types, legal references (indicative), trust-property tags and a playbook of suggested tools.
- **Everything is sorted.** Controls, decisions, evidence, working papers and logs each have a folder; controls sit by area; each person has a folder per system; status views are generated.
- **Defensible record.** One line per decision in an append-only, hash-chained journal; evidence fingerprinted at intake; findings with reasons.
- **Risk you can explain.** Inherent and residual risk by scenario; only verified controls earn credit, scaled by evidence strength; expiry on time or on a model-version change.
- **Lanes.** A light lane for low-risk systems; standard and full for the rest.
- **Scripts own the state.** The engine (Python standard library only) writes every record. Agents cannot hand-edit status.

## Inside `.claude\`

| Folder | What it is |
|---|---|
| `agents\` | 11 agents (Genesis, Atlas, Meridian, Curator, Envoy, Verifier, Guardian, Warden, Herald, Prism, Auditor) |
| `skills\` | 11 stage and process skills |
| `shared\engine\` | The engine (`py -3 .claude\shared\engine\aigrceler.py`) |
| `shared\catalog\` | Starter control catalog, risk scenarios, import formats |
| `shared\methodology\` | Architecture, lifecycle, risk method, evidence and journal, lanes, decision policy, coverage map, open items, command list |
| `shared\templates\` | Plain-words templates |
| `shared\docs\` | This file and INSTALL |
| `shared\testing\selftest.py` | Self-test |
| `shared\regulatory-mappings\` | Generated from the regulatory map: ISO/IEC 42001, EU AI Act, NIST AI RMF |

## Try it

From the company root (or any folder holding `.claude\`):

```
py -3 .claude\shared\testing\selftest.py
```

It builds a throw-away demo company in a temp folder, runs a complete lifecycle for a customer-facing chatbot (including red-teaming) and checks the rules that matter. It writes nothing else.
