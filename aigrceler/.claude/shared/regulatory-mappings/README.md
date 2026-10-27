# Regulatory mappings

This is AIGRCeler's own mapping of where each requirement is met. It is not legal advice, it is not a statement that the company complies, and it is not a certification. Whether a duty applies to a given system is a question for counsel; certification is decided by an accredited body.

These documents are generated from `shared/catalog/regulatory-map.json`, the same data the engine reads.

Each row says where the requirement is met: by which control of the catalog (and the lane that brings it in), by which part of how AIGRCeler works (for example the journal, the gate or the approval rules), and which Discover questions supply the facts. Per system, `aig reg project` shows the same table with the state of that system's controls, and `aig reg coverage` lists what is not fully covered.

| Framework | Document | Items | Covered | Partly | Not covered |
|---|---|---|---|---|---|
| ISO/IEC 42001:2023 | [ISO-42001.md](ISO-42001.md) | 65 | 62 | 3 | 0 |
| EU AI Act (Regulation (EU) 2024/1689) | [EU-AI-Act.md](EU-AI-Act.md) | 32 | 30 | 2 | 0 |
| NIST AI Risk Management Framework 1.0 | [NIST-AI-RMF.md](NIST-AI-RMF.md) | 72 | 66 | 6 | 0 |

## What is only partly covered

Partly covered means the product supplies part of what the item asks for and the rest depends on the company's own work or on a decision for counsel.

- ISO 42001 A.4.4 (partial): Tools are suggested in playbooks and their use is recorded as evidence. AIGRCeler does not inventory the company's tools itself.
- ISO 42001 A.4.5 (partial): Recovery and dependencies are covered; capacity planning is the company's own engineering practice and is only recorded, not checked.
- ISO 42001 A.10.4 (partial): Information for customers who receive the company's AI output is covered; responsibilities written into customer contracts are the company's legal work and are recorded only as evidence.
- EU AI Act Art. 17 (partial): Covers accountability, risk management, data management, testing, record-keeping, change control and post-market monitoring. Not covered by the starter catalog: the list of harmonised standards applied, and written communication procedures with national authorities beyond incident and regulator readiness. Counsel decides what the company's QMS document must contain.
- EU AI Act Art. 51-55 (partial): Covers the company as a user of a general-purpose model: it obtains the provider's documentation (TP-14). The duties of the provider of such a model are out of the starter catalog's scope; a company that itself places a general-purpose model on the market needs its own legal plan.
- NIST AI RMF GOVERN 3.1 (partial): Roles bring several functions to each system, and affected people are heard (GO-15). The make-up of the company's teams is the company's own matter and is not measured.
- NIST AI RMF GOVERN 4.1 (partial): Principles, training and screen design support it; culture itself is not something a control can prove.
- NIST AI RMF MEASURE 1.3 (partial): Independent assessment is recommended in red-teaming and the yearly audit, and recorded, but not enforced; AIGRCeler agents are not independent of each other.
- NIST AI RMF MEASURE 2.2 (partial): Covered only for usability and accessibility testing with people; formal human-subject protection review is the company's own process.
- NIST AI RMF MEASURE 2.12 (partial): Considered in the impact assessment; energy and emissions are not measured by AIGRCeler.
- NIST AI RMF MEASURE 4.2 (partial): Owners and reviewers supply domain knowledge; there is no check that a domain expert reviewed each result.

## Reading the EU AI Act table

Each EU item says which roles (provider, deployer, importer, distributor) and which classes (prohibited, high-risk, limited, minimal, general-purpose model) it is relevant to. Whether a system is in a class, and which duties apply to the company, are questions for counsel (operating rule 14). Discover records what the company says; `aig reg project` shows where the controls would meet each item if it applies.
