# Lanes (provisional)

A short screening at discovery gives a tier (1 to 4) from four plain questions: how many people are affected, how much the system acts without review, what data it touches, how serious a wrong outcome is. AI Governance confirms the lane and records why.

| Lane | When | What changes |
|---|---|---|
| Light | Tier 1 and no ruling-out factor | One combined pass for Discover, Assess and Govern. A core-minimum set of controls (inventory entry, named owner, acceptable-use rule, data-sharing rule, vendor basics, access, incident contact, annual review...). One batch approval. Annual check plus triggers. |
| Standard | Tier 2, or a softer factor | All four stages with a reduced catalog subset |
| Full | Tier 3 or 4, or any hard factor | Everything |

## What Discover asks per lane

Discover uses one set of 77 questions in eleven sections. The light lane asks the 22 core questions, the standard lane adds 31 (53 in all), the full lane asks everything (77). Some questions apply only when a fact calls for them. Before the lane is decided, the suggested lane sets the depth, and with neither the core questions apply. No more than 20 percent of the required questions may be unknown or skipped, and 16 critical ones can never be unknown.

## Factors

Hard (full lane): decisions about people with legal or similar effect; sensitive personal data; EU AI Act high-risk or prohibited use; safety impact; consequential actions; more than three downstream dependencies.
Softer (at least standard): personal data; automated customer-facing output; a regulated-sector use.

Any of them rules out the light lane. The tool refuses to set it.

## Moving between lanes

- Up: automatic when a factor appears (a new data type, a new use, scale, an incident). The journal records it as automatic.
- Down: AI Governance decision with a reason, in their own words. Choosing a lane below the suggested one is allowed with a reason and is labelled `below-suggested`.
- Yearly: AI Governance spot-checks a sample of light systems (Warden helps).

## Why

An SME running a meeting-notes summarizer and an SME running a hiring screener need different amounts of governance. Same catalog, different slice.
