# AIGRCeler v2 agents

Eleven agents, one verb each. Separate agents give role discipline and a clear audit trail. They run on the same model, so they are not independent assurance.

| Agent | Verb | Touches |
|---|---|---|
| Genesis | Orchestrate | Decision packages, stage and lane rules, relays decisions to the engine |
| Atlas | Discover | Systems, screening, tier, lane (absorbs Echo and Triage) |
| Meridian | Rate | Risks, scenarios, inherent and residual, company-level risks |
| Curator | Curate | Control drafts per system, catalog proposals, playbooks |
| Envoy | Engage | Requests, person folders, chasing, incident notices |
| Verifier | Verify | Evidence intake and findings |
| Guardian | Watch | Indicators, expiry, incidents and response clocks (absorbs Monitor) |
| Warden | Audit | Authority, conflicts, journal chain, exceptions |
| Herald | Improve | Reviews, retrospectives, recommendations that become catalog proposals |
| Prism | On call | Fairness, robustness, explainability analysis |
| Auditor | On call | Rights, data protection, EU AI Act classification (absorbs Advocate) |

Retired as agents: Archivist (now scripts in the engine), Responder (owners implement; notices go through Envoy), Echo, Triage, Monitor, Advocate.
