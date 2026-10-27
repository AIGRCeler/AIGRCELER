"""Stages and their gates. A stage starts only by an AI Governance decision."""
import shutil
from pathlib import Path

from .core import (
    AigError, STAGES, iso, today, require, need_text, resolve_actor, split_list, write_text,
    sha256_file, sha256_text, now, check_file, read_any_text, norm_stage,
)
from . import projmod, evidmod

SEQ = {s: i for i, s in enumerate(STAGES)}
LIGHT_PASS = ["DISCOVER", "ASSESS", "GOVERN"]
PLAIN_STAGE = {
    "DISCOVER": "Discover: what the AI system is and how much care it needs",
    "ASSESS": "Assess: what could go wrong",
    "GOVERN": "Govern: decide which controls apply and who owns them",
    "OPERATE": "Operate: every control is proved and watched on its own; the go decision is recorded when AI Governance makes it",
}


def gate(ws, pr, stage):
    """Return a list of reasons the stage cannot close yet, in plain words."""
    evidmod.refresh(ws, pr)   # evidence past its date and ended waivers must not count at a gate
    info = pr.info()
    b = []
    cs = pr.all_controls()
    live = [c for c in cs if c["state"] not in ("retired",)]
    if stage == "DISCOVER":
        if not info.get("purpose"):
            b.append("The purpose of the AI system is not written down.")
        if not info.get("sourcing_mode"):
            b.append("How the system is sourced (built, bought, open-source...) is not recorded.")
        if not info.get("tier"):
            b.append("The screening has not been done.")
        if not info.get("lane_decided"):
            b.append("AI Governance has not confirmed the lane.")
        from . import profmod
        b.extend(profmod.gate_items(ws, pr, info))
        names = {p["id"]: p["name"] for p in ws.load("people", [])}
        openq = [r for r in pr.load("requests", []) if r.get("type") == "discovery_question" and r["status"] == "open"]
        if openq:
            who = sorted({names.get(r["to"], r["to"]) for r in openq})
            b.append("%d discovery question(s) sent to %s are not answered yet." % (len(openq), ", ".join(who)))
    elif stage == "ASSESS":
        ob = [x for x in info["blocks"] if not x["lifted"]]
        if ob:
            b.append("A stage block is in force, so Assess cannot close until AI Governance lifts it: %s" % ob[0]["reason"])
        risks = pr.load("risks", [])
        if not risks:
            b.append("No risk scenarios have been opened (risk init).")
        un = [r["id"] for r in risks if not r.get("inherent_set")]
        if un:
            b.append("%d risk scenario(s) are not rated yet: %s." % (len(un), ", ".join(un[:8])))
        from . import concernmod, assessmod
        carried = [c["id"] for c in concernmod.open_items(pr, "concern") if c.get("carry_to") == "ASSESS"]
        if carried:
            b.append("%d concern(s) carried into Assess are not dealt with yet: %s. Rate each as a risk or explain why not and record it "
                     "('concern resolve'), or pass it on to a later stage with the reason ('concern carry')." % (len(carried), ", ".join(carried[:8])))
        b.extend(assessmod.gate_items(ws, pr, info))
    elif stage == "GOVERN":
        from . import assessmod as _am
        b.extend(_am.govern_gate_items(ws, pr))
        from . import concernmod as _cm
        _carried = [c["id"] for c in _cm.open_items(pr, "concern") if c.get("carry_to") == "GOVERN"]
        if _carried:
            b.append("%d concern(s) carried into Govern are not dealt with yet: %s. Settle each ('concern resolve', with a note saying how) "
                     "or pass it on to a later stage with the reason ('concern carry')." % (len(_carried), ", ".join(_carried[:8])))
        if not ws.settings().get("catalog_version"):
            b.append("The company has not adopted a control catalog.")
        if not cs:
            b.append("No controls have been drafted for this AI system.")
        dr = [c["id"] for c in cs if c["state"] == "drafted"]
        if dr:
            b.append("%d drafted control(s) still wait for AI Governance: %s." % (len(dr), ", ".join(dr[:8])))
        no_owner = [c["id"] for c in live if c["state"] in ("approved",) ]
        if no_owner:
            b.append("%d approved control(s) have no owner yet: %s." % (len(no_owner), ", ".join(no_owner[:8])))
        crit = [c["id"] for c in live if c["definition"].get("critical") and c["state"] == "drafted"]
        if crit:
            b.append("Critical controls not yet decided: %s." % ", ".join(crit))
    elif stage == "OPERATE":
        b.extend(readiness(ws, pr)[0])
    return b


def readiness(ws, pr, fresh=True):
    """What stands between this AI system and a go decision, worked out live from the records.
    Returns (blockers in plain words, numbers). The required set is every critical or launch-required control that applies.
    fresh=False reads the records as they are, without applying expiries (the dashboard only reads)."""
    if fresh:
        evidmod.refresh(ws, pr)
    cs = [c for c in pr.all_controls() if c["state"] not in ("retired",)]
    ok_states = ("verified", "monitored", "waived")
    req = [c for c in cs if c["definition"].get("critical") or c["definition"].get("launch_required")]
    pend_crit = [c["id"] for c in cs if c["definition"].get("critical") and c["state"] not in ok_states]
    pend_launch = [c["id"] for c in cs if c["definition"].get("launch_required") and c["state"] not in ok_states and c["id"] not in pend_crit]
    b = []
    if pend_crit:
        b.append("%d critical control(s) are not verified yet: %s." % (len(pend_crit), ", ".join(pend_crit[:10])))
    if pend_launch:
        b.append("Controls required before launch are not verified: %s." % ", ".join(pend_launch[:10]))
    openinc = [i["id"] for i in pr.load("incidents", []) if i["status"] == "open" and i["severity"] in ("high", "critical")]
    if openinc:
        b.append("High or critical incidents are still open: %s." % ", ".join(openinc))
    done = [c for c in req if c["state"] in ok_states]
    return b, {"required": len(req), "done": len(done)}


def _stage_arg(args):
    if not args.stage:
        raise AigError("Say which stage (--stage %s)." % " | ".join(STAGES))
    stage = norm_stage(args.stage)
    if stage not in STAGES:
        raise AigError("Stage must be one of: %s." % ", ".join(STAGES))
    return stage


def _closed(st):
    return st["status"] in ("closed", "closed_without_start")


def _may_begin(info, stage):
    """The rules every way of beginning a stage must obey (a start decision, an adopted statement, or a close without start)."""
    # A block lets Discover and Assess start and run (that is where the facts are found and the risks rated),
    # but holds Assess from closing and the stages after it from starting until AI Governance lifts it.
    open_blocks = [b for b in info["blocks"] if not b["lifted"]]
    if open_blocks and SEQ[stage] > SEQ["ASSESS"]:
        raise AigError("Stages after Assess cannot start while a block is in force: %s. AI Governance lifts a block with 'stage lift-block'." % open_blocks[0]["reason"])
    st = info["stages"][stage]
    if st["status"] != "not_started":
        raise AigError("%s is already %s." % (stage, st["status"]))
    light = info.get("lane") == "light"
    if light and stage in ("ASSESS", "GOVERN") and info["stages"]["DISCOVER"]["status"] == "not_started":
        raise AigError("In the light lane Discover, Assess and Govern run as one pass. Start DISCOVER.")
    if SEQ[stage] > 0:
        prev = STAGES[SEQ[stage] - 1]
        if not _closed(info["stages"][prev]):
            raise AigError("%s must close before %s can start." % (prev, stage))
    if SEQ[stage] > 0 and not info.get("lane_decided"):
        raise AigError("The lane must be decided before %s." % stage)


def _covers(info, stage):
    return LIGHT_PASS if (info.get("lane") == "light" and stage == "DISCOVER") else [stage]


def widen_light_pass(info, lane_seq):
    """The lane became 'light' after DISCOVER had started on its own: the one pass now covers all three."""
    d = info["stages"]["DISCOVER"]
    if d["status"] == "started" and d.get("covers", ["DISCOVER"]) == ["DISCOVER"] and \
            all(info["stages"][x]["status"] == "not_started" for x in ("ASSESS", "GOVERN")):
        d["covers"] = list(LIGHT_PASS)
        for x in ("ASSESS", "GOVERN"):
            info["stages"][x] = {"status": "started", "started_seq": d.get("started_seq"), "started": d.get("started"),
                                 "covers": list(LIGHT_PASS), "joined_by_lane_seq": lane_seq}
        return True
    return False


def cmd_gate(args, ws):
    pr = ws.project(args.project)
    stage = _stage_arg(args)
    info = pr.info()
    stages = info["stages"][stage].get("covers") or _covers(info, stage)
    allb = []
    for s in stages:
        allb += ["%s: %s" % (s, x) for x in gate(ws, pr, s)]
    if stage == "OPERATE":
        return _print_readiness(ws, pr)
    if allb:
        print("Cannot close %s yet:" % stage)
        for x in allb:
            print("  - " + x)
    else:
        print("%s can close." % stage)
    if stage == "DISCOVER":
        from . import profmod
        print(profmod.summary_line(ws, pr, info))
    return allb


def cmd_start(args, ws):
    a = require(ws, args.by, "start_stages", "Starting a stage")
    text = need_text(args, "statement", "Starting a stage")
    pr = ws.project(args.project)
    info = pr.info()
    stage = _stage_arg(args)
    _may_begin(info, stage)
    covers = _covers(info, stage)
    e = pr.journal().append("stage_start", ["project:" + pr.slug, "stage:" + stage], a.decided_by,
                            "Started %s for %s%s" % (stage, info["name"], " (light lane: one combined pass)" if len(covers) > 1 else ""),
                            authority_basis=a.basis, labels=["unsigned"], text=text, extra={"covers": covers})
    for s in covers:
        info["stages"][s] = {"status": "started", "started_seq": e["seq"], "started": iso(), "covers": covers}
    info["current_stage"] = stage
    pr.save_info(info)
    print("%s started (journal line %d)." % (stage, e["seq"]))
    from .concernmod import stage_text
    for s_ in covers:
        t_ = stage_text(pr, s_)
        if t_:
            print(t_)


def cmd_close(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    stage = _stage_arg(args)
    if stage == "OPERATE":
        raise AigError("Operate does not close: controls are proved and watched one by one for as long as the AI system is in use. "
                       "The go decision is recorded with 'operate signoff'; see what stands in the way with 'operate readiness'.")
    st = info["stages"][stage]
    a = resolve_actor(ws, args.by)
    text = None
    if st["status"] == "not_started":
        if not args.without_start:
            raise AigError("%s was never started. If it was done under an earlier arrangement, AI Governance can close it as 'closed without a start decision' (--without-start with a reason)." % stage)
        a = require(ws, args.by, "close_stages", "Closing a stage that has no start decision")
        text = need_text(args, "statement", "Closing a stage without a start decision")
        _may_begin(info, stage)
        covers = _covers(info, stage)
    elif _closed(st):
        raise AigError("%s is already closed." % stage)
    else:
        covers = st.get("covers") or [stage]
        if stage != covers[0]:
            raise AigError("%s is part of one combined pass that closes with %s." % (stage, covers[0]))
        if SEQ[stage] > 0 and not _closed(info["stages"][STAGES[SEQ[stage] - 1]]):
            raise AigError("%s must close before %s can close." % (STAGES[SEQ[stage] - 1], stage))
    open_blocks_ = [x for x in info["blocks"] if not x["lifted"]]
    if open_blocks_ and any(SEQ[c] >= SEQ["ASSESS"] for c in covers):
        raise AigError("%s cannot close while a stage block is in force: %s. AI Governance lifts a block with 'stage lift-block'; closing over it is not an option."
                       % (stage, open_blocks_[0]["reason"]))
    blockers = []
    for s in covers:
        blockers += ["%s: %s" % (s, x) for x in gate(ws, pr, s)]
    if blockers and not args.force_with_reason:
        print("Cannot close %s yet:" % stage)
        for x in blockers:
            print("  - " + x)
        raise AigError("The gate for %s has %d open item(s)." % (stage, len(blockers)))
    labels = ["tool"] if a.is_tool else ["unsigned"]
    if blockers:
        a = require(ws, args.by, "close_stages", "Closing a stage over open gate items")
        text = need_text(args, "force_with_reason", "Closing a stage over open gate items")
        if len(text.split()) < 12:
            print("These items would stay open:")
            for x in blockers:
                print("  - " + x)
            raise AigError("Closing %s over open items needs the decision-maker's reason in their own words: what they accept leaving open, and why. "
                           "A short phrase is not enough (at least a full sentence or two)." % stage)
        labels.append("closed-with-open-items")
    elif a.is_tool is False and text is None:
        text = None
    kind = "stage_close"
    summary = "Closed %s for %s" % (stage, info["name"])
    never_started = st["status"] == "not_started"
    if never_started:
        kind = "stage_close_without_start"
        summary += " without a start decision"
        labels.append("no-start-decision")
    if blockers:
        summary += " with %d open gate item(s)" % len(blockers)
    e = pr.journal().append(kind, ["project:" + pr.slug, "stage:" + stage], a.decided_by, summary,
                            authority_basis=a.basis, labels=labels, text=text,
                            extra={"covers": covers, "open_items": blockers})
    for s in covers:
        info["stages"][s] = dict(info["stages"][s], status="closed_without_start" if never_started else "closed",
                                 closed_seq=e["seq"], closed=iso(), covers=covers)
    info["current_stage"] = stage
    pr.save_info(info)
    print("%s closed (journal line %d)." % (stage, e["seq"]))


def cmd_adopt(args, ws):
    a = require(ws, args.by, "adopt_statement", "Adopting an existing statement as the start decision")
    pr = ws.project(args.project)
    info = pr.info()
    stage = _stage_arg(args)
    if not args.source:
        raise AigError("Give the existing statement as --source <file>.")
    src = check_file(args.source, "statement file")
    text = read_any_text(src)
    _may_begin(info, stage)
    covers = _covers(info, stage)
    e = pr.journal().append("adoption", ["project:" + pr.slug, "stage:" + stage], a.decided_by,
                            "Adopted an existing statement (%s) as the start decision for %s" % (src.name, stage),
                            authority_basis=a.basis, labels=["unsigned", "adopted"], text=text,
                            extra={"source_sha256": sha256_file(src), "source_name": src.name, "covers": covers})
    for s_ in covers:
        info["stages"][s_] = {"status": "started", "started_seq": e["seq"], "started": iso(), "adopted": True, "covers": covers}
    info["current_stage"] = stage
    pr.save_info(info)
    print("%s started by adoption (journal line %d)." % (stage, e["seq"]))


def _print_readiness(ws, pr):
    b, n = readiness(ws, pr)
    print("Readiness for the go decision (worked out now from the records; it changes as controls and incidents change):")
    print("  Required controls verified: %d of %d." % (n["done"], n["required"]))
    if b:
        print("  Standing in the way:")
        for x in b:
            print("    - " + x)
    else:
        print("  Nothing stands in the way.")
    info = pr.info()
    so = info.get("signoffs") or []
    if so:
        l = so[-1]
        print("  Last go decision: %s by %s (journal line %d)%s." % (l["time"][:10], l["by_name"], l["seq"],
                                                                      ", with %d item(s) left open" % len(l["open_items"]) if l.get("open_items") else ""))
    else:
        print("  No go decision has been recorded yet.")
    return b


def cmd_readiness(args, ws):
    pr = ws.project(args.project)
    _print_readiness(ws, pr)


def cmd_signoff(args, ws):
    """The go decision: a person in AI Governance says, in their own words, that the AI system may go ahead (or carry on)
    on what is proved so far. It is an event, not a stage; it can be repeated, and each one is a journal line."""
    a = require(ws, args.by, "close_stages", "Recording the go decision")
    pr = ws.project(args.project)
    info = pr.info()
    if info["stages"]["OPERATE"]["status"] != "started":
        raise AigError("Operate has not started, so there is nothing to sign off yet (stage start --stage OPERATE).")
    open_blocks = [x for x in info["blocks"] if not x["lifted"]]
    if open_blocks:
        raise AigError("A stage block is in force: %s. AI Governance lifts it first ('stage lift-block')." % open_blocks[0]["reason"])
    text = need_text(args, "statement", "Recording the go decision")
    blockers, n = readiness(ws, pr)
    labels = ["unsigned"]
    if blockers:
        if len(text.split()) < 12:
            print("These items would stay open:")
            for x in blockers:
                print("  - " + x)
            raise AigError("Going ahead over open items needs the decision-maker's reason in their own words: what they accept leaving open, and why. "
                           "A short phrase is not enough (at least a full sentence or two).")
        labels.append("signed-off-with-open-items")
    summary = "Go decision for %s: %d of %d required controls verified%s" % (
        info["name"], n["done"], n["required"], (", %d item(s) left open" % len(blockers)) if blockers else ", nothing left open")
    e = pr.journal().append("signoff", ["project:" + pr.slug, "stage:OPERATE"], a.decided_by, summary,
                            authority_basis=a.basis, labels=labels, text=text,
                            extra={"open_items": blockers, "required": n["required"], "verified": n["done"]})
    info.setdefault("signoffs", []).append({"seq": e["seq"], "time": iso(), "by": a.decided_by, "by_name": a.name,
                                            "open_items": blockers, "required": n["required"], "verified": n["done"]})
    pr.save_info(info)
    if blockers:
        items = pr.load("concerns", [])
        cid = pr.next_id("CON", "CON")
        items.append({"id": cid, "kind": "concern",
                      "text": "The go decision of %s (journal line %d) was recorded over open items: %s They stay open until dealt with." % (
                          today(), e["seq"], " ".join(blockers)),
                      "carry_to": "OPERATE", "raised_by": "AIGRCeler (its own reading)", "asked_to_keep_by": None,
                      "raised": iso(), "status": "open", "resolved": None, "resolution": None})
        pr.save("concerns", items)
        print("Go decision recorded (journal line %d) with %d item(s) left open; they are kept as %s." % (e["seq"], len(blockers), cid))
    else:
        print("Go decision recorded (journal line %d). Every required control is verified and no high incident is open." % e["seq"])
