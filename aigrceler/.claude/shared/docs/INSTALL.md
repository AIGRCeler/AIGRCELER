# Installing AIGRCeler v2 for a company

You need Windows, Python 3 (`py -3`), and Claude Code.

1. Make a folder for the company, for example `C:\Clients\Acme\AIGRCeler`. This is the company root.
2. Copy the three items of the delivery into it: `.claude\`, `CLAUDE.md`, `aigrceler.ps1`.
3. Optional: run the self-test from that folder: `py -3 .claude\shared\testing\selftest.py`. It should end with a line such as "286 checks, 0 failed." (the number of checks grows with releases; "0 failed" is what matters).
4. Run the menu: `powershell -ExecutionPolicy Bypass -File aigrceler.ps1`
5. First run: it asks for the company name, the person who will act as AI Governance, how to reach them, and the authority they act on. Then choose **N** to add the first AI system (name and one line on what it does).
6. It opens Claude Code in that system's folder. Say "start AIGRCeler". The setup skill leads you through people, roles and adopting the starter catalog (company-level work: choose **W** in the menu).

Next time, run the menu again and pick the AI system, or **W** for company-level work.

## Updating the framework later

Replace `.claude\` and `CLAUDE.md` in the company root with the new ones. The company's records are in `data\`, `catalog\`, `decisions\`, `00-status\` and `projects\`, outside `.claude\`, and are not touched.

## Folder map of a company root

```
<company root>\
  .claude\                framework (agents, skills, engine, templates)
  CLAUDE.md               operating rules
  aigrceler.ps1           the menu
  00-status\              roll-up views (generated)
  catalog\                the company's control catalog (current, versions, proposals)
  decisions\              company-level decision journal
  data\                   records (script-owned: do not edit)
  projects\<AI system>\   controls, evidence, incidents, decisions, people, working papers, logs
                          and .claude\ (a junction to the company's .claude\)
```

## If something is refused

The engine says why in plain words. Typical reasons: the person is not in the AI Governance role; a stage has not closed; a statement in the decision-maker's own words is missing; evidence is statement-only. Fix the cause. Do not edit the files.
