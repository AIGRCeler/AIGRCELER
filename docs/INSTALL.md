# Installing AIGRCeler

## What you need

- Windows with PowerShell (the menu script is a PowerShell script).
- Python 3, started with `py -3`. The engine uses only Python's standard library, so nothing else needs installing.
- Claude Code.

## 1. Get the release

Either download the zip from the Releases page of this repository, or copy the `aigrceler` folder from the repository. The zip holds the same folder.

Optional check of the download: the release also has a file `SHA256SUMS.txt`. In PowerShell:

```
Get-FileHash .\aigrceler-v<version>.zip -Algorithm SHA256
```

The hash printed must match the line in `SHA256SUMS.txt`. If it does not, do not use the file.

## 2. Put it in a company folder

Make a folder for the company, for example `C:\Clients\Acme\AIGRCeler`. This is the **company root**. Copy the three items from the `aigrceler` folder into it:

```
<company root>\
  .claude\          the framework: agents, skills, engine, catalog, templates, methodology
  CLAUDE.md         operating rules
  aigrceler.ps1     the menu
```

Which release you have is written in `.claude\shared\VERSION`, and `py -3 .claude\shared\engine\aigrceler.py ws release` prints it.

## 3. Check it works (optional)

From the company root:

```
py -3 .claude\shared\testing\selftest.py
```

It builds a throw-away demo company in a temporary folder, runs a full lifecycle and checks the rules that matter. It should end with a line such as "286 checks, 0 failed." (the number of checks grows with releases; "0 failed" is what matters). It writes nothing in your company folder.

## 4. Start

```
powershell -ExecutionPolicy Bypass -File aigrceler.ps1
```

The first run asks for the company name, the person who will act as AI Governance, how to reach them, and the authority they act on. Then choose **N** to add the first AI system (a name and one line on what it does). The menu opens Claude Code in that system's folder. Say "start AIGRCeler". The setup skill leads you through people, roles and adopting the starter catalog (company-level work is **W** in the menu).

Next time, run the menu again and pick the AI system, or **W** for company-level work.

## Where things end up

Next to the three items, AIGRCeler creates the company's own records. They are written by the engine and are not to be edited by hand:

```
<company root>\
  00-status\              roll-up views (generated)
  catalog\                the company's control catalog
  decisions\              company-level decision journal
  data\                   records
  projects\<AI system>\   controls, evidence, incidents, decisions, people, working papers, logs
```

Back this folder up like any other sensitive company record.

## If something is refused

The engine says why in plain words. Typical reasons: the person is not in the AI Governance role; a stage has not closed; a statement in the decision-maker's own words is missing; evidence is a statement only. Fix the cause. Do not edit the files to get around it.

## Newer releases

See [UPGRADE.md](UPGRADE.md).
