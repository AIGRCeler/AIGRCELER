# How AIGRCeler v2 covers three outside governance architectures

Three outside designs were compared item by item (86 items). This is the short map.

| Outside idea | Where it lives in v2 |
|---|---|
| A: model inventory | GO-03, project attributes (purpose, data sources, techniques, evaluation measures, resources, dependencies) |
| A: risk assessments | ASSESS stage, 32 standard scenarios, risk view |
| A: data governance | Data area (DG-01 to DG-16): provenance, quality, representativeness, privacy, consent withdrawal, poisoning, leakage, retention |
| A: verification and validation | Model area (MD-01 to MD-16), evidence loop, red-teaming (MD-07), code and dependency scans (MD-08, MD-09) |
| A: monitoring and detection | Deployment and operations area, indicators, security monitoring (DO-03), explainability signals (DO-15), launch gate (DO-12) |
| B layer 1 data | Data area |
| B layer 2 model | Model area and Third-party area |
| B layer 3 system integration | DO-09 circuit breaker, DO-10 dependency map, DO-11 pipeline security, DO-14 agent action limits, HR-03 over-reliance |
| B layer 4 control and monitoring | Deployment and operations area, indicators, launch-status feed |
| B layer 5 audit and evidence | Evidence and audit area, decision journal with hash chain, fingerprints, retention by lane |
| B accountability matrix | View 2: area by role (generated) |
| C seven trustworthiness blocks | Trust-property tags on every control; view 4 |
| C ten essential components | Accountability (GO, journal), risk management (ASSESS), monitoring (DO), model governance (MD, TP), operating model (roles, lanes), people and culture (GO-02, GO-05, GO-06, GO-15), tools (playbooks, import registry), infrastructure (DO-11), stakeholder engagement (GO-15, HR-11) |
| C organizational view | Company-level risks, principles statement, context notes on each system |
| C hourglass model | Environmental (legal mapping, sector obligations), organizational (workspace), AI system (project) |

## Regulatory frameworks

A separate map (`catalog/regulatory-map.json`, readable in `shared/regulatory-mappings/`) lists every clause and Annex A item of ISO/IEC 42001:2023 (65), every provision of the EU AI Act the product touches (32 items, with the roles and classes each applies to), and every subcategory of the NIST AI RMF 1.0 (72). Each item names the controls, the product mechanisms and the Discover questions behind it. Completeness is tested against independent lists in the self-test. The legal tags on controls are generated from this map. Commands: `aig reg coverage`, `aig reg item --ref ...`, `aig reg project`.

What is not in the framework by design: the company's own deployment pipeline gate (the framework publishes launch-status; the company's engineers enforce it) and any tool the company chooses to run (the framework suggests, reads results, and does not run them).

The item-by-item trace is kept by the maintainer and is not part of the release.
