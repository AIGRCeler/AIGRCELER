"""The chase list and the review schedule. Both only read the records and say what is owed and what to do next.
AIGRCeler cannot send anything: a message counts as sent when a person says so."""
import datetime

from .core import AigError, iso, today, parse_date, require, need_text, write_text
from . import evidmod

REVIEW_DAYS = {"full": 90, "standard": 180, "light": 365}
WAITING_STATES = ("approved", "assigned", "implementing", "rejected", "expired", "evidenced")


def _days(a, b):
    """Whole days from date a to date b (both YYYY-MM-DD)."""
    return (datetime.date.fromisoformat(b[:10]) - datetime.date.fromisoformat(a[:10])).days


def _name(ws):
    return {p["id"]: p["name"] for p in ws.load("people", [])}


def _short(text, n=56):
    text = " ".join(str(text).split())
    if len(text) <= n:
        return text
    cut = text[:n].rsplit(" ", 1)[0]
    return (cut or text[:n]) + "..."


def _subject(pr, r):
    """A request's own subject line: the first line of the message that was written for it."""
    try:
        with open(pr.root / r["message_file"], encoding="utf-8") as f:
            line = f.readline().lstrip("# ").strip()
        if line:
            return line
    except (OSError, KeyError, TypeError):
        pass
    return (r.get("type") or "request").replace("_", " ")


def build(ws, pr):
    """Return a list of rows: who it is about, what, how late, which side must act, and the next step."""
    names = _name(ws)
    reqs = {r["id"]: r for r in pr.load("requests", [])}
    evs = pr.load("evidence", [])
    td = today()
    rows = []
    for c in pr.all_controls():
        if c["state"] not in WAITING_STATES:
            continue
        d = c["definition"]
        pr_ = 0 if d.get("critical") else 1 if d.get("launch_required") else 2
        who = c.get("owner")
        due = c.get("due")
        late = max(0, _days(due, td)) if due and td > due else 0
        r = reqs.get(c.get("request")) if c.get("request") else None
        nm = names.get(who, who)
        if c["state"] == "approved":
            side, action = "us", "No owner yet. Assign one (control assign)."
            who = who or "(no owner yet)"
        elif c["state"] == "evidenced":
            side = "verifier"
            action = "Evidence is filed. Someone who neither owns the control nor sent the evidence must judge it (finding record)."
        elif c["state"] == "rejected":
            side, action = "owner", "The evidence was not accepted (see the finding). Ask %s for better evidence." % nm
        elif c["state"] == "expired":
            why = ""
            for e in reversed([e for e in evs if e.get("control") == c["id"] and e.get("status") == "expired"]):
                why = e.get("expired_reason") or ""
                break
            side = "owner"
            action = "Evidence expired%s. Ask %s for fresh evidence (request create)." % ((": " + why) if why else "", nm)
        elif r is None or r["status"] == "withdrawn":
            side, action = "us", "No message is out for this control. Write one for %s (request create)." % nm
        elif r["status"] == "open" and not r.get("delivered"):
            side, action = "us", "Message %s is written but not marked as sent. Send it, then tell the tool (control mark-sent)." % r["id"]
        elif r["status"] == "open":
            asked = (r["delivered"].get("time") or r.get("sent") or "")[:10]
            side = "owner"
            action = "Asked on %s (%s); waiting for the answer%s." % (asked, r["id"], (", %d day(s) ago" % _days(asked, td)) if asked else "")
        else:
            side = "owner"
            action = "A reply came to %s but no evidence is filed for this control yet. File it, or ask again." % r["id"]
        rows.append({"who": who or "(no owner yet)", "kind": "control", "id": c["id"], "title": c["title"], "prio": pr_,
                     "due": due, "late": late, "side": side, "action": action})
    shown = {r_["id"] for r_ in rows if r_["side"] == "us" and r_["kind"] == "control"}
    for r in reqs.values():
        if r["status"] != "open":
            continue
        if r.get("controls") and (r.get("delivered") or r["id"] in shown):
            continue   # the controls it covers carry it
        due = r.get("due")
        late = max(0, _days(due, td)) if due and td > due else 0
        if not r.get("delivered"):
            side, action = "us", "Message %s to %s is written but not marked as sent. Send it, then tell the tool (control mark-sent)." % (r["id"], names.get(r["to"], r["to"]))
        else:
            asked = (r["delivered"].get("time") or "")[:10]
            side, action = "owner", "Asked on %s (%s); waiting for the answer." % (asked, r["id"])
        rows.append({"who": r["to"], "kind": "request", "id": r["id"], "title": _subject(pr, r),
                     "prio": 3, "due": due, "late": late, "side": side, "action": action})
    rows.sort(key=lambda x: (-x["late"], x["prio"], x["due"] or "9999", x["id"]))
    return rows


def review_status(ws, pr):
    """When the next review is due. None until Operate has started."""
    info = pr.info()
    op = info["stages"].get("OPERATE", {})
    if op.get("status") != "started":
        return None
    custom = info.get("review_every_days")
    every = custom or REVIEW_DAYS.get(info.get("lane"), 180)
    revs = pr.load("reviews", [])
    last = max((r["time"][:10] for r in revs), default=None)
    base = last or (op.get("started") or iso())[:10]
    due = (datetime.date.fromisoformat(base) + datetime.timedelta(days=every)).isoformat()
    why = []
    since = last or base
    for i in pr.load("incidents", []):
        if i["status"] == "closed" and i["severity"] in ("high", "critical") and (i.get("closed") or "")[:10] >= since:
            why.append("incident %s (%s) closed since the last review" % (i["id"], i["severity"]))
    return {"every": every, "custom": bool(custom), "last": last, "base": base, "due": due,
            "left": _days(today(), due), "reasons": why}


def review_line(st):
    if not st:
        return None
    if st["left"] < 0:
        t = "Review overdue: it was due %s (%d day(s) ago)" % (st["due"], -st["left"])
    elif st["left"] == 0:
        t = "Review due today"
    else:
        t = "Next review due %s (in %d day(s))" % (st["due"], st["left"])
    t += "; %s, every %d days%s." % ("last recorded " + st["last"] if st["last"] else "none recorded yet", st["every"], " (set by AI Governance)" if st["custom"] else " (default for the lane)")
    if st["reasons"]:
        t += " A review is also called for: " + "; ".join(st["reasons"]) + "."
    return t


def render(ws, pr, only=None):
    names = _name(ws)
    rows = build(ws, pr)
    if only:
        rows = [r for r in rows if r["who"] == only]
    info = pr.info()
    out = ["Chase list for %s, %s. Nothing here has been sent: AIGRCeler cannot send; a message counts as sent when a person says so." % (info["name"], today())]
    rl = review_line(review_status(ws, pr))
    if rl:
        out.append(rl)
    us = [r for r in rows if r["side"] == "us"]
    out.append("")
    out.append("Waiting on us (%d):" % len(us))
    if not us:
        out.append("  Nothing.")
    for r in us:
        out.append("  %s %s: %s%s" % (r["id"], _short(r["title"], 60), r["action"], (" Due %s." % r["due"]) if r["due"] else ""))
    ver = [r for r in rows if r["side"] == "verifier"]
    if ver:
        out.append("")
        out.append("Waiting for a verifier (%d):" % len(ver))
        for r in ver:
            out.append("  %s %s: %s" % (r["id"], _short(r["title"], 60), r["action"]))
    owners = sorted({r["who"] for r in rows if r["side"] == "owner"}, key=lambda w: (-sum(1 for r in rows if r["who"] == w and r["side"] == "owner" and r["late"]), names.get(w, w)))
    for w in owners:
        mine = [r for r in rows if r["who"] == w and r["side"] == "owner"]
        late = [r for r in mine if r["late"]]
        out.append("")
        out.append("%s: %d open, %d late" % (names.get(w, w), len(mine), len(late)))
        for r in mine:
            tag = {0: "critical", 1: "required before launch"}.get(r["prio"], "")
            out.append("  %s %s%s - due %s%s - %s" % (r["id"], _short(r["title"]), (" [%s]" % tag) if tag else "",
                                                     r["due"] or "no date", (" (%d day(s) late)" % r["late"]) if r["late"] else "", r["action"]))
    total = len(rows)
    out.append("")
    out.append("%d item(s) in all: %d waiting on us, %d on a verifier, %d on owners, %d of them late." % (
        total, len(us), len(ver), sum(1 for r in rows if r["side"] == "owner"), sum(1 for r in rows if r["late"])))
    return "\n".join(out) + "\n"


def cmd_chase(args, ws):
    pr = ws.project(args.project)
    evidmod.refresh(ws, pr)
    only = None
    if args.person:
        ids = {p["id"] for p in ws.load("people", [])}
        if args.person not in ids:
            raise AigError("'%s' is not in the people directory." % args.person)
        only = args.person
    text = render(ws, pr, only)
    print(text, end="")
    if not only:
        write_text(pr.p("00-status", "7-chase-list.md"), "# Chase list\n\n```\n" + text + "```\n")


def cmd_review_due(args, ws):
    pr = ws.project(args.project)
    st = review_status(ws, pr)
    if not st:
        print("Operate has not started, so no review is due yet.")
        return
    print(review_line(st))


def cmd_review_schedule(args, ws):
    a = require(ws, args.by, "start_stages", "Setting how often the AI system is reviewed")
    pr = ws.project(args.project)
    if args.days is None:
        raise AigError("Say how often, in days (--days), for example 90.")
    if not 14 <= args.days <= 730:
        raise AigError("A review every %d days is outside what makes sense (14 to 730 days)." % args.days)
    text = need_text(args, "statement", "Setting how often the AI system is reviewed")
    info = pr.info()
    old = info.get("review_every_days")
    e = pr.journal().append("review_schedule", ["project:" + pr.slug], a.decided_by,
                            "Review every %d days for %s%s" % (args.days, info["name"], (" (was %d)" % old) if old else ""),
                            authority_basis=a.basis, labels=["unsigned"], text=text, extra={"days": args.days})
    info["review_every_days"] = args.days
    pr.save_info(info)
    print("Reviews are now due every %d days (journal line %d)." % (args.days, e["seq"]))
    st = review_status(ws, pr)
    if st:
        print(review_line(st))
