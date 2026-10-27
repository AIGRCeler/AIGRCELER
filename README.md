# AIGRCeler

An AI-governance framework for small and medium companies. It runs inside [Claude Code](https://claude.com/claude-code) as a team of agents and skills, and keeps a tamper-evident record of what your company decided about each of its AI systems.

AIGRCeler helps the people in a company who are responsible for AI (called **AI Governance** here) to find out which AI systems the company uses, rate their risk, put the right controls in place, collect proof that the controls work, and keep watching afterwards. The agents draft, ask, check, score and record. **People decide.** AIGRCeler never approves a control, accepts a risk or starts a stage on its own.

> AIGRCeler is a working tool, not legal advice. Read [DISCLAIMER.md](DISCLAIMER.md) before relying on any of it.

## How it works

Four stages for each AI system:

1. **Discover** - what the system is, what it does, who it affects, what data it uses.
2. **Assess** - how risky it is, and which controls it needs.
3. **Govern** - the controls are approved by AI Governance and given owners.
4. **Operate** - owners send proof, the proof is checked, risk is re-scored, incidents are handled. Operate never closes, because governing a live system never ends.

What you get:

- 11 agents and 11 skills for Claude Code that lead each stage and write to the people involved in plain business words.
- An engine written in Python's standard library only. It writes every record, so an agent cannot hand-edit a status.
- A starter catalog of 104 controls in seven areas, 32 risk scenarios and a 77-question discovery profile. The company owns its copy and changes it through proposals.
- Evidence that is fingerprinted when it arrives and expires on a date or when the model version changes. Only verified controls earn credit against risk.
- A decision journal that cannot be changed without detection, one line per decision, in the decision-maker's own words.
- A governance dashboard built by the engine from a fixed template.
- A map of where the controls meet ISO/IEC 42001, the EU AI Act and the NIST AI RMF 1.0. It shows where the controls help, and never says that a company complies.
- A self-test of the engine (hundreds of checks) that you can run yourself.

## Quick start

You need Windows with PowerShell, Python 3 and Claude Code.

1. Download the latest release zip from the Releases page (or copy the `aigrceler` folder of this repository).
2. Make a folder for your company, for example `C:\Clients\Acme\AIGRCeler`, and put the three items from the `aigrceler` folder into it: `.claude`, `CLAUDE.md` and `aigrceler.ps1`.
3. Run `powershell -ExecutionPolicy Bypass -File aigrceler.ps1`, name your company and the person who acts as AI Governance, then add your first AI system.
4. When Claude Code opens, say "start AIGRCeler".

The full steps, including how to check the download, are in [docs/INSTALL.md](docs/INSTALL.md). To move to a newer release, see [docs/UPGRADE.md](docs/UPGRADE.md).

## What is in this repository

| Path | What it is |
|---|---|
| `aigrceler/` | The product exactly as you install it: `.claude/`, `CLAUDE.md`, `aigrceler.ps1`. |
| `docs/` | Install and upgrade guides. |
| `CHANGELOG.md` | What changed in each release. |
| `VERSION` | The release this tree is. |
| `LICENSE` | Apache License 2.0. |
| `SECURITY.md`, `CONTRIBUTING.md`, `DISCLAIMER.md` | How to report a problem, how to take part, and what AIGRCeler is not. |

The product sits in a subfolder on purpose: a `CLAUDE.md` at the top of this repository would make Claude Code behave as AIGRCeler whenever someone opened the repository itself.

## Examples

Worked examples are in a separate repository: **[AIGRCeler-Examples](https://github.com/AIGRCeler/AIGRCeler-Examples)**.

**Why they exist.** A governance framework is hard to judge from a list of features. The examples let you see what AIGRCeler does with a realistic company before you put your own company into it: what the agents ask, which AI systems and risks come up, which controls are chosen, what evidence is requested, and what the records look like afterwards. Each example is a fictional company with its AI systems, a test case for each system, and the records produced when AIGRCeler was run on it. You can read one, or continue it yourself.

**What to keep in mind.**

- Every company, person and result in the examples is invented. None of it is real data, and none of it is advice about your company.
- They are a separate repository so that this one stays small and holds only what you install. Examples have no versions or releases of their own, and they can lag behind the latest release of the product.
- Nothing in the examples is needed to install or run AIGRCeler.

## Website, videos and news

- Website: [www.aigrceler.com](https://www.aigrceler.com)
- Videos: [AIGRCeler on YouTube](https://www.youtube.com/@AIGRCeler)
- News: [AIGRCeler on LinkedIn](https://www.linkedin.com/company/aigrceler)

## Support

This is a project with one maintainer. The latest release is the supported one. Questions and problems go in the issue tracker; there is no promised response time. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first and [SECURITY.md](SECURITY.md) for anything about security.

## Licence and owner

Copyright 2026 H&G Tech Inc, Ontario, Canada. Licensed under the Apache License 2.0, see [LICENSE](LICENSE). The licence covers the software; it does not give a right to use the AIGRCeler name or logo (see [DISCLAIMER.md](DISCLAIMER.md)).

Several settings (retention periods, incident clocks, risk bands, evidence validity, lane rules, legal mappings) are starting values that must be checked for your company; the list is in `aigrceler/.claude/shared/methodology/OPEN-ITEMS.md`.
