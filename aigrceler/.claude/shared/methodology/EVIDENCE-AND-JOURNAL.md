# Evidence and the decision journal

## Evidence

- **Fingerprint at intake.** The file is copied under `evidence/EV-xxx/` and a SHA-256 is recorded. `check run` re-tests every fingerprint. Originals are never altered.
- **Strength on arrival.** Decided from the file itself, never from what the sender says about it. Strong: a machine-readable report whose own contents name the tool that made it (a SARIF driver name, or a "tool" field), tied to the model version where the control is model-bound. Moderate: a document or screenshot a person produced, or a report that does not name its tool. Weak: a statement, and any text typed in by someone on a person's behalf (recorded as "transcribed"). A finding may lower strength, never raise it.
- **Model-bound controls.** Evidence for a control that depends on the model is tied to the model version in force when it arrives, whatever its kind. A model version change expires it.
- **Validity.** Each control says how long evidence stays valid. A model version change expires evidence tied to the old version.
- **Retention.** `retain_until` is set by lane (provisional: full 10 years, standard 7, light 5). Verify against counsel for your sector. The EU AI Act documentation period for providers of high-risk systems is 10 years.
- **Findings.** Verdict (satisfied, partly, not, cannot tell), reasons, gaps, strength, reviewer. The tool may record any verdict on strong evidence and "partly", "not" or "cannot tell" on anything. "Satisfied" on a document or statement needs a named reviewer who holds the authority to verify (AI Governance), and who is not the owner of the control, the person who sent the evidence, or the person who recorded it. Only a "satisfied" finding can lift a control to verified, and only from a state where that makes sense: never a retired, waived or drafted control. AI Governance can overrule (not their own control's evidence); the overrule is a journal decision and files a catalog proposal. `check run` lists controls verified by the tool alone so AI Governance can sample them.
- **Calendar.** Evidence past its valid-until date earns no credit as soon as the date passes. Every gate, status view, launch check and risk recompute applies the expiry first.
- **Importing from other tools.** `formats list`. SARIF, JSON and CSV are read for structure and counts; documents and images are fingerprinted and read by Verifier.

## Journal

One line per decision, JSON Lines, append-only: `decisions/journal.jsonl`, for the workspace and for each system.

Each line has: number, time, type, scope, subject, decided by (role and person), authority basis, summary, labels (`unsigned` = relayed through the tool, not cryptographically signed; `tool`; `adopted`; `below-suggested`; ...), optional pointer to a longer text with its fingerprint, the previous line's hash, its own hash.

- Editing or removing a line breaks the chain; `journal verify` says where. The latest line number and hash are also kept outside the journal folder (`data/journal-head.json`), so removing the last lines, or the whole journal, is caught too.
- Evidence arrival (with its fingerprint and strength) and every finding are journal lines. `check run` compares the evidence records with those lines, so a rewritten record or fingerprint is caught.
- One command runs at a time per workspace (an operating-system lock), so two commands cannot overwrite each other.
- Corrections are new lines of type `erratum`; the original is never changed.
- Decision-makers' own words are stored in `decisions/texts/NNNN.md`. The tool never writes a person's words for them.
- Readable table: `00-status/decision-journal.md` (generated).

Types: workspace init, screening, project facts changed, evidence intake, finding, role change and assignment, threshold change, principles adopted, catalog version, catalog proposal decided, project created, lane assignment and change, block placed and lifted, stage start, stage close (including without a start decision, recorded as such), adoption, control approval and retirement, waiver, exception, finding overruled, risk acceptance and lapse, incident declared and closed, obligation, containment, erratum.

## Honest limit

The hash chain proves a line was not altered after it was written. It does not prove who wrote it; the `unsigned` label says so. `--by` is a name typed at the keyboard, not a login. Anyone with access to the workspace folder could rewrite the whole journal and its head record together; a company that needs more keeps a copy of the head record somewhere outside (for example in a ticket or a signed email). A company that needs signatures can add them outside the framework.
