"""Monitoring: indicators, incidents with response clocks, obligations,
containment actions, reviews."""
import json
from pathlib import Path

from .core import clip
from .core import (
    AigError, SEVERITIES, iso, now, parse_dt, add_days, add_business_days, require, need_text,
    resolve_actor, split_list, write_text, write_json, read_json, slug, today, finite, parse_date, read_any_text,
)
from . import ctrlmod, riskmod


# --------------------------------------------------------- indicators ----
def _status(ind):
    v = ind.get("current")
    if v is None:
        return "no_reading"
    import math
    if not math.isfinite(v):
        return "out_of_tolerance"   # a reading that is not a number is never treated as fine
    if ind.get("min") is not None and v < ind["min"]:
        return "out_of_tolerance"
    if ind.get("max") is not None and v > ind["max"]:
        return "out_of_tolerance"
    return "in_tolerance"


def cmd_ind_set(args, ws):
    pr = ws.project(args.project)
    c = pr.get_control(args.control)
    if c["state"] not in ("verified", "monitored"):
        raise AigError("Indicators watch controls that are verified. %s is %s." % (c["id"], c["state"]))
    inds = pr.load("indicators", [])
    if not args.metric:
        raise AigError("Say what is measured (--metric).")
    if any(i["control"] == c["id"] and i["metric"] == args.metric for i in inds):
        raise AigError("That control already has an indicator for this measure.")
    base = finite(args.baseline, "baseline") if args.baseline is not None else None
    lo = finite(args.min, "minimum") if args.min is not None else None
    hi = finite(args.max, "maximum") if args.max is not None else None
    if lo is None and hi is None:
        raise AigError("Give the tolerated range: --min, --max or both.")
    if lo is not None and hi is not None and lo > hi:
        raise AigError("The minimum is higher than the maximum.")
    ind = {"id": pr.next_id("IND", "IND"), "control": c["id"], "metric": args.metric,
           "baseline": base, "min": lo, "max": hi, "current": base,
           "unit": args.unit or "", "updated": iso(), "history": []}
    ind["status"] = _status(ind)
    inds.append(ind)
    pr.save("indicators", inds)
    if c["state"] == "verified":
        ctrlmod.log(c, "tool:aigrceler", "verified", "monitored", "indicator %s set" % ind["id"])
    c["suspended"] = any(i["control"] == c["id"] and i["status"] == "out_of_tolerance" for i in inds)
    pr.save_control(c)
    riskmod.recompute(ws, pr)
    print("Indicator %s watching %s (%s)." % (ind["id"], c["title"], ind["status"]))
    if ind["status"] == "out_of_tolerance":
        print("ALERT: the starting reading is already outside the tolerated range, so credit for %s is suspended." % c["id"])


def cmd_ind_update(args, ws):
    pr = ws.project(args.project)
    inds = pr.load("indicators", [])
    ind = next((i for i in inds if i["id"] == args.id), None)
    if not ind:
        raise AigError("No indicator %s." % args.id)
    old = ind["status"]
    value = finite(args.value, "reading")
    ind["history"].append({"time": ind["updated"], "value": ind["current"], "status": old})
    ind["current"] = value
    ind["updated"] = iso()
    ind["status"] = _status(ind)
    pr.save("indicators", inds)
    lf = pr.p("logs", "indicator-log.jsonl")
    with open(lf, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"time": iso(), "indicator": ind["id"], "control": ind["control"], "value": value, "status": ind["status"]}) + "\n")
    c = pr.get_control(ind["control"])
    c["suspended"] = any(i["control"] == c["id"] and i["status"] == "out_of_tolerance" for i in inds)
    pr.save_control(c)
    s = riskmod.recompute(ws, pr)
    print("%s = %s (%s)." % (ind["metric"], value, ind["status"]))
    if ind["status"] == "out_of_tolerance":
        print("ALERT: credit for %s is suspended while this stays out of tolerance. Residual risk now %.1f (%s). "
              "Guardian should decide whether this is an incident." % (c["id"], s["residual_total"], s["residual_band"]))
    elif old == "out_of_tolerance":
        print("Back in tolerance; credit restored.")


def cmd_ind_list(args, ws):
    pr = ws.project(args.project)
    for i in pr.load("indicators", []):
        print("%s  %-8s %-18s now %s (range %s to %s) %s" % (i["id"], i["control"], i["status"], i["current"], i["min"], i["max"], i["metric"]))


# ----------------------------------------------------------- incidents ----
def _deadline(ws, severity, start):
    clk = ws.settings()["incident_clocks"][severity]
    if "escalate_hours" in clk:
        return start + __import__("datetime").timedelta(hours=clk["escalate_hours"])
    return add_business_days(start, clk["escalate_business_days"])


def _write_incident_view(pr, inc):
    lines = ["# Incident: %s" % inc["title"], "",
             "Severity: **%s** | Status: **%s** | Opened: %s" % (inc["severity"], inc["status"], inc["opened"][:16].replace("T", " ")),
             "Must reach AI Governance and the response owner by: %s%s" % (inc["escalate_due"][:16].replace("T", " "), " (done)" if inc.get("acknowledged") else ""),
             "Controls involved: %s" % (", ".join(inc["controls"]) or "none named"), "",
             "## What happened", "", inc["description"], "", "## Timeline", ""]
    for t in inc["timeline"]:
        lines.append("- %s: %s (%s)" % (t["time"][:16].replace("T", " "), t["note"], t["by"]))
    if inc.get("retrospective"):
        lines += ["", "## Retrospective", "", inc["retrospective"]]
    write_text(pr.p("incidents", inc["id"] + ".md"), "\n".join(lines) + "\n")


def cmd_inc_open(args, ws):
    pr = ws.project(args.project)
    if not args.title:
        raise AigError("Give the incident a title (--title).")
    if not args.severity or args.severity.lower() not in SEVERITIES:
        raise AigError("Severity must be one of: %s (--severity)." % ", ".join(SEVERITIES))
    sev = args.severity.lower()
    if args.owner and args.owner not in {p["id"] for p in ws.load("people", [])}:
        raise AigError("'%s' is not in the people directory." % args.owner)
    a = resolve_actor(ws, args.by)
    text = None
    if not a.is_tool:
        # an incident declared in a person's name carries what that person said
        text = need_text(args, "statement", "Declaring an incident in a person's name")
    t = now()
    iid = pr.next_id("INC", "INC")
    inc = {"id": iid, "title": args.title, "severity": sev, "status": "open", "opened": iso(t),
           "description": args.description or "", "controls": split_list(args.controls),
           "escalate_due": iso(_deadline(ws, sev, t)), "acknowledged": None,
           "response_owner": args.owner, "timeline": [{"time": iso(t), "note": "Incident opened: " + clip(args.description or args.title, 160), "by": a.decided_by}],
           "notices": [], "obligations": [], "containment": [], "retrospective": None, "outcome": None,
           "reportable": bool(args.reportable)}
    incs = pr.load("incidents", [])
    incs.append(inc)
    pr.save("incidents", incs)
    _write_incident_view(pr, inc)
    pr.journal().append("incident_declared", [iid] + ["ctl:" + x for x in inc["controls"]], a.decided_by,
                        "Incident %s opened (%s): %s" % (iid, sev, args.title), authority_basis=a.basis,
                        labels=["tool"] if a.is_tool else ["unsigned"], text=text)
    print("Incident %s opened%s, severity %s. AI Governance and the response owner must be told by %s." % (
        iid, " by AIGRCeler (no person declared it; AI Governance is to be told at once)" if a.is_tool else "", sev, inc["escalate_due"][:16].replace("T", " ")))
    if inc["reportable"]:
        print("Marked possibly reportable: check regulator notice periods and add each as an obligation.")


def _get_inc(pr, iid):
    incs = pr.load("incidents", [])
    inc = next((i for i in incs if i["id"] == iid), None)
    if not inc:
        raise AigError("No incident %s." % iid)
    return incs, inc


def cmd_inc_update(args, ws):
    pr = ws.project(args.project)
    incs, inc = _get_inc(pr, args.id)
    a = resolve_actor(ws, args.by)
    if inc["status"] == "closed":
        raise AigError("This incident is closed.")
    if args.note:
        inc["timeline"].append({"time": iso(), "note": args.note, "by": a.decided_by})
    if args.severity:
        sev = args.severity.lower()
        if sev not in SEVERITIES:
            raise AigError("Severity must be one of: %s." % ", ".join(SEVERITIES))
        inc["timeline"].append({"time": iso(), "note": "Severity changed from %s to %s" % (inc["severity"], sev), "by": a.decided_by})
        inc["severity"] = sev
    if args.owner:
        if args.owner not in {p["id"] for p in ws.load("people", [])}:
            raise AigError("'%s' is not in the people directory." % args.owner)
        inc["response_owner"] = args.owner
    pr.save("incidents", incs)
    _write_incident_view(pr, inc)
    print("Updated.")


def cmd_inc_escalate(args, ws):
    pr = ws.project(args.project)
    incs, inc = _get_inc(pr, args.id)
    a = resolve_actor(ws, args.by)
    text = ("An incident has been opened on the AI system \"%s\".\n\nWhat happened: %s\nSeriousness: %s\n\n"
            "Please confirm that you have seen this, and tell us what you are doing about it." % (
                pr.info()["name"], inc["description"] or inc["title"], inc["severity"]))
    who = split_list(args.to)
    if not who:
        raise AigError("Say who must be told (--to <person id>, or several separated by commas). Nothing was written.")
    for person in who:
        ctrlmod.person_dir(ws, pr, person)
        r = ctrlmod.cmd_request_create(type("A", (), dict(project=pr.slug, to=person, type="notice",
                                                          subject="Incident: " + inc["title"], text=text,
                                                          controls="", due=None))(), ws)
        inc["notices"].append({"to": person, "time": iso(), "by": a.decided_by})
    inc["timeline"].append({"time": iso(), "note": "Notice written for %s (not sent: AIGRCeler cannot send; it counts as sent when a person says so)" % ", ".join(who), "by": a.decided_by})
    pr.save("incidents", incs)
    _write_incident_view(pr, inc)
    print("A notice is written for %s. It has NOT been sent; AI Governance sends it and then says so." % ", ".join(ctrlmod.person_name(ws, x) for x in who))


def cmd_inc_ack(args, ws):
    pr = ws.project(args.project)
    incs, inc = _get_inc(pr, args.id)
    a = require(ws, args.by, "close_incidents", "Confirming that AI Governance has been told")
    inc["acknowledged"] = {"by": a.person, "time": iso()}
    inc["timeline"].append({"time": iso(), "note": "AI Governance confirmed they were told", "by": a.decided_by})
    pr.save("incidents", incs)
    _write_incident_view(pr, inc)
    late = parse_dt(inc["acknowledged"]["time"]) > parse_dt(inc["escalate_due"])
    pr.journal().append("incident_acknowledged", ["project:" + pr.slug, inc["id"]], a.decided_by,
                        "%s confirmed AI Governance was told about %s%s" % (a.name, inc["id"], " (after the response clock ran out)" if late else " (within the response clock)"),
                        authority_basis=a.basis, labels=["unsigned"])
    print("Recorded%s." % (" (after the response clock ran out)" if late else ", within the response clock"))


def cmd_inc_close(args, ws):
    a = require(ws, args.by, "close_incidents", "Closing an incident")
    text = need_text(args, "statement", "Closing an incident")
    pr = ws.project(args.project)
    incs, inc = _get_inc(pr, args.id)
    if inc["status"] == "closed":
        raise AigError("Already closed.")
    open_ob = [o for o in pr.load("obligations", []) if o.get("incident") == inc["id"] and o["status"] == "open"]
    if open_ob:
        raise AigError("Open regulator or customer obligations remain on this incident: %s." % ", ".join(o["id"] for o in open_ob))
    if not args.retrospective:
        raise AigError("Closing needs a short retrospective: what happened, why, what changes (--retrospective).")
    p = Path(args.retrospective)
    try:
        inc["retrospective"] = read_any_text(p) if len(args.retrospective) < 240 and p.exists() and p.is_file() else args.retrospective
    except (OSError, ValueError, AigError):
        inc["retrospective"] = args.retrospective
    inc["status"] = "closed"
    inc["outcome"] = args.outcome or ""
    inc["closed"] = iso()
    inc["closed_by"] = a.decided_by
    inc["lesson"] = args.lesson or None
    inc["timeline"].append({"time": iso(), "note": "Incident closed", "by": a.decided_by})
    pr.save("incidents", incs)
    _write_incident_view(pr, inc)
    pr.journal().append("incident_closed", [inc["id"]], a.decided_by,
                        "Incident %s closed: %s" % (inc["id"], args.outcome or inc["title"]),
                        authority_basis=a.basis, labels=["unsigned"], text=text + "\n\nRetrospective:\n" + inc["retrospective"])
    if args.lesson:
        pid = ws.next_id("P", "P")
        write_json(ws.p("catalog", "proposals", pid + ".json"), {
            "id": pid, "source": "incident", "ref": inc["id"], "kind": "review",
            "target": (inc["controls"] or [None])[0], "change": {}, "reason": args.lesson,
            "status": "open", "created": iso(), "proposed_by": a.decided_by, "projects_affected": [pr.slug]})
        print("Lesson filed as catalog proposal %s." % pid)
    print("Incident closed.")


def cmd_inc_clocks(args, ws):
    slugs = [args.project] if args.project else ws.project_slugs()
    over = 0
    for sl in slugs:
        pr = ws.project(sl)
        for inc in pr.load("incidents", []):
            if inc["status"] == "open" and not inc.get("acknowledged"):
                late = now() > parse_dt(inc["escalate_due"])
                over += late
                print("%s %s [%s] %s: AI Governance must confirm by %s%s" % (
                    sl, inc["id"], inc["severity"], inc["title"], inc["escalate_due"][:16].replace("T", " "), "  ** OVERDUE **" if late else ""))
        for o in pr.load("obligations", []):
            if o["status"] == "open":
                late = bool(o.get("due")) and o["due"] < today()
                over += late
                print("%s %s obligation to %s due %s%s" % (sl, o["id"], o["authority"], o.get("due") or "(no date)", "  ** OVERDUE **" if late else ""))
    print("%d overdue." % over)


def cmd_inc_list(args, ws):
    pr = ws.project(args.project)
    for i in pr.load("incidents", []):
        print("%s  %-9s %-8s %s" % (i["id"], i["status"], i["severity"], i["title"]))


# --------------------------------------------- obligations, containment ----
def cmd_ob_add(args, ws):
    pr = ws.project(args.project)
    if not args.title or not args.authority:
        raise AigError("An obligation needs a title (--title) and who it is owed to (--authority).")
    due = parse_date(args.due, "due date")
    if not due:
        raise AigError("An obligation needs a due date (--due YYYY-MM-DD).")
    a = resolve_actor(ws, args.by)
    obs = pr.load("obligations", [])
    oid = pr.next_id("OB", "OB")
    obs.append({"id": oid, "title": args.title, "authority": args.authority, "due": due,
                "incident": args.incident, "status": "open", "opened": iso()})
    pr.save("obligations", obs)
    pr.journal().append("obligation", [oid], a.decided_by, "Obligation to %s due %s: %s" % (args.authority, due, args.title),
                        authority_basis=a.basis, labels=["tool"] if a.is_tool else ["unsigned"])
    print("Obligation %s recorded, due %s." % (oid, due))


def cmd_ob_close(args, ws):
    pr = ws.project(args.project)
    obs = pr.load("obligations", [])
    o = next((x for x in obs if x["id"] == args.id), None)
    if not o:
        raise AigError("No obligation %s." % args.id)
    a = require(ws, args.by, "close_incidents", "Closing an obligation")
    if not args.note:
        raise AigError("Say how it was met (--note).")
    o.update(status="met", closed=iso(), note=args.note)
    pr.save("obligations", obs)
    pr.journal().append("obligation", [o["id"]], a.decided_by, "Obligation met: %s" % o["title"], authority_basis=a.basis, labels=["unsigned"], text=args.note)
    print("Closed.")


def cmd_ct_add(args, ws):
    pr = ws.project(args.project)
    a = require(ws, args.by, "close_incidents", "Putting a containment action in place")
    text = need_text(args, "statement", "A containment action")
    ends = parse_date(args.ends, "end date")
    if not args.title or not ends:
        raise AigError("A containment action needs a title (--title) and an end date (--ends YYYY-MM-DD).")
    cts = pr.load("containment", [])
    cid = pr.next_id("CT", "CT")
    cts.append({"id": cid, "title": args.title, "ends": ends, "incident": args.incident,
                "control": args.control, "status": "active", "started": iso(),
                "request": args.request, "confirmed": None})
    pr.save("containment", cts)
    pr.journal().append("containment", [cid], a.decided_by, "Containment action until %s: %s" % (ends, args.title),
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Containment %s recorded; it must end or be renewed by %s." % (cid, ends))
    print("It is a decision, not yet a fact: nobody has said it is in place. Word it as the measure, not as done. When the owner says it is, run: containment confirm --id %s --source \"<who said it>\"." % cid)


def cmd_ct_confirm(args, ws):
    pr = ws.project(args.project)
    cts = pr.load("containment", [])
    c = next((x for x in cts if x["id"] == args.id), None)
    if not c:
        raise AigError("No containment action %s." % args.id)
    if not args.source or len(str(args.source).split()) < 2:
        raise AigError("Say who told you it is in place (--source), for example \"Tamsin Clarke, reply to REQ-004\". It is not confirmed on anyone's guess.")
    c["confirmed"] = {"source": str(args.source).strip(), "at": iso()}
    pr.save("containment", cts)
    pr.journal().append("containment_confirmed", [c["id"]], "tool:aigrceler", "Containment %s reported in place by %s" % (c["id"], c["confirmed"]["source"]),
                        labels=["tool"])
    print("Recorded that %s is in place, as reported by %s. AIGRCeler has not checked it." % (c["id"], c["confirmed"]["source"]))


def cmd_ct_end(args, ws):
    pr = ws.project(args.project)
    a = require(ws, args.by, "close_incidents", "Ending a containment action")
    cts = pr.load("containment", [])
    c = next((x for x in cts if x["id"] == args.id), None)
    if not c:
        raise AigError("No containment action %s." % args.id)
    c.update(status="ended", ended=iso())
    pr.save("containment", cts)
    pr.journal().append("containment", [c["id"]], a.decided_by, "Containment ended: %s" % c["title"], authority_basis=a.basis, labels=["unsigned"])
    print("Ended.")


# ------------------------------------------------------------- reviews ----
def cmd_review_add(args, ws):
    pr = ws.project(args.project)
    a = resolve_actor(ws, args.by)
    revs = pr.load("reviews", [])
    rid = pr.next_id("REV", "REV")
    revs.append({"id": rid, "kind": args.kind, "summary": args.summary, "time": iso(), "by": a.decided_by,
                 "cycle": pr.info().get("cycle", 1)})
    pr.save("reviews", revs)
    from .chasemod import review_status, review_line
    print("Review %s recorded." % rid)
    rl = review_line(review_status(ws, pr))
    if rl:
        print(rl)
