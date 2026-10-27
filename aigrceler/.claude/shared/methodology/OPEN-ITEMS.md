# Provisional settings and what to verify

| Setting | Value now | Where | Verify with |
|---|---|---|---|
| Risk points by dimension | 20/20/15/15/15/15 | RISK-METHOD.md, engine | Run on real systems; adjust if one dimension dominates |
| Scenario bands | Low 1-4, Medium 5-9, High 10-16, Critical 17-25 | `data/workspace.json` | Calibrate after first assessments |
| Credit strengths | strong 1, moderate 1/2, weak 0 | engine | A regulator's view of "moderate" |
| Retention | full 10, standard 7, light 5 years | `data/workspace.json` | Counsel, per sector and jurisdiction |
| Incident clocks | critical 1h, high 4h, medium 1 business day, low 5 business days | `data/workspace.json` | Counsel; regulator notice periods are separate obligations |
| Lane rules | hard and soft factors in LANES.md | `projmod.py` | First real screenings |
| Evidence validity (days) | per control | catalog | Your own change rate |
| Legal mappings | indicative | catalog `legal` field, generated from `catalog/regulatory-map.json` | Counsel |
| Use of ISO clause titles | the ISO map names clauses by number and short title only, with our own wording | `regulatory-mappings/ISO-42001.md` | Counsel: whether naming the clause titles needs ISO's permission |
| Unknown limit | 20 percent of required discovery questions | workspace setting `discovery_unknown_limit` | AI Governance |
| Critical discovery questions | 16 that decide tier, lane or a risk floor | `catalog/discovery-profile.json` | AI Governance |
| Starter catalog content | 104 controls | `shared/catalog/starter-catalog.json` | Adopt, then AI Governance edits |
| How requests reach people | folders today; email, chat, tickets by hand | Envoy | Choose a channel and add a connector later |
| Framework-side catalog upkeep | new starter versions are delivered as a new file; the company chooses what to adopt through proposals | -- | Decide the maintainer's process |
| Tool-only verification | A strong machine report can verify a control without a person; `check run` lists these for sampling | engine | AI Governance: sample a few each cycle, or require a person for all |
| Identity | `--by` is typed, not a login; the journal says `unsigned` | -- | Add signatures or a company login outside the framework if auditors require |
| Launch-status feed format | `launch-status.json` | engine | Your engineers |

None of these are legal advice. Where a number is a number a regulator will read, confirm it.
