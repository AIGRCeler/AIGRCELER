"""Controls on an AI system and the requests that go to their owners."""
import re
import shutil
from pathlib import Path

from .core import clip
from .core import (
    AigError, DOMAINS, DOMAIN_TITLES, LANES, iso, today, slug, require, need_text, resolve_actor,
    split_list, write_text, write_json, read_json, domain_of, is_governance_person, parse_dt,
    active_assignments, TOOL, add_days, now, parse_date, check_file, read_any_text, default_due_date,
)
from .catalogmod import load_defs
from .projmod import escalators

TRANSITIONS_TOOL = {("assigned", "implementing"), ("rejected", "implementing")}


def active_flags(info):
    f = [k for k, v in info["flags"].items() if v]
    if info.get("consequential_actions"):
        f.append("consequential_actions")
    if len(info.get("downstream_dependencies") or []) > 3:
        f.append("many_dependencies")
    return f


def applicable(defn, info):
    ap = defn["applies"]
    modes = ap.get("modes") or ["any"]
    if "any" not in modes and info["sourcing_mode"] not in modes:
        return False
    if info["lane"] not in (ap.get("lanes") or LANES):
        return False
    af = active_flags(info)
    rf = ap.get("requires_flags") or []
    if rf and not any(f in af for f in rf):
        return False
    if any(f in af for f in (ap.get("excludes_flags") or [])):
        return False
    return True


def log(c, by, frm, to, why=""):
    c.setdefault("history", []).append({"time": iso(), "by": by, "from": frm, "to": to, "why": why})
    c["state"] = to


def person_name(ws, pid):
    for p in ws.load("people", []):
        if p["id"] == pid:
            return p["name"]
    return pid


def default_owner(ws, role):
    gov = {r["id"] for r in ws.load("roles", []) if r.get("governance")}
    if role in gov:
        return None
    for a in active_assignments(ws):
        if a["role"] == role and a["kind"] == "primary":
            return a["person"]
    return None


# ------------------------------------------------------------- draft ----
def cmd_draft(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    s = ws.settings()
    if not s.get("catalog_version"):
        raise AigError("The company has not adopted a control catalog yet.")
    if not info.get("sourcing_mode"):
        raise AigError("Say how the AI system is sourced first (project set --sourcing-mode).")
    if not info.get("lane"):
        raise AigError("The lane is not decided yet. Run the screening and ask AI Governance to set the lane.")
    defs = load_defs(ws)
    made, skipped = [], 0
    for d in defs.values():
        if args.domain and domain_of(d["id"]) != args.domain.upper():
            continue
        if not applicable(d, info):
            continue
        if pr.has_control(d["id"]):
            skipped += 1
            continue
        owner = default_owner(ws, d["owner_role"])
        c = {"id": d["id"], "title": d["title"], "domain": domain_of(d["id"]), "state": "drafted",
             "definition": d, "catalog_version": s["catalog_version"], "owner": None,
             "proposed_owner": owner, "owner_role": d["owner_role"], "due": None, "tailoring": "",
             "approved_by": None, "approved_seq": None, "request": None, "evidence": [],
             "current_evidence": None, "strength": None, "suspended": False, "history": []}
        log(c, "tool:aigrceler", None, "drafted", "selected for %s lane, %s" % (info["lane"], info["sourcing_mode"]))
        pr.save_control(c)
        made.append(c["id"])
    print("Drafted %d controls (%d already there). They are proposals until AI Governance approves them." % (len(made), skipped))
    from .catalogmod import behind_starter
    bs = behind_starter(ws)
    if bs:
        print("NOTE: the company's catalog (version %s) does not have %d control(s) this product now ships with: %s. "
              "Adding them is AI Governance's decision ('catalog sync-starter'); then run 'control draft' again so they are drafted too." % (
                  s.get("catalog_version"), len(bs), ", ".join(bs)))


def cmd_owners(args, ws):
    """Who is proposed or named to own the controls on this system, with counts taken from the records."""
    pr = ws.project(args.project)
    cs = [c for c in pr.all_controls() if c["state"] not in ("retired", "rejected")]
    by = {}
    for c in cs:
        by.setdefault(c.get("owner") or c.get("proposed_owner") or None, []).append(c)
    print("%d control(s) on %s." % (len(cs), pr.info()["name"]))
    for who, lst in sorted(by.items(), key=lambda kv: -len(kv[1])):
        if who is None:
            print("- No owner proposed: %d control(s): %s" % (len(lst), ", ".join(sorted(c["id"] for c in lst))))
            continue
        named = sum(1 for c in lst if c.get("owner"))
        crit = sum(1 for c in lst if c["definition"].get("critical"))
        gov = is_governance_person(ws, who)
        exs = sorted({c["exception"] for c in lst if c.get("exception")})
        uncovered = [c["id"] for c in lst if not c.get("exception")]
        if gov and exs and not uncovered:
            note = "; holds an AI Governance role, and exception %s covers all of these" % ", ".join(exs)
        elif gov and exs:
            note = "; holds an AI Governance role: exception %s covers some, but not %s" % (", ".join(exs), ", ".join(sorted(uncovered)))
        elif gov:
            note = "; holds an AI Governance role, so an exception must be recorded before they can own any"
        else:
            note = ""
        print("- %s: %d control(s)%s%s%s" % (person_name(ws, who), len(lst),
              (" (%d named, %d proposed)" % (named, len(lst) - named)) if named else " (proposed)",
              ", %d critical" % crit if crit else "", note))
        print("    %s" % ", ".join(sorted(c["id"] for c in lst)))


def cmd_applies(args, ws):
    """Why a catalog control is, or is not, among this system's controls. Run it before saying a control was left out by mistake."""
    pr = ws.project(args.project)
    info = pr.info()
    defs = load_defs(ws)
    ids = [i.upper() for i in split_list(args.ids)]
    if not ids:
        raise AigError("Say which controls (--ids MD-04,EA-03).")
    for cid in ids:
        d = defs.get(cid)
        if not d:
            print("%s: not in the company's catalog." % cid)
            continue
        ap = d["applies"]
        why = []
        modes = ap.get("modes") or ["any"]
        if "any" not in modes and info.get("sourcing_mode") not in modes:
            why.append("it is for systems that are %s; this one is '%s'" % (" or ".join(modes), info.get("sourcing_mode")))
        if info.get("lane") not in (ap.get("lanes") or LANES):
            why.append("it is for the %s lane(s); this system is on the %s lane" % (", ".join(ap.get("lanes") or LANES), info.get("lane")))
        af = active_flags(info)
        rf = ap.get("requires_flags") or []
        if rf and not any(f in af for f in rf):
            why.append("it needs at least one of these facts to be true of the system: %s" % ", ".join(rf))
        ex = [f for f in (ap.get("excludes_flags") or []) if f in af]
        if ex:
            why.append("it does not apply when: %s" % ", ".join(ex))
        mine = pr.has_control(cid)
        if mine:
            c = pr.get_control(cid)
            print("%s (%s): on this system, %s%s." % (cid, d["title"], c["state"], ", owner %s" % c["owner"] if c.get("owner") else ""))
        elif why:
            print("%s (%s): not on this system on purpose: %s." % (cid, d["title"], "; and ".join(why)))
        else:
            print("%s (%s): it applies to this system but is not among its controls. Run 'control draft' (the catalog may have been updated since)." % (cid, d["title"]))
        deps = d.get("depends_on") or []
        if deps:
            print("    Its catalog card says it depends on %s (the engine does not enforce this; a dependency that does not apply to this system is carried by whatever control covers the same work here)." % ", ".join(deps))


def _select(pr, args):
    cs = pr.all_controls()
    if args.ids:
        ids = split_list(args.ids)
        out = []
        for i in ids:
            out.append(pr.get_control(i))
        return out
    if getattr(args, "all_drafted", False):
        return [c for c in cs if c["state"] == "drafted" and (not args.domain or c["domain"] == args.domain.upper())]
    raise AigError("Say which controls (--ids A,B or --all-drafted).")


def cmd_approve(args, ws):
    a = require(ws, args.by, "approve_controls", "Approving controls")
    words = need_text(args, "statement", "Approving controls")
    pr = ws.project(args.project)
    sel = _select(pr, args)
    if not sel:
        raise AigError("No controls to approve.")
    for c in sel:
        if c["state"] != "drafted":
            raise AigError("%s is %s, not drafted." % (c["id"], c["state"]))
        if c.get("owner") == a.person:
            raise AigError("%s: an owner cannot approve their own control." % c["id"])
    lines = ["%s v%s  %s" % (c["id"], c["definition"]["version"], c["title"]) for c in sel]
    text = "Controls approved for %s:\n\n%s\n\nDecision-maker's words:\n%s" % (pr.info()["name"], "\n".join("- " + l for l in lines), words)
    e = pr.journal().append("control_approval", ["ctl:" + c["id"] for c in sel], a.decided_by,
                            "Approved %d controls for %s" % (len(sel), pr.info()["name"]),
                            authority_basis=a.basis, labels=["unsigned"], text=text)
    for c in sel:
        c["approved_by"] = a.person
        c["approved_seq"] = e["seq"]
        log(c, a.decided_by, "drafted", "approved", "approved in journal line %d" % e["seq"])
        pr.save_control(c)
    print("Approved %d controls (journal line %d)." % (len(sel), e["seq"]))


def cmd_decline(args, ws):
    a = require(ws, args.by, "approve_controls", "Declining a drafted control")
    text = need_text(args, "statement", "Declining a drafted control")
    pr = ws.project(args.project)
    for c in _select(pr, args):
        if c["state"] != "drafted":
            raise AigError("%s is %s, not drafted." % (c["id"], c["state"]))
        log(c, a.decided_by, "drafted", "retired", "declined at draft: " + clip(text, 100))
        pr.save_control(c)
        pr.journal().append("control_retirement", ["ctl:" + c["id"]], a.decided_by,
                            "Declined drafted control %s" % c["id"], authority_basis=a.basis,
                            labels=["unsigned"], text=text)
    print("Declined.")


def cmd_tailor(args, ws):
    pr = ws.project(args.project)
    c = pr.get_control(args.id)
    if c["state"] not in ("drafted",):
        raise AigError("Tailoring notes can only be changed while the control is a draft.")
    c["tailoring"] = args.note
    if args.owner_role:
        c["owner_role"] = args.owner_role
    pr.save_control(c)
    print("Noted.")


# -------------------------------------------------------------- assign ----
def _message(ws, pr, person, items, due, kind="evidence_request"):
    s = ws.settings()
    info = pr.info()
    gov = [person_name(ws, a["person"]) for a in active_assignments(ws)
           if a["role"] in {r["id"] for r in ws.load("roles", []) if r.get("governance")}]
    out = []
    out.append("# Help needed with the AI system \"%s\"\n" % info["name"])
    out.append("Hello %s,\n" % person_name(ws, person))
    out.append("%s is putting the AI system \"%s\" through its AI governance work. AI Governance (%s) has "
               "approved the items below and asked you to take them on. You may use any tool or method you "
               "like, and you may ask for help.\n" % (s["company"], info["name"], ", ".join(gov) or "the governance lead"))
    n = 0
    items = sorted(items, key=lambda c: (not c["definition"].get("critical"), c["id"]))
    if any(c["definition"].get("critical") for c in items):
        out.append("Items marked **Priority** matter most for launch; please start with them.\n")
    for c in items:
        d = c["definition"]
        n += 1
        out.append("## %d. %s%s\n" % (n, c["title"], "  (Priority)" if d.get("critical") else ""))
        out.append("**What we need:** %s\n" % d["requirement"])
        out.append("**Why it matters:** %s\n" % d["objective"])
        out.append("**We will know it is done when:**\n")
        for x in d["acceptance"]:
            out.append("- %s" % x)
        out.append("\n**Please send back:** %s\n" % "; ".join(d["evidence_types"]))
        pb = d.get("playbook") or {}
        if pb.get("howto"):
            out.append("**A way to do it:** %s\n" % pb["howto"])
        if pb.get("tools"):
            out.append("**Tools other teams use for this (optional):** %s\n" % ", ".join(pb["tools"]))
        if c.get("tailoring"):
            out.append("**Note for your situation:** %s\n" % c["tailoring"])
    out.append("## By when\n\n%s\n" % (due or "As soon as you can; tell us if you need longer."))
    out.append("## How to reply\n\nPut your files and answers in your own folder for this AI system "
               "(the folder named \"from-person\"), or tell the person who sent you this. If something is unclear, "
               "or you cannot do it, say so. That is also a useful answer.\n")
    return "\n".join(out)


def person_dir(ws, pr, person):
    people = {p["id"]: p for p in ws.load("people", [])}
    if person not in people:
        raise AigError("'%s' is not in the people directory." % person)
    base = pr.p("people", people[person]["folder"])
    (base / "to-person").mkdir(parents=True, exist_ok=True)
    (base / "from-person").mkdir(parents=True, exist_ok=True)
    return base


def issue_request(ws, pr, owner, items, due, rtype="evidence_request", intro=None):
    """One message per person: all items for that person go in one file."""
    reqid = pr.next_id("REQ", "REQ")
    base = person_dir(ws, pr, owner)
    first = items[0]["title"] if len(items) == 1 else "%d items" % len(items)
    label = "Request" if rtype == "evidence_request" else rtype.replace("_", " ").capitalize()
    fname = "%s %s - %s.md" % (today(), label, slug(first)[:50])
    mpath = base / "to-person" / fname
    n = 2
    while mpath.exists():
        mpath = base / "to-person" / ("%s %s - %s (%d).md" % (today(), label, slug(first)[:50], n))
        n += 1
    body = _message(ws, pr, owner, items, due)
    if intro:
        body = body.replace("\n## 1.", "\n" + intro + "\n\n## 1.", 1)
    write_text(mpath, body)
    reqs = pr.load("requests", [])
    reqs.append({"id": reqid, "controls": [c["id"] for c in items], "to": owner, "type": rtype,
                 "channel": "folder", "message_file": str(mpath.relative_to(pr.root)).replace("\\", "/"),
                 "sent": iso(), "due": due, "status": "open", "answered": None, "answer_file": None})
    pr.save("requests", reqs)
    return reqid, mpath


def cmd_assign(args, ws):
    pr = ws.project(args.project)
    ids = [i.upper() for i in split_list(args.ids)]
    if args.role and ids:
        # both given: the list decides which controls move; the role is only a check that they belong to it
        for i in ids:
            c_ = pr.get_control(i)
            if c_["owner_role"] != args.role:
                raise AigError("%s belongs to role '%s', not '%s'. Use --ids alone to move specific controls to any owner." % (i, c_["owner_role"], args.role))
    elif args.role:
        ids = [c["id"] for c in pr.all_controls() if c["state"] == "approved" and c["owner_role"] == args.role]
        if not ids:
            raise AigError("No approved, unassigned controls for role '%s'." % args.role)
    if not ids:
        raise AigError("Say which controls (--ids or --role).")
    owner = args.owner
    if owner == TOOL or not owner:
        raise AigError("A control needs a named human owner (--owner).")
    items = []
    if owner not in {p["id"] for p in ws.load("people", [])}:
        raise AigError("'%s' is not in the people directory." % owner)
    gov_owner = is_governance_person(ws, owner)
    ex = None
    if gov_owner:
        exs = (pr.load("exceptions", []) + ws.load("exceptions", []))
        ex = next((e for e in exs if e["id"] == args.exception and e.get("person") == owner), None)
        if not ex:
            raise AigError("%s holds the AI Governance role. AI Governance approves controls and never implements them. "
                           "Pick another owner, or have AI Governance record an exception first (exception add)." % person_name(ws, owner))
        if ex.get("expires") and ex["expires"] < today():
            raise AigError("Exception %s ended on %s. Record a new one." % (ex["id"], ex["expires"]))
        if ex.get("controls") and any(i.upper() not in ex["controls"] for i in ids):
            raise AigError("Exception %s only covers: %s." % (ex["id"], ", ".join(ex["controls"])))
        if str(ex.get("scope", "")).startswith("project:") and ex["scope"] != "project:" + pr.slug:
            raise AigError("Exception %s belongs to a different AI system." % ex["id"])
    for cid in ids:
        c = pr.get_control(cid)
        if c["state"] not in ("approved", "assigned"):
            raise AigError("%s is %s. Only approved controls can be assigned." % (cid, c["state"]))
        if c.get("approved_by") == owner and not ex:
            raise AigError("%s: the person who approved a control cannot own it." % cid)
        items.append(c)
    due = parse_date(args.due, "due date")
    # no date given: each control gets one from how much it matters (critical 14 days, required before launch 21, others 60)
    dues = {c["id"]: (due or default_due_date(c["definition"])) for c in items}
    set_by_hand = bool(due)
    due = min(dues.values())   # the one message carries the earliest date
    # controls that already had an owner and a message: take them out of the old message (withdraw it and reissue what is left)
    moved = {c["id"] for c in items}
    prior = {}
    for c in items:
        if c["state"] == "assigned" and c.get("request") and c.get("owner") and c["owner"] != owner:
            prior.setdefault(c["request"], []).append(c["id"])
    reqid, mpath = issue_request(ws, pr, owner, items, due)
    notes = []
    for old_id, gone in prior.items():
        reqs = pr.load("requests", [])
        old = next((x for x in reqs if x["id"] == old_id), None)
        if not old or old["status"] != "open":
            continue
        if old.get("delivered"):
            notes.append("The earlier message %s to %s was already sent and still lists %s: tell them by hand that these moved." % (
                old_id, person_name(ws, old["to"]), ", ".join(gone)))
            continue
        old["status"] = "withdrawn"
        old["withdrawn"] = iso()
        old["withdrawn_reason"] = "controls %s moved to %s (%s)" % (", ".join(gone), person_name(ws, owner), reqid)
        old["withdrawn_by"] = "tool:aigrceler"
        mf = pr.root / old["message_file"]
        if mf.exists():
            wd = mf.parent / "withdrawn"
            wd.mkdir(parents=True, exist_ok=True)
            target = wd / mf.name
            k = 2
            while target.exists():
                target = wd / ("%s (%d)%s" % (mf.stem, k, mf.suffix)); k += 1
            shutil.move(str(mf), str(target))
            old["message_file"] = str(target.relative_to(pr.root)).replace("\\", "/")
        pr.save("requests", reqs)
        left = [i for i in old["controls"] if i not in moved]
        if left:
            litems = [pr.get_control(i) for i in left]
            new_id, new_path = issue_request(ws, pr, old["to"], litems, old.get("due"))
            for lc in litems:
                lc["request"] = new_id
                pr.save_control(lc)
            notes.append("%s's earlier message %s listed controls that moved, so it was withdrawn (moved to a 'withdrawn' folder) and one new message %s covers the %d that stay." % (
                person_name(ws, old["to"]), old_id, new_id, len(left)))
        else:
            notes.append("%s's earlier message %s is withdrawn (moved to a 'withdrawn' folder): all its controls moved." % (person_name(ws, old["to"]), old_id))
    for c in items:
        c["owner"] = owner
        c["due"] = dues[c["id"]]
        c["request"] = reqid
        if ex:
            c["exception"] = ex["id"]
            if c.get("approved_by") == owner:
                c["self_approved"] = True
        if c["state"] == "approved":
            log(c, "tool:aigrceler", "approved", "assigned", "request %s written for %s" % (reqid, owner))
        pr.save_control(c)
    print("One message written for %s covering %d control(s): %s" % (person_name(ws, owner), len(items), mpath.relative_to(pr.root)))
    for n_ in notes:
        print(n_)
    if not set_by_hand:
        print("No due date was given, so each control got one from how much it matters (critical 14 days, required before launch 21, others 60). "
              "The message carries the earliest, %s. Change one with 'control set-due'." % due)
    print("The message is in their folder. Send it by your usual channel (email, chat or ticket) and tell the tool when you have.")


def cmd_set_due(args, ws):
    """Move one control's due date. Only the date changes; the message already written keeps its own date."""
    pr = ws.project(args.project)
    if not args.id or not args.due or not args.why:
        raise AigError("Give the control (--id), the new date (--due YYYY-MM-DD) and the reason (--why).")
    c = pr.get_control(args.id.upper())
    new = parse_date(args.due, "due date")
    a = resolve_actor(ws, args.by)
    old = c.get("due")
    log(c, a.decided_by, c["state"], c["state"], "due date moved from %s to %s: %s" % (old or "none", new, args.why))
    c["due"] = new
    pr.save_control(c)
    print("%s is now due %s (was %s)." % (c["id"], new, old or "not set"))


def cmd_mark_sent(args, ws):
    pr = ws.project(args.project)
    reqs = pr.load("requests", [])
    r = next((x for x in reqs if x["id"] == args.id), None)
    if not r:
        raise AigError("No request %s." % args.id)
    a = resolve_actor(ws, args.by)
    if a.is_tool:
        raise AigError("A message counts as sent only when a person says they sent it: AIGRCeler cannot send anything. "
                       "Repeat with --by <the id of the person who sent it> and --note with what they told you. "
                       "If nobody has said they sent it, it is not sent.")
    if r.get("delivered"):
        raise AigError("%s is already marked as sent (%s)." % (r["id"], r["delivered"].get("time", "")[:10]))
    r["channel"] = args.channel or r["channel"]
    r["delivered"] = {"time": iso(), "via": args.channel or "folder", "note": args.note or "", "by": a.person}
    pr.save("requests", reqs)
    pr.journal().append("request_sent", ["project:" + pr.slug, r["id"]], a.decided_by,
                        "%s says %s to %s was sent (%s)" % (a.name, r["id"], person_name(ws, r["to"]), args.channel or "folder"),
                        authority_basis=a.basis, labels=["unsigned"], text=(args.note or None))
    print("Recorded: %s says %s was sent." % (a.name, r["id"]))


def cmd_unmark_sent(args, ws):
    """Take back a 'sent' mark that was wrong. The old mark stays in the request's history."""
    pr = ws.project(args.project)
    reqs = pr.load("requests", [])
    r = next((x for x in reqs if x["id"] == args.id), None)
    if not r:
        raise AigError("No request %s." % args.id)
    if not r.get("delivered"):
        raise AigError("%s is not marked as sent." % r["id"])
    if len((args.note or "").split()) < 5:
        raise AigError("Say in a sentence why the mark was wrong (--note).")
    r.setdefault("delivered_history", []).append(dict(r["delivered"], withdrawn=iso(), withdrawn_note=args.note))
    r["delivered"] = None
    pr.save("requests", reqs)
    a_ = resolve_actor(ws, args.by)
    pr.journal().append("request_unsent", ["project:" + pr.slug, r["id"]], a_.decided_by,
                        "Sent mark taken back for %s" % r["id"], authority_basis=a_.basis,
                        labels=["tool"] if a_.is_tool else ["unsigned"], text=args.note)
    print("%s is no longer marked as sent. The earlier mark is kept in its history." % r["id"])


def cmd_state(args, ws):
    pr = ws.project(args.project)
    c = pr.get_control(args.id)
    if (c["state"], args.to) not in TRANSITIONS_TOOL:
        raise AigError("A control cannot be moved from %s to %s by hand. States move through approvals, evidence and findings." % (c["state"], args.to))
    a = resolve_actor(ws, args.by)
    log(c, a.decided_by, c["state"], args.to, args.why or "")
    pr.save_control(c)
    print("%s is now %s." % (c["id"], args.to))


def cmd_waive(args, ws):
    a = require(ws, args.by, "waive_controls", "Waiving a control")
    text = need_text(args, "statement", "Waiving a control")
    pr = ws.project(args.project)
    c = pr.get_control(args.id)
    if c["state"] in ("waived", "retired"):
        raise AigError("%s is already %s." % (c["id"], c["state"]))
    if c.get("owner") == a.person:
        raise AigError("%s owns this control and cannot waive it. Another person in AI Governance must decide." % a.name)
    until = parse_date(args.until, "end date")
    if until and until < today():
        raise AigError("The end date %s has already passed." % until)
    if c["definition"].get("critical") and not until:
        raise AigError("Waiving a critical control needs an end date (--until) so it comes back for review.")
    log(c, a.decided_by, c["state"], "waived", clip(text, 120))
    c["waiver"] = {"by": a.person, "time": iso(), "until": until, "words": text}
    pr.save_control(c)
    pr.journal().append("waiver", ["ctl:" + c["id"]], a.decided_by,
                        "Waived %s %s" % (c["id"], "until " + until if until else "(no end date)"),
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Waived. The risks it addressed lose that credit.")


def cmd_retire(args, ws):
    a = require(ws, args.by, "waive_controls", "Retiring a control")
    text = need_text(args, "statement", "Retiring a control")
    pr = ws.project(args.project)
    c = pr.get_control(args.id)
    if c["state"] == "retired":
        raise AigError("%s is already retired." % c["id"])
    if c.get("owner") == a.person:
        raise AigError("%s owns this control and cannot retire it. Another person in AI Governance must decide." % a.name)
    log(c, a.decided_by, c["state"], "retired", clip(text, 120))
    pr.save_control(c)
    pr.journal().append("control_retirement", ["ctl:" + c["id"]], a.decided_by,
                        "Retired control %s on this AI system" % c["id"], authority_basis=a.basis,
                        labels=["unsigned"], text=text)
    print("Retired.")


def cmd_upgrade(args, ws):
    a = require(ws, args.by, "approve_controls", "Upgrading a control to a newer catalog version")
    text = need_text(args, "statement", "Upgrading a control")
    pr = ws.project(args.project)
    defs = load_defs(ws, True)
    c = pr.get_control(args.id)
    cur = defs.get(args.id)
    if not cur or cur["version"] == c["definition"]["version"]:
        raise AigError("%s is already on the current version." % args.id)
    if c["state"] in ("retired", "waived", "drafted"):
        raise AigError("%s is %s; upgrade applies to controls that are in force." % (c["id"], c["state"]))
    if c.get("owner") == a.person:
        raise AigError("%s owns this control and cannot upgrade it. Another person in AI Governance must decide." % a.name)
    old = c["definition"]["version"]
    c["definition"] = cur
    c["catalog_version"] = ws.settings()["catalog_version"]
    new_state = c["state"]
    if c["state"] in ("verified", "monitored"):
        new_state = "evidenced"
    if cur.get("status") == "retired":
        new_state = "retired"
    # evidence collected against the old version no longer counts toward the new one
    evs = pr.load("evidence", [])
    for e in evs:
        if e["control"] == c["id"] and e["status"] in ("accepted", "received"):
            e["status"] = "superseded"
            e["superseded_reason"] = "control upgraded from %s to %s" % (old, cur["version"])
    pr.save("evidence", evs)
    c["current_evidence"] = None
    c["strength"] = None
    log(c, a.decided_by, c["state"], new_state, "upgraded %s to %s" % (old, cur["version"]))
    pr.save_control(c)
    pr.journal().append("control_approval", ["ctl:" + c["id"]], a.decided_by,
                        "Upgraded %s from version %s to %s" % (c["id"], old, cur["version"]),
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Upgraded %s to version %s%s." % (c["id"], cur["version"], "; it must be verified again" if new_state == "evidenced" else ""))


def cmd_list(args, ws):
    pr = ws.project(args.project)
    cs = pr.all_controls()
    for c in cs:
        if args.state and c["state"] != args.state:
            continue
        if args.domain and c["domain"] != args.domain.upper():
            continue
        print("%-7s %-12s %-10s owner: %-18s %s" % (
            c["id"], c["state"], c.get("strength") or "-", c.get("owner") or c.get("proposed_owner") or "-", c["title"][:60]))
    print("%d controls." % len(cs))


# ------------------------------------------------------------ requests ----
GREETING = re.compile(r"^\s*(hello|hi|hey|dear)\b[^\n]{0,60}?[,!:]\s*", re.I)


def _strip_greeting(text):
    """The engine writes the greeting. A second one written into the text would double it."""
    t = GREETING.sub("", text or "", count=1)
    return t[:1].upper() + t[1:] if t else text


def _default_due():
    from .core import add_business_days
    return add_business_days(now(), 5).date().isoformat()


def _write_request(ws, pr, to, rtype, subject, text, due, controls=None):
    base = person_dir(ws, pr, to)
    reqid = pr.next_id("REQ", "REQ")
    fname = "%s %s - %s.md" % (today(), rtype.replace("_", " ").capitalize(), slug(subject)[:40])
    body = "# %s\n\nHello %s,\n\n%s\n\nPlease reply in your \"from-person\" folder or to the person who sent this.\n" % (
        subject, person_name(ws, to), _strip_greeting(text))
    mpath = base / "to-person" / fname
    write_text(mpath, body)
    reqs = pr.load("requests", [])
    reqs.append({"id": reqid, "controls": split_list(controls), "to": to, "type": rtype,
                 "channel": "folder", "message_file": str(mpath.relative_to(pr.root)).replace("\\", "/"),
                 "sent": iso(), "due": due, "status": "open", "answered": None, "answer_file": None})
    pr.save("requests", reqs)
    return reqid


REQUEST_TYPES = ("discovery_question", "evidence_request", "containment", "notice", "request")


def cmd_request_create(args, ws):
    pr = ws.project(args.project)
    if not args.to or not args.type or not args.subject or not args.text:
        raise AigError("A request needs --to, --type, --subject and --text.")
    if args.type not in REQUEST_TYPES:
        raise AigError("The request type must be one of: %s. (Questions that must be answered before DISCOVER can close are 'discovery_question'; "
                       "a request that asks someone to act is 'request'.)" % ", ".join(REQUEST_TYPES))
    due = parse_date(args.due, "due date")
    defaulted = False
    if not due:
        due, defaulted = _default_due(), True
    reqid = _write_request(ws, pr, args.to, args.type, args.subject, args.text, due, args.controls)
    print("Message %s written to %s's folder, reply wanted by %s%s." % (
        reqid, person_name(ws, args.to), due, " (set by default: five working days; change it with 'request set-due')" if defaulted else ""))


def cmd_request_set_due(args, ws):
    pr = ws.project(args.project)
    if not args.id or not args.due:
        raise AigError("Give the request (--id) and the new date (--due YYYY-MM-DD).")
    due = parse_date(args.due, "due date")
    reqs = pr.load("requests", [])
    r = next((x for x in reqs if x["id"] == args.id), None)
    if not r:
        raise AigError("No request %s." % args.id)
    if r["status"] != "open":
        raise AigError("Request %s is already %s; its date cannot change." % (args.id, r["status"]))
    old = r.get("due")
    r["due"] = due
    pr.save("requests", reqs)
    rewritten = False
    if not r.get("delivered") and r.get("message_file"):
        import re as _re
        mp = pr.root / r["message_file"]
        try:
            txt = open(mp, encoding="utf-8").read()
            new_txt = _re.sub(r"(## By when\n\n).*?(\n\n## )", lambda m: m.group(1) + due + m.group(2), txt, count=1, flags=_re.S)
            if new_txt != txt:
                open(mp, "w", encoding="utf-8").write(new_txt)
                rewritten = True
        except OSError:
            pass
    if rewritten:
        print("Request %s is now due %s (was %s). The message in the person's folder has not been sent yet, so its date now says %s too." % (
            args.id, due, old or "no date", due))
    else:
        print("Request %s is now due %s (was %s). The person's message is unchanged: tell them the new date in a short follow-up only if it matters to them." % (
            args.id, due, old or "no date"))


def cmd_request_answer(args, ws):
    pr = ws.project(args.project)
    reqs = pr.load("requests", [])
    r = next((x for x in reqs if x["id"] == args.id), None)
    if not r:
        raise AigError("No request %s." % args.id)
    base = person_dir(ws, pr, r["to"])
    a = resolve_actor(ws, args.by)
    if args.file:
        src = check_file(args.file, "reply file")
        dest = base / "from-person" / ("%s %s" % (today(), src.name))
        shutil.copy2(src, dest)
    elif args.text:
        _t = args.text.strip()
        if len(re.sub(r"[^A-Za-z0-9]", "", _t)) < 2 or _t.lower() in {"test", "asdf", "foo", "bar", "abc", "xxx", "tmp", "todo", "tbd"}:
            raise AigError("That is not a real reply (%r). A reply is the person's own answer, so nothing was recorded. "
                           "To see what the command accepts, run it with --help." % _t[:20])
        dest = base / "from-person" / ("%s Reply to %s.md" % (today(), r["id"]))
        who = "typed in by %s from what %s told us; these are not %s's own signed words" % (a.name, person_name(ws, r["to"]), person_name(ws, r["to"]))
        write_text(dest, "(%s)\n\n%s\n" % (who, args.text))
        r["transcribed"] = True
    else:
        raise AigError("Give the reply as --file or --text.")
    r["status"] = "answered"
    r["answered"] = iso()
    r["answer_file"] = str(dest.relative_to(pr.root)).replace("\\", "/")
    r["answer_recorded_by"] = a.decided_by
    follow = None
    pr.save("requests", reqs)
    if args.remaining and args.remaining.strip():
        target = args.remaining_to or r["to"]
        if args.remaining_to and args.remaining_to not in {p["id"] for p in ws.load("people", [])}:
            raise AigError("'%s' is not in the people directory. Add the person first (an outside contact is added as a person with no role)." % args.remaining_to)
        try:
            first = open(pr.root / r["message_file"], encoding="utf-8").readline().lstrip("# ").strip()
        except OSError:
            first = ""
        first = re.sub(r"^(still open:\s*)+", "", first, flags=re.I).strip()
        subject = "Still open: " + (first or "earlier questions")
        ftype = "discovery_question" if r["type"] == "discovery" else r["type"]   # an old record with a mistyped question
        if target == r["to"]:
            body = "Thank you for your reply. We still need an answer to this: " + args.remaining.strip()
        else:
            body = args.remaining.strip()
        follow = _write_request(ws, pr, target, ftype, subject, body, _default_due())
        reqs = pr.load("requests", [])
        for x in reqs:
            if x["id"] == r["id"]:
                x["follow_up"] = follow
        pr.save("requests", reqs)
    print("Reply filed in %s's folder. Next: analyze it (evidence intake and finding)." % person_name(ws, r["to"]))
    if follow:
        print("The reply did not cover everything, so a follow-up (%s) was written for %s for what is still missing (not sent until AI Governance sends it); it keeps the stage open until it is answered." % (
            follow, person_name(ws, args.remaining_to or r["to"])))


def cmd_request_withdraw(args, ws):
    """Take back a request that should not have been sent (or is no longer needed). The message stays in the person's folder."""
    pr = ws.project(args.project)
    if not args.id or not args.reason or not args.reason.strip():
        raise AigError("Give the request (--id) and why it is withdrawn (--reason), in plain words.")
    reqs = pr.load("requests", [])
    r = next((x for x in reqs if x["id"] == args.id), None)
    if not r:
        raise AigError("No request %s." % args.id)
    if r["status"] != "open":
        raise AigError("Request %s is already %s." % (args.id, r["status"]))
    a = resolve_actor(ws, args.by)
    r["status"] = "withdrawn"
    r["withdrawn"] = iso()
    r["withdrawn_reason"] = args.reason.strip()
    r["withdrawn_by"] = a.decided_by
    moved = False
    mf = pr.root / r["message_file"] if r.get("message_file") else None
    if not r.get("delivered") and mf and mf.exists():
        # never sent, so take it out of the person's folder: it must not sit beside live messages
        wd = mf.parent / "withdrawn"
        wd.mkdir(parents=True, exist_ok=True)
        target = wd / mf.name
        k = 2
        while target.exists():
            target = wd / ("%s (%d)%s" % (mf.stem, k, mf.suffix)); k += 1
        shutil.move(str(mf), str(target))
        r["message_file"] = str(target.relative_to(pr.root)).replace("\\", "/")
        moved = True
    pr.save("requests", reqs)
    pr.journal().append("request_withdrawn", ["project:" + pr.slug, r["id"]], a.decided_by,
                        "Request %s withdrawn%s" % (r["id"], "" if not r.get("delivered") else " (it had been sent)"),
                        authority_basis=a.basis, labels=["tool"] if a.is_tool else ["unsigned"], text=r["withdrawn_reason"])
    if moved:
        print("Request %s to %s is withdrawn, so nothing waits on it. It was never sent, so the message was moved to a 'withdrawn' folder and is no longer beside the live ones." % (
            args.id, person_name(ws, r["to"])))
    else:
        print("Request %s to %s is withdrawn, so nothing waits on it. It was marked as sent, so the message stays in their folder; tell them it is no longer needed if they have seen it." % (
            args.id, person_name(ws, r["to"])))


def request_subject(pr, r):
    """What a request is about: the title line of its message, or the control IDs. Never just 'a request'."""
    try:
        t = open(pr.root / r["message_file"], encoding="utf-8").readline().lstrip("# ").strip()
        if t:
            return t[:90]
    except Exception:
        pass
    return ", ".join(r.get("controls") or []) or r.get("type", "request")


def cmd_request_list(args, ws):
    pr = ws.project(args.project)
    for r in pr.load("requests", []):
        if args.status and r["status"] != args.status:
            continue
        dl = r.get("delivered")
        print("%s  %-9s to %-16s due %-11s %s | %s" % (r["id"], r["status"], r["to"], r["due"] or "-",
              ("marked sent" if dl else "not marked sent"),
              (", ".join(r["controls"]) if r["controls"] else request_subject(pr, r))))
