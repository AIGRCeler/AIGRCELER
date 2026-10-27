"""Command line for AIGRCeler v2.  py -3 aigrceler.py <group> <command> [options]"""
import argparse
import os
import sys
import time
from pathlib import Path

from .core import AigError, WS
from . import (wsmod, catalogmod, projmod, ctrlmod, riskmod, evidmod, monmod, stagemod, viewsmod, checkmod, concernmod, profmod, regmod, assessmod, chasemod, dashmod)

INT_ARGS = {"likelihood", "impact_n", "seq", "days"}
FLOAT_ARGS = {"baseline", "min", "max", "value"}
TRUE_FLAGS = {"all_drafted", "all_defaults", "without_start", "transcribed", "reportable", "inferred", "send", "open"}
DEST = {"--with": "with_person", "--impact": None}


class Args:
    """Namespace that answers None for any option a command did not define."""
    def __init__(self, ns):
        self.__dict__.update(vars(ns))

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return None


# (group, command, function, [options], needs_workspace)
C = []


def cmd(group, name, fn, opts="", ws=True):
    C.append((group, name, fn, [o for o in opts.split() if o], ws))


cmd("ws", "init", wsmod.cmd_init, "--company --governance-name --governance-contact --basis", ws=False)
cmd("ws", "status", wsmod.cmd_status)
cmd("ws", "release", wsmod.cmd_version, ws=False)
cmd("ws", "thresholds-set", wsmod.cmd_thresholds_set, "--level --roles --statement")
cmd("ws", "principles-set", wsmod.cmd_principles_set, "--text")
cmd("role", "list", wsmod.cmd_role_list)
cmd("role", "add", wsmod.cmd_role_add, "--name --parent --domains --note")
cmd("role", "set", wsmod.cmd_role_set, "--role --name --parent --domains --note")
cmd("role", "assign", wsmod.cmd_assign, "--person --role --kind --start --end --basis")
cmd("role", "unassign", wsmod.cmd_unassign, "--person --role --end")
cmd("person", "add", wsmod.cmd_person_add, "--name --contact --type")
cmd("person", "list", wsmod.cmd_person_list)
cmd("orgrisk", "add", wsmod.cmd_orgrisk_add, "--title --description --inherent --residual --controls --owner-role")
cmd("orgrisk", "accept", wsmod.cmd_orgrisk_accept, "--id --statement --basis")
cmd("orgrisk", "list", wsmod.cmd_orgrisk_list)
cmd("exception", "add", wsmod.cmd_exception_add, "--what --why --expires --statement --person --controls")
cmd("exception", "list", wsmod.cmd_exception_list, "")
cmd("formats", "list", wsmod.cmd_formats_list)

cmd("catalog", "adopt-starter", catalogmod.cmd_adopt_starter, "--statement")
cmd("catalog", "list", catalogmod.cmd_list, "--domain")
cmd("catalog", "show", catalogmod.cmd_show, "--id")
cmd("catalog", "coverage", catalogmod.cmd_coverage)
cmd("catalog", "impact", catalogmod.cmd_impact, "--id")
cmd("catalog", "propose", catalogmod.cmd_propose, "--kind --id --change --reason --source --ref")
cmd("catalog", "proposals", catalogmod.cmd_proposals, "--status")
cmd("catalog", "proposal-show", catalogmod.cmd_proposal_show, "--id")
cmd("catalog", "approve", catalogmod.cmd_proposal_approve, "--id --statement")
cmd("catalog", "decline", catalogmod.cmd_proposal_decline, "--id --statement")
cmd("catalog", "release", catalogmod.cmd_release, "--statement")
cmd("catalog", "sync-starter", catalogmod.cmd_sync_starter, "--statement")

cmd("project", "create", projmod.cmd_create, "--name --purpose --users --jurisdictions --sourcing-mode --business-owner-role --model-version")
cmd("project", "set", projmod.cmd_set, "--purpose --users --interaction-mode --human-review --context-notes --resources --jurisdictions --sourcing-mode --data-sources --techniques --eval-metrics --downstream-dependencies --business-owner-role --consequential-actions --flags-on --flags-off --model-version --statement")
cmd("project", "screen", projmod.cmd_screen, "--users --autonomy --data --impact --flags-on")
cmd("project", "show", projmod.cmd_show)
cmd("project", "lane-options", projmod.cmd_lane_options)
cmd("project", "lane-set", projmod.cmd_lane_set, "--lane --statement")

cmd("stage", "gate", stagemod.cmd_gate, "--stage")
cmd("stage", "start", stagemod.cmd_start, "--stage --statement")
cmd("stage", "close", stagemod.cmd_close, "--stage --without-start --statement --force-with-reason")
cmd("stage", "adopt", stagemod.cmd_adopt, "--stage --source")
cmd("operate", "readiness", stagemod.cmd_readiness)
cmd("operate", "signoff", stagemod.cmd_signoff, "--statement")
cmd("operate", "chase", chasemod.cmd_chase, "--person")
cmd("stage", "block", projmod.cmd_block_add, "--reason")
cmd("stage", "block-review", projmod.cmd_block_review, "--reason")
cmd("stage", "lift-block", projmod.cmd_lift_block, "--id --statement")

cmd("risk", "init", riskmod.cmd_init)
cmd("risk", "set", riskmod.cmd_set, "--id --likelihood --impact --reason --all-defaults --like")
cmd("risk", "recompute", riskmod.cmd_recompute)
cmd("risk", "show", riskmod.cmd_show)
cmd("risk", "add", riskmod.cmd_add, "--title --dimension --likelihood --impact --reason --like")
cmd("risk", "gaps", riskmod.cmd_gaps)
cmd("assess", "item", assessmod.cmd_item, "--item --status --note --control --statement")
cmd("assess", "show", assessmod.cmd_show)
cmd("risk", "accept", riskmod.cmd_accept, "--id --statement --basis --with --until")

cmd("control", "draft", ctrlmod.cmd_draft, "--domain")
cmd("control", "approve", ctrlmod.cmd_approve, "--ids --all-drafted --domain --statement")
cmd("control", "decline", ctrlmod.cmd_decline, "--ids --all-drafted --domain --statement")
cmd("control", "tailor", ctrlmod.cmd_tailor, "--id --note --owner-role")
cmd("control", "assign", ctrlmod.cmd_assign, "--ids --role --owner --due --exception")
cmd("control", "mark-sent", ctrlmod.cmd_mark_sent, "--id --channel --note")
cmd("control", "unmark-sent", ctrlmod.cmd_unmark_sent, "--id --note")
cmd("control", "set-due", ctrlmod.cmd_set_due, "--id --due --why")
cmd("control", "state", ctrlmod.cmd_state, "--id --to --why")
cmd("control", "waive", ctrlmod.cmd_waive, "--id --statement --until")
cmd("control", "retire", ctrlmod.cmd_retire, "--id --statement")
cmd("control", "upgrade", ctrlmod.cmd_upgrade, "--id --statement")
cmd("control", "list", ctrlmod.cmd_list, "--state --domain")
cmd("control", "owners", ctrlmod.cmd_owners)
cmd("control", "applies", ctrlmod.cmd_applies, "--ids")
cmd("request", "create", ctrlmod.cmd_request_create, "--to --type --subject --text --controls --due")
cmd("request", "answer", ctrlmod.cmd_request_answer, "--id --file --text --transcribed --remaining --remaining-to")
cmd("request", "set-due", ctrlmod.cmd_request_set_due, "--id --due")
cmd("request", "withdraw", ctrlmod.cmd_request_withdraw, "--id --reason")
cmd("request", "list", ctrlmod.cmd_request_list, "--status")

cmd("evidence", "intake", evidmod.cmd_intake, "--control --file --text --kind --type --tool --tool-version --model-version --period --submitted-by --request")
cmd("evidence", "list", evidmod.cmd_list, "--control")
cmd("evidence", "expire-check", evidmod.cmd_expire_check)
cmd("finding", "record", evidmod.cmd_finding, "--evidence --verdict --reasons --gaps --strength --statement")
cmd("finding", "overrule", evidmod.cmd_overrule, "--id --verdict --statement --strength")

cmd("indicator", "set", monmod.cmd_ind_set, "--control --metric --baseline --min --max --unit")
cmd("indicator", "update", monmod.cmd_ind_update, "--id --value")
cmd("indicator", "list", monmod.cmd_ind_list)
cmd("incident", "open", monmod.cmd_inc_open, "--title --severity --description --controls --owner --reportable --statement")
cmd("incident", "update", monmod.cmd_inc_update, "--id --note --severity --owner")
cmd("incident", "escalate", monmod.cmd_inc_escalate, "--id --to")
cmd("incident", "ack", monmod.cmd_inc_ack, "--id")
cmd("incident", "close", monmod.cmd_inc_close, "--id --outcome --retrospective --lesson --statement")
cmd("incident", "clocks", monmod.cmd_inc_clocks)
cmd("incident", "list", monmod.cmd_inc_list)
cmd("obligation", "add", monmod.cmd_ob_add, "--title --authority --due --incident")
cmd("obligation", "close", monmod.cmd_ob_close, "--id --note")
cmd("containment", "add", monmod.cmd_ct_add, "--title --ends --incident --control --statement --request")
cmd("containment", "confirm", monmod.cmd_ct_confirm, "--id --source")
cmd("containment", "end", monmod.cmd_ct_end, "--id")
cmd("review", "add", monmod.cmd_review_add, "--kind --summary")
cmd("review", "due", chasemod.cmd_review_due)
cmd("review", "schedule", chasemod.cmd_review_schedule, "--days --statement")

cmd("concern", "add", concernmod.cmd_add, "--kind --text --carry-to --asked-by")
cmd("concern", "resolve", concernmod.cmd_resolve, "--id --note --statement")
cmd("concern", "carry", concernmod.cmd_carry, "--id --to --reason")
cmd("concern", "list", concernmod.cmd_list, "--status")
cmd("profile", "show", profmod.cmd_show, "--open")
cmd("profile", "set", profmod.cmd_set, "--field --value --source --file --inferred")
cmd("profile", "unknown", profmod.cmd_unknown, "--field --asked --reason")
cmd("profile", "na", profmod.cmd_na, "--field --reason")
cmd("profile", "plan", profmod.cmd_plan, "--send --due")
cmd("profile", "for", profmod.cmd_for, "--scenario --control --field")
cmd("profile", "doc", profmod.cmd_doc, "--kind --name --status --source")
cmd("reg", "coverage", regmod.cmd_coverage, "--framework --status")
cmd("reg", "item", regmod.cmd_item, "--ref")
cmd("reg", "project", regmod.cmd_project, "--framework")
cmd("journal", "verify", checkmod.cmd_verify)
cmd("journal", "show", checkmod.cmd_show)
cmd("journal", "erratum", checkmod.cmd_erratum, "--seq --text")
cmd("views", "regenerate", viewsmod.cmd_regenerate)
cmd("views", "launch-status", viewsmod.cmd_launch_status)
cmd("check", "run", checkmod.cmd_check)
cmd("dashboard", "build", dashmod.cmd_build, "--open")
cmd("dashboard", "path", dashmod.cmd_path)

TYPES = {"likelihood": int, "impact_n": int, "seq": int, "baseline": float, "min": float, "max": float, "value": float}
# options whose name clashes between meanings of 'impact': in 'project screen' it is a word, in 'risk set' it is a number.
INT_FOR = {("risk", "set"): {"impact"}, ("risk", "add"): {"impact"}}
STR_FOR = {("profile", "set"): {"value"}}
DESTS = {"--with": "with_person"}


def build():
    p = argparse.ArgumentParser(prog="aigrceler.py", description="AIGRCeler v2 engine. Scripts own all records.")
    sub = p.add_subparsers(dest="group", metavar="group")
    groups = {}
    for group, name, fn, opts, needs_ws in C:
        if group not in groups:
            gp = sub.add_parser(group)
            groups[group] = gp.add_subparsers(dest="command", metavar="command")
        sp = groups[group].add_parser(name)
        sp.add_argument("--ws")
        sp.add_argument("--by")
        sp.add_argument("-p", "--project")
        sp.add_argument("--json", action="store_true")
        for o in opts:
            dest = DESTS.get(o, o[2:].replace("-", "_"))
            kw = {"dest": dest}
            if dest in TRUE_FLAGS:
                kw["action"] = "store_true"
            elif dest in INT_ARGS or dest in INT_FOR.get((group, name), set()):
                kw["type"] = int
            elif dest in FLOAT_ARGS and dest not in STR_FOR.get((group, name), set()):
                kw["type"] = float
            sp.add_argument(o, **kw)
        sp.set_defaults(_fn=fn, _needs_ws=needs_ws)
    return p


def main(argv=None):
    parser = build()
    ns = parser.parse_args(argv)
    if not getattr(ns, "_fn", None):
        parser.print_help()
        return 0
    args = Args(ns)
    lock = None
    try:
        if ns._needs_ws:
            ws = WS.find(args.ws)
            lock = _acquire(ws.p("data", ".aigrceler.lock"))
            if not ns.project and hasattr(ns, "project"):
                ns.project = args.project = _project_from_cwd(ws)
        else:
            ws = WS(args.ws or ".")
        rc = ns._fn(args, ws)
        # Keep the dashboard current after anything that may have changed a record. Best effort: it never stops the command.
        if ns._needs_ws and not (isinstance(rc, int) and rc) and ns.command not in dashmod.READ_ONLY_COMMANDS \
                and dashmod.auto_enabled() and ws.exists():
            dashmod.try_build(ws)
        return rc if isinstance(rc, int) else 0
    except AigError as e:
        print("Not done: %s" % e, file=sys.stderr)
        return 2
    except BrokenPipeError:
        return 0
    except Exception as e:  # never show a raw traceback to a person who cannot act on it
        if os.environ.get("AIGRCELER_DEBUG") == "1":
            raise
        print("Not done: something unexpected went wrong (%s: %s). Check what you typed. "
              "If it keeps happening, run the check ('check run') and tell the person who looks after AIGRCeler." % (
                  type(e).__name__, str(e)[:160]), file=sys.stderr)
        return 3
    finally:
        if lock:
            try:
                lock.close()
            except OSError:
                pass


def _project_from_cwd(ws):
    """Working inside <workspace>/projects/<system>? Then that system is the one meant."""
    try:
        rel = Path.cwd().resolve().relative_to(ws.root / "projects")
        name = rel.parts[0] if rel.parts else None
        if name and (ws.root / "projects" / name / "data" / "project.json").exists():
            return name
    except (ValueError, OSError):
        pass
    return None


def _acquire(path):
    """One command at a time per workspace, so two commands cannot overwrite each other's records.
    Uses an operating-system file lock (no file to delete afterwards)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    f = open(path, "a+")
    if f.tell() == 0 and path.stat().st_size == 0:
        f.write(" ")
        f.flush()
    deadline = time.time() + 60
    while True:
        try:
            if os.name == "nt":
                import msvcrt
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return f
        except OSError:
            if time.time() > deadline:
                raise AigError("Another AIGRCeler command is still running on this workspace. Try again in a minute.")
            time.sleep(0.1)
