---
name: aigrceler-evidence-loop
description: "The loop that runs through OPERATE (Prove and Watch): request, receive, verify, follow up, re-score. Use whenever a person sends something back."
---

# AIGRCeler evidence loop

`aig` means `py -3 .claude/shared/engine/aigrceler.py`. Add `-p <system>` to commands about one AI system.

## The loop

1. **Request** (Envoy): a message in the person's folder; AI Governance sends it.
2. **Receive** (Envoy): file the reply with `aig request answer --id REQ-0xx --file ...`.
3. **Register** (Verifier): `aig evidence intake --control <id> --file ... --kind report|document|statement --tool ... --tool-version ... --model-version ... --period ... --submitted-by <person>`. The file is fingerprinted. Never edit evidence.
4. **Judge** (Verifier): read it against the acceptance criteria. `aig finding record --evidence EV-0xx --verdict satisfied|partly|not|cannot-tell --reasons "..." --gaps "..."`. Verifier may record any verdict on strong evidence and partly, not or cannot-tell on anything. A "satisfied" on a document or a statement needs a named reviewer in AI Governance (add `--by <id>`), who is not the owner and not the person who sent or recorded the evidence. Prepare it as one message for AI Governance: say which acceptance criteria the document meets and how, what the engine cannot check (is the signature real, is it current, is it the final version), and your recommendation. The person decides and says so in their own words (`--by <id> --statement "<their words>"`); the finding is recorded under their name with their words beside your reasons. Never record a person's "satisfied" without their statement, and never write the statement for them.
5. **Follow up** (Envoy): anything but satisfied writes a plain-words follow-up for the owner automatically. It is written, not sent: AI Governance sends it, then you record that with `aig control mark-sent`. Until then say it is written and waiting to be sent, never that the owner has been sent it. Mark a request sent only when a person says they sent it (`aig control mark-sent --id REQ-0xx --by <their id> --note "<their words>"`); a follow-up you write yourself is never "sent". Improve wording if needed.
6. **Re-score** (Meridian): `aig risk recompute` runs after each finding; explain the move. Credit counts in whole steps: moderate evidence earns half a step, which is banked but does not move the score alone. When a score does not move after a verified control, say how much is banked and what would move it; never say only "still Red".
7. **Overrule** (AI Governance only): `aig finding overrule --id F-0xx --verdict ... --by <id> --statement "<their words>"`. It files a catalog proposal so the criteria get reviewed.

## Importing results from other tools

`aig formats list` shows what the engine reads (SARIF code scans, JSON and CSV results, plus PDFs, documents and screenshots that are fingerprinted and read by Verifier). Tell owners the formats their tools can export; the playbook of each control lists tools people commonly use. Examples: Semgrep or CodeQL (SARIF) for code and dependency scans; garak, PyRIT or promptfoo (JSON) for red-teaming; Fairlearn or Aequitas (CSV or JSON) for fairness; SHAP output for explainability; Evidently exports for drift.

## Strength and credit

Strong full credit, moderate half, weak none, expired none. Strength is set from the file itself on arrival: a report earns "strong" only if its own contents name the tool that made it; typed-in text is always weak. A model version change expires evidence tied to the old version, including documents for controls that depend on the model. Evidence past its date earns no credit the moment it passes, even before the expiry check runs.
