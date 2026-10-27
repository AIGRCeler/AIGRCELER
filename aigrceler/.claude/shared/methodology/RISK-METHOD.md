# Risk method (provisional)

Provisional means: chosen to be defensible and simple, and reversible if experience says otherwise.

## Steps

1. **Scenarios.** `risk init` opens the standard scenarios that fit the system's sourcing mode and factors. Each belongs to one of six dimensions.
2. **Inherent rating.** Meridian rates likelihood (1 to 5) and impact (1 to 5) before any control, with a reason. Score = likelihood x impact (1 to 25).
3. **Credit.** A control states which scenarios it addresses, its type, and the most steps it can remove (0 to 2). Preventive controls reduce likelihood; detective and corrective controls reduce impact or duration.
4. **Only verified controls earn credit.** Strong evidence earns the full reduction, moderate half, weak none. Expired evidence earns none. Evidence tied to an old model version earns none.
5. **Whole steps.** Credit is summed per axis and rounded down. At most two steps in total per scenario.
6. **Floors.** Some scenarios cannot drop below High (for example automated decisions about people with legal effect and no human review; EU high-risk use; consequential actions).
7. **Suspension.** If a control's indicator is out of tolerance, its credit is suspended until it recovers.
8. **Roll-up.** For each dimension: ratio = (0.7 x highest scenario + 0.3 x average scenario) / 25. Points = ratio x the dimension's maximum.

| Dimension | Max points |
|---|---|
| Accuracy | 20 |
| Fairness | 20 |
| Data quality | 15 |
| Security and misuse | 15 |
| Human oversight | 15 |
| Regulatory and governance | 15 |

Total 100. Bands: Green 0-20, Yellow 21-40, Orange 41-60, Red 61-100. Scenario levels (illustrative): Low 1-4, Medium 5-9, High 10-16, Critical 17-25.

## Acceptance

Residual level sets who may accept (workspace thresholds): Low, Medium and High by AI Governance; Critical by executive leadership alone or with AI Governance. The basis (charter, board resolution) is recorded. If a later recomputation raises the residual level, the acceptance lapses and the journal says so.

## Company-level risks

AI expertise, technology readiness, accountability gaps and complexity are tracked in the workspace beside the system scores, never added into them.

## Why not the old score

The old five-dimension score (25/25/20/15/15) mixed inherent risk with control state. The new one separates them so a regulator can see what each control bought.
