# Engine commands

Generated from the engine. `aig` = `py -3 .claude/shared/engine/aigrceler.py`. Every command accepts `--ws <folder>` (default: the workspace you are in), `--by <person id>` (who is acting; `tool` or nothing means AIGRCeler itself), `-p <system>` (the AI system).

Decision commands refuse unless `--by` names a person whose role allows it, and need the decision-maker's own words in `--statement`.


## ws

| Command | Options |
|---|---|
| `ws init` | `--company` `--governance-name` `--governance-contact` `--basis` |
| `ws status` | - |
| `ws release` | - |
| `ws thresholds-set` | `--level` `--roles` `--statement` |
| `ws principles-set` | `--text` |

## role

| Command | Options |
|---|---|
| `role list` | - |
| `role add` | `--name` `--parent` `--domains` `--note` |
| `role set` | `--role` `--name` `--parent` `--domains` `--note` |
| `role assign` | `--person` `--role` `--kind` `--start` `--end` `--basis` |
| `role unassign` | `--person` `--role` `--end` |

## person

| Command | Options |
|---|---|
| `person add` | `--name` `--contact` `--type` |
| `person list` | - |

## orgrisk

| Command | Options |
|---|---|
| `orgrisk add` | `--title` `--description` `--inherent` `--residual` `--controls` `--owner-role` |
| `orgrisk accept` | `--id` `--statement` `--basis` |
| `orgrisk list` | - |

## exception

| Command | Options |
|---|---|
| `exception add` | `--what` `--why` `--expires` `--statement` `--person` `--controls` |
| `exception list` | - |

## formats

| Command | Options |
|---|---|
| `formats list` | - |

## catalog

| Command | Options |
|---|---|
| `catalog adopt-starter` | `--statement` |
| `catalog list` | `--domain` |
| `catalog show` | `--id` |
| `catalog coverage` | - |
| `catalog impact` | `--id` |
| `catalog propose` | `--kind` `--id` `--change` `--reason` `--source` `--ref` |
| `catalog proposals` | `--status` |
| `catalog proposal-show` | `--id` |
| `catalog approve` | `--id` `--statement` |
| `catalog decline` | `--id` `--statement` |
| `catalog release` | `--statement` |
| `catalog sync-starter` | `--statement` |

## project

| Command | Options |
|---|---|
| `project create` | `--name` `--purpose` `--users` `--jurisdictions` `--sourcing-mode` `--business-owner-role` `--model-version` |
| `project set` | `--purpose` `--users` `--interaction-mode` `--human-review` `--context-notes` `--resources` `--jurisdictions` `--sourcing-mode` `--data-sources` `--techniques` `--eval-metrics` `--downstream-dependencies` `--business-owner-role` `--consequential-actions` `--flags-on` `--flags-off` `--model-version` `--statement` |
| `project screen` | `--users` `--autonomy` `--data` `--impact` `--flags-on` |
| `project show` | - |
| `project lane-options` | - |
| `project lane-set` | `--lane` `--statement` |

## stage

| Command | Options |
|---|---|
| `stage gate` | `--stage` |
| `stage start` | `--stage` `--statement` |
| `stage close` | `--stage` `--without-start` `--statement` `--force-with-reason` |
| `stage adopt` | `--stage` `--source` |
| `stage block` | `--reason` |
| `stage block-review` | `--reason` |
| `stage lift-block` | `--id` `--statement` |

## risk

| Command | Options |
|---|---|
| `risk init` | - |
| `risk set` | `--id` `--likelihood` `--impact` `--reason` `--all-defaults` `--like` |
| `risk recompute` | - |
| `risk show` | - |
| `risk add` | `--title` `--dimension` `--likelihood` `--impact` `--reason` `--like` |
| `risk gaps` | - |

## assess

| Command | Options |
|---|---|
| `assess item` | `--item` `--status` `--note` `--control` `--statement` |
| `assess show` | - |

## risk

| Command | Options |
|---|---|
| `risk accept` | `--id` `--statement` `--basis` `--with` `--until` |

## control

| Command | Options |
|---|---|
| `control draft` | `--domain` |
| `control approve` | `--ids` `--all-drafted` `--domain` `--statement` |
| `control decline` | `--ids` `--all-drafted` `--domain` `--statement` |
| `control tailor` | `--id` `--note` `--owner-role` |
| `control assign` | `--ids` `--role` `--owner` `--due` `--exception` |
| `control mark-sent` | `--id` `--channel` `--note` |
| `control unmark-sent` | `--id` `--note` |
| `control set-due` | `--id` `--due` `--why` |
| `control state` | `--id` `--to` `--why` |
| `control waive` | `--id` `--statement` `--until` |
| `control retire` | `--id` `--statement` |
| `control upgrade` | `--id` `--statement` |
| `control list` | `--state` `--domain` |
| `control owners` | - |
| `control applies` | `--ids` |

## request

| Command | Options |
|---|---|
| `request create` | `--to` `--type` `--subject` `--text` `--controls` `--due` |
| `request answer` | `--id` `--file` `--text` `--transcribed` `--remaining` `--remaining-to` |
| `request set-due` | `--id` `--due` |
| `request withdraw` | `--id` `--reason` |
| `request list` | `--status` |

## evidence

| Command | Options |
|---|---|
| `evidence intake` | `--control` `--file` `--text` `--kind` `--type` `--tool` `--tool-version` `--model-version` `--period` `--submitted-by` `--request` |
| `evidence list` | `--control` |
| `evidence expire-check` | - |

## finding

| Command | Options |
|---|---|
| `finding record` | `--evidence` `--verdict` `--reasons` `--gaps` `--strength` `--statement` |
| `finding overrule` | `--id` `--verdict` `--statement` `--strength` |

## indicator

| Command | Options |
|---|---|
| `indicator set` | `--control` `--metric` `--baseline` `--min` `--max` `--unit` |
| `indicator update` | `--id` `--value` |
| `indicator list` | - |

## incident

| Command | Options |
|---|---|
| `incident open` | `--title` `--severity` `--description` `--controls` `--owner` `--reportable` `--statement` |
| `incident update` | `--id` `--note` `--severity` `--owner` |
| `incident escalate` | `--id` `--to` |
| `incident ack` | `--id` |
| `incident close` | `--id` `--outcome` `--retrospective` `--lesson` `--statement` |
| `incident clocks` | - |
| `incident list` | - |

## obligation

| Command | Options |
|---|---|
| `obligation add` | `--title` `--authority` `--due` `--incident` |
| `obligation close` | `--id` `--note` |

## containment

| Command | Options |
|---|---|
| `containment add` | `--title` `--ends` `--incident` `--control` `--statement` `--request` |
| `containment confirm` | `--id` `--source` |
| `containment end` | `--id` |

## operate

| Command | Options |
|---|---|
| `operate readiness` | |
| `operate signoff` | `--statement` |
| `operate chase` | `--person` |

## review

| Command | Options |
|---|---|
| `review add` | `--kind` `--summary` |
| `review due` | |
| `review schedule` | `--days` `--statement` |

## concern

| Command | Options |
|---|---|
| `concern add` | `--kind` `--text` `--carry-to` `--asked-by` |
| `concern resolve` | `--id` `--note` `--statement` |
| `concern carry` | `--id` `--to` `--reason` |
| `concern list` | `--status` |

## profile

| Command | Options |
|---|---|
| `profile show` | `--open` |
| `profile set` | `--field` `--value` `--source` `--file` `--inferred` |
| `profile unknown` | `--field` `--asked` `--reason` |
| `profile na` | `--field` `--reason` |
| `profile plan` | `--send` `--due` |
| `profile for` | `--scenario` `--control` `--field` |
| `profile doc` | `--kind` `--name` `--status` `--source` |

## reg

| Command | Options |
|---|---|
| `reg coverage` | `--framework` `--status` |
| `reg item` | `--ref` |
| `reg project` | `--framework` |

## journal

| Command | Options |
|---|---|
| `journal verify` | - |
| `journal show` | - |
| `journal erratum` | `--seq` `--text` |

## views

| Command | Options |
|---|---|
| `views regenerate` | - |
| `views launch-status` | - |

## dashboard

The dashboard is one fixed page template (`shared/templates/dashboard/template.html`) filled with facts the engine reads from the records. It only reads: it changes no record. The engine rebuilds it by itself after any command that may have changed a record (never after a command that only looks), and a failure to build never stops that command. Output: `dashboard/index.html` (the page), `dashboard/dashboard.json` (the data behind it) and one dated snapshot per day in `dashboard/history/` (for trends). Optional company settings in `dashboard/config.json`: `title`, `accent` (a plain `#rrggbb` colour), `hide` (sections to leave out: attention, portfolio, dates, people, company, trends, controls, risk, evidence, watch, chase, discovery, regulatory, decisions) and `logo` (a small png, jpg or svg inside the dashboard folder). Nobody writes or edits dashboard HTML by hand.

| Command | Options |
|---|---|
| `dashboard build` | `--open` (also opens it in the default browser) |
| `dashboard path` | - |

## check

| Command | Options |
|---|---|
| `check run` | - |
