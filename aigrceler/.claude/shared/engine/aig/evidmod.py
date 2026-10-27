"""Evidence in, findings out. Evidence is fingerprinted at intake and never altered."""
import csv
import json
import shutil
from pathlib import Path

from .core import clip
from .core import (
    AigError, iso, now, parse_dt, add_days, require, need_text, resolve_actor, split_list,
    write_text, read_json, write_json, sha256_file, TOOL, slug, CREDIT_STATES, check_file, read_any_text,
    parse_date, today, evidence_usable,
)
from . import ctrlmod, riskmod

RANK = {"weak": 0, "moderate": 1, "strong": 2}
BYRANK = ["weak", "moderate", "strong"]
INTAKE_STATES = ("assigned", "implementing", "rejected", "expired", "evidenced", "verified", "monitored")
# a finding can promote a control to verified only from these states (never from waived, retired, drafted ...)
PROMOTE_FROM = ("assigned", "implementing", "rejected", "expired", "evidenced")


def parse_file(path):
    """Read what we can from machine-generated reports. Returns a small summary dict."""
    ext = path.suffix.lower()
    try:
        if ext in (".sarif", ".json"):
            data = json.loads(read_any_text(path))
            if isinstance(data, dict) and "runs" in data:
                levels = {}
                tool = None
                for run in data.get("runs", []):
                    tool = tool or (run.get("tool", {}).get("driver", {}).get("name"))
                    for res in run.get("results", []):
                        lv = res.get("level", "warning")
                        levels[lv] = levels.get(lv, 0) + 1
                return {"format": "sarif", "tool": tool, "results_by_level": levels,
                        "total": sum(levels.values())}
            if isinstance(data, dict):
                tool = data.get("tool") or data.get("generator")
                return {"format": "json", "keys": sorted(data.keys())[:20],
                        "tool": tool if isinstance(tool, str) else (tool.get("name") if isinstance(tool, dict) else None)}
            return {"format": "json", "items": len(data) if hasattr(data, "__len__") else 1}
        if ext == ".csv":
            import io
            rows = list(csv.reader(io.StringIO(read_any_text(path), newline="")))
            return {"format": "csv", "columns": rows[0] if rows else [], "rows": max(0, len(rows) - 1)}
    except Exception as e:  # unreadable report: say so, do not guess
        return {"format": ext.lstrip("."), "unreadable": str(e)[:120]}
    return {"format": ext.lstrip(".") or "file"}


def retain_until(ws, info, collected):
    years = ws.settings()["retention_years"].get(info.get("lane") or "full", 10)
    dt = collected
    try:
        return dt.replace(year=dt.year + years).date().isoformat()
    except ValueError:
        return dt.replace(year=dt.year + years, day=28).date().isoformat()


def cmd_intake(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    c = pr.get_control(args.control)
    if c["state"] not in INTAKE_STATES:
        raise AigError("%s is %s. Evidence can be received once the control has been approved and assigned." % (c["id"], c["state"]))
    d = c["definition"]
    kind = args.kind
    if kind not in ("report", "document", "statement"):
        raise AigError("--kind must be report (produced by a tool), document (a person's document) or statement.")
    if args.text and kind != "statement":
        raise AigError("Typed-in text can only be recorded as a statement (--kind statement). "
                       "For a report or a document, give the file itself (--file).")
    if not args.file and not args.text:
        raise AigError("Give the evidence as --file or --text.")
    if args.file:
        src = check_file(args.file, "evidence file")
    submitter = args.submitted_by or c.get("owner")
    if submitter and submitter not in {p["id"] for p in ws.load("people", [])}:
        raise AigError("'%s' is not in the people directory." % submitter)
    recorder = resolve_actor(ws, args.by)
    evid = pr.next_id("EV", "EV")
    edir = pr.p("evidence", evid)
    edir.mkdir(parents=True, exist_ok=True)
    rec = {"id": evid, "control": c["id"], "submitted_by": submitter, "recorded_by": recorder.decided_by,
           "recorded_person": None if recorder.is_tool else recorder.person,
           "request": args.request, "kind": kind, "type": args.type or "", "tool": args.tool,
           "tool_version": args.tool_version, "model_version": args.model_version,
           "period": args.period, "collected": iso(), "status": "received"}
    if args.file:
        dest = edir / src.name
        shutil.copy2(src, dest)
        rec["file"] = str(dest.relative_to(pr.root)).replace("\\", "/")
        rec["original_name"] = src.name
        rec["sha256"] = sha256_file(dest)
        rec["parsed"] = parse_file(dest)
    else:
        dest = edir / "statement.md"
        who = ctrlmod.person_name(ws, rec["submitted_by"]) if rec.get("submitted_by") else "the owner"
        write_text(dest, "(Typed in by %s from what %s said; not their own signed words.)\n\n%s\n" % (
            recorder.name, who, args.text))
        rec["transcribed"] = True
        rec.update(file=str(dest.relative_to(pr.root)).replace("\\", "/"), original_name="statement.md",
                   sha256=sha256_file(dest), parsed={"format": "text"})
    # what a report is worth is decided from the file itself, never from what the sender says about it
    parsed = rec["parsed"]
    file_tool = parsed.get("tool") if parsed.get("format") in ("sarif", "json") and not parsed.get("unreadable") else None
    if kind == "report":
        if rec.get("transcribed"):
            st = "weak"
        elif file_tool:
            st = "strong"
            rec["tool_from_file"] = file_tool
            if args.tool and args.tool.lower() != str(file_tool).lower():
                st = "moderate"
                rec["strength_note"] = "the report says it was made by '%s' but you named '%s', so it counts as moderate" % (file_tool, args.tool)
        else:
            st = "moderate"
            rec["strength_note"] = "the report does not name the tool that made it (or is not a machine-readable report), so it counts as moderate"
        if st == "strong" and d.get("model_bound") and not (args.model_version or info.get("model_version")):
            st = "moderate"
            rec["strength_note"] = "report is not tied to a model version, so it counts as moderate"
    elif kind == "document":
        st = "moderate"
    else:
        st = "weak"
    # model-bound controls: the evidence belongs to the model version in force when it arrived
    if d.get("model_bound") and not rec.get("model_version") and info.get("model_version"):
        rec["model_version"] = info["model_version"]
        rec["model_version_assumed"] = True
    rec["strength_intake"] = st
    coll = now()
    rec["valid_until"] = add_days(coll, d["valid_days"]).date().isoformat()
    rec["retain_until"] = retain_until(ws, info, coll)
    evs = pr.load("evidence", [])
    evs.append(rec)
    pr.save("evidence", evs)
    frm = c["state"]
    c.setdefault("evidence", []).append(evid)
    if frm not in ("evidenced", "verified", "monitored"):
        if frm == "assigned":
            ctrlmod.log(c, "tool:aigrceler", "assigned", "implementing", "work started (evidence received)")
        ctrlmod.log(c, "tool:aigrceler", c["state"], "evidenced", "evidence %s received" % evid)
    pr.save_control(c)
    pr.journal().append("evidence_intake", ["ev:" + evid, "ctl:" + c["id"]], recorder.decided_by,
                        "Evidence %s received for %s (%s, strength on arrival %s)" % (evid, c["id"], kind, st),
                        labels=["tool", "automatic"] + (["transcribed"] if rec.get("transcribed") else []),
                        extra={"sha256": rec["sha256"], "strength": st, "submitted_by": submitter})
    # close the request this evidence answers: the one named with --request, else the only open one for this person and control.
    # Never close a second request that merely concerns the same control (it may be asking for something different).
    reqs = pr.load("requests", [])
    cands = [r for r in reqs if r["status"] == "open" and c["id"] in r["controls"] and r["to"] == rec["submitted_by"]
             and r["type"] == "evidence_request"]
    if rec.get("request"):
        cands = [r for r in cands if r["id"] == rec["request"]]
    elif len(cands) > 1:
        print("Note: %s are all waiting on %s for %s; none was closed because this file was not said to answer one of them. Say which with --request." % (
            ", ".join(r["id"] for r in cands), ctrlmod.person_name(ws, rec["submitted_by"]), c["id"]))
        cands = []
    for r in cands:
        if all(pr.get_control(x)["state"] in ("evidenced", "verified", "monitored") for x in r["controls"]):
            r["status"] = "answered"; r["answered"] = iso()
    pr.save("requests", reqs)
    print("Evidence %s received for %s: strength on arrival %s; valid until %s; keep until %s." % (
        evid, c["title"], st, rec["valid_until"], rec["retain_until"]))
    if rec.get("strength_note"):
        print("Note: " + rec["strength_note"] + ".")
    print("Fingerprint %s. Next: Verifier analyzes it and a finding is recorded." % rec["sha256"][:16])


# ------------------------------------------------------------- findings ----
VERDICTS = ("satisfied", "partly", "not", "cannot-tell")


def _best(pr, evs, cid, info=None):
    """The accepted, still-valid evidence that earns the most credit for a control."""
    info = info or pr.info()
    ok = [e for e in evs if e["control"] == cid and evidence_usable(e, info)]
    if not ok:
        return None
    return max(ok, key=lambda e: (RANK[e["strength"]], e["collected"]))


def _apply_verdict(ws, pr, c, ev, evs, verdict, strength, by, reasons):
    """Record what a verdict does to the evidence and the control.
    Only a 'satisfied' verdict can lift a control into verified, and only from a state where that makes sense."""
    if verdict == "satisfied":
        ev["status"] = "accepted"
        ev["strength"] = strength
    else:
        ev["status"] = "not-accepted"
        ev["strength"] = None
    prev = c["state"]
    best = _best(pr, evs, c["id"])
    if best:
        c["current_evidence"] = best["id"]
        c["strength"] = best["strength"]
        c["suspended"] = False
        if prev in CREDIT_STATES:
            if verdict != "satisfied":
                ctrlmod.log(c, by, prev, prev, "newer evidence %s was judged '%s'; credit continues on %s" % (ev["id"], verdict, best["id"]))
        elif verdict == "satisfied" and prev in PROMOTE_FROM:
            ctrlmod.log(c, by, prev, "verified", "evidence %s satisfied the acceptance criteria" % best["id"])
        # any other state (waived, retired, drafted ...) is left exactly as it is
    else:
        c["current_evidence"] = None
        c["strength"] = None
        if prev in CREDIT_STATES:
            ctrlmod.log(c, by, prev, "evidenced", "no accepted evidence remains (%s)" % verdict)
        if verdict == "not" and c["state"] == "evidenced":
            ctrlmod.log(c, by, "evidenced", "rejected", "evidence %s did not meet the criteria: %s" % (ev["id"], clip(reasons, 100)))


def _independent(a, c, ev, what):
    if a.is_tool:
        return
    for who, label in ((c.get("owner"), "the owner of this control"), (ev.get("submitted_by"), "the person who sent this evidence"),
                       (ev.get("recorded_person"), "the person who recorded this evidence")):
        if who and a.person == who:
            raise AigError("%s cannot %s: %s is %s. Someone else with the authority must do it." % (a.name, what, a.name, label))


def cmd_finding(args, ws):
    pr = ws.project(args.project)
    evs = pr.load("evidence", [])
    ev = next((e for e in evs if e["id"] == args.evidence), None)
    if not ev:
        raise AigError("No evidence %s." % args.evidence)
    if ev["status"] != "received":
        raise AigError("Evidence %s already has a finding (%s)." % (ev["id"], ev["status"]))
    if args.verdict not in VERDICTS:
        raise AigError("Verdict must be one of: %s." % ", ".join(VERDICTS))
    if not args.reasons:
        raise AigError("A finding needs its reasons (--reasons). A regulator will ask why.")
    c = pr.get_control(ev["control"])
    if c["state"] not in INTAKE_STATES:
        raise AigError("%s is %s. A finding cannot be recorded on a control that is not in force." % (c["id"], c["state"]))
    a = resolve_actor(ws, args.by)
    st = ev["strength_intake"]
    if args.strength:
        if args.strength not in RANK:
            raise AigError("Strength must be strong, moderate or weak.")
        if RANK[args.strength] > RANK[st]:
            raise AigError("A finding may lower the strength of evidence but never raise it above what it earned on arrival (%s)." % st)
        st = args.strength
    # who may say what: the tool may judge machine reports and may say 'not', 'partly' or 'cannot tell'.
    # Anything that lifts a control to verified on a document or a statement needs a reviewing person.
    if a.is_tool:
        if args.verdict == "satisfied" and st != "strong":
            raise AigError("Evidence of strength '%s' needs a named reviewer with the authority to verify (--by <name>). "
                           "AIGRCeler may analyze it and may say 'partly' or 'not', but cannot verify it alone." % st)
    else:
        if "verify_evidence" not in a.caps:
            raise AigError("%s does not hold the authority to verify evidence (roles: %s)." % (a.name, ", ".join(a.roles) or "none"))
        _independent(a, c, ev, "verify this evidence")
        words = need_text(args, "statement", "Verifying evidence")
    if args.verdict == "satisfied" and ev["valid_until"] < today():
        raise AigError("This evidence is already past its valid-until date.")
    verdict = args.verdict
    reasons = args.reasons
    gaps = args.gaps or ""
    if verdict == "satisfied" and st == "weak":
        verdict = "partly"
        gaps = ("A statement on its own cannot verify a control. Please send a document or a report from a tool. "
                "AI Governance may instead accept the statement with a recorded reason. " + gaps).strip()
        print("Note: this evidence is a statement only (weak). The control stays at 'evidenced' until stronger proof arrives, or AI Governance overrules.")
    fid = pr.next_id("F", "F")
    f = {"id": fid, "evidence": ev["id"], "control": c["id"], "verdict": verdict, "reasons": reasons,
         "gaps": gaps, "strength": st, "reviewed_by": a.decided_by, "time": iso(),
         "overruled": False, "sha256": ev.get("sha256")}
    _apply_verdict(ws, pr, c, ev, evs, verdict, st, a.decided_by, reasons)
    pr.save_control(c)
    pr.save("evidence", evs)
    fs = pr.load("findings", [])
    fs.append(f)
    pr.save("findings", fs)
    pr.journal().append("finding", ["finding:" + fid, "ev:" + ev["id"], "ctl:" + c["id"]], a.decided_by,
                        "Finding %s on %s: %s (strength %s)" % (fid, c["id"], verdict, st),
                        labels=["tool", "automatic"] if a.is_tool else ["unsigned", "reviewed"],
                        extra={"sha256": ev.get("sha256"), "verdict": verdict, "strength": st},
                        text="Reasons: %s\n\nGaps: %s%s" % (reasons, gaps or "none",
                                                           "" if a.is_tool else "\n\nReviewer's own words:\n%s" % words))
    msg = ""
    if verdict != "satisfied" and c.get("owner"):
        intro = ("We looked at what you sent for this item. %s\n\nWhat is missing or unclear: %s\n\n"
                 "Please send an updated answer or tell us what is blocking you." % (
                     {"partly": "It covers part of what we asked.", "not": "It does not yet meet what we asked.",
                      "cannot-tell": "We could not tell whether it meets what we asked."}[verdict],
                     gaps or reasons))
        rid, path = ctrlmod.issue_request(ws, pr, c["owner"], [c], c.get("due"), rtype="follow_up", intro=intro)
        msg = " A follow-up message (%s) is written in %s's folder; it has NOT been sent. AI Governance sends it." % (rid, ctrlmod.person_name(ws, c["owner"]))
    s = riskmod.recompute(ws, pr)
    print("Finding %s: %s. %s is now %s.%s Residual risk %.1f (%s)." % (
        fid, verdict, c["id"], c["state"], msg, s["residual_total"], s["residual_band"]))
    banked = []
    for r_ in pr.load("risks", []):
        tot = sum(x.get("steps", 0.0) for x in r_.get("credits", []))
        mine = [x for x in r_.get("credits", []) if x["control"] == c["id"] and x.get("steps", 0.0) > 0]
        if mine and abs(tot - round(tot)) > 1e-9 and r_.get("residual_level") == r_.get("inherent_level"):
            banked.append("%s (%s) has %.1f of a step banked and has not moved yet" % (r_["id"], r_["title"][:50], tot))
    if banked:
        print("Credit is counted in whole steps, so a half step is kept but does not move the score by itself: %s. "
              "It moves when more verified controls (or stronger evidence) bring the total to a whole step." % "; ".join(banked))


def cmd_overrule(args, ws):
    a = require(ws, args.by, "overrule_findings", "Overruling a finding")
    text = need_text(args, "statement", "Overruling a finding")
    pr = ws.project(args.project)
    fs = pr.load("findings", [])
    f = next((x for x in fs if x["id"] == args.id), None)
    if not f:
        raise AigError("No finding %s." % args.id)
    if args.verdict not in VERDICTS:
        raise AigError("Verdict must be one of: %s." % ", ".join(VERDICTS))
    if f["overruled"]:
        raise AigError("This finding was already overruled.")
    evs = pr.load("evidence", [])
    ev = next(e for e in evs if e["id"] == f["evidence"])
    c = pr.get_control(f["control"])
    if c["state"] not in INTAKE_STATES:
        raise AigError("%s is %s. A finding cannot be overruled on a control that is not in force." % (c["id"], c["state"]))
    if ev["status"] in ("superseded", "expired"):
        raise AigError("Evidence %s is %s, so its finding can no longer be overruled. Ask for new evidence." % (ev["id"], ev["status"]))
    _independent(a, c, ev, "overrule the finding on this evidence")
    st = ev["strength_intake"]
    if args.strength:
        if args.strength not in RANK:
            raise AigError("Strength must be strong, moderate or weak.")
        if RANK[args.strength] > RANK[st]:
            raise AigError("Strength cannot exceed what the evidence earned on arrival (%s)." % st)
        st = args.strength
    if args.verdict == f["verdict"]:
        raise AigError("The finding already says '%s'. Overruling means changing the verdict." % f["verdict"])
    f["overruled"] = True
    f["original_verdict"] = f["verdict"]
    f["verdict"] = args.verdict
    f["overruled_by"] = a.person
    f["overrule_time"] = iso()
    _apply_verdict(ws, pr, c, ev, evs, args.verdict, st, a.decided_by, text)
    f["strength"] = st
    pr.save_control(c)
    pr.save("evidence", evs)
    pr.save("findings", fs)
    pr.journal().append("finding_overruled", [f["id"], "ctl:" + c["id"]], a.decided_by,
                        "Overruled finding %s on %s: %s became %s" % (f["id"], c["id"], f["original_verdict"], args.verdict),
                        authority_basis=a.basis, labels=["unsigned"], text=text,
                        extra={"sha256": ev.get("sha256"), "verdict": args.verdict, "strength": st})
    # feeds the catalog: the acceptance criteria may be wrong
    pid = ws.next_id("P", "P")
    write_json(ws.p("catalog", "proposals", pid + ".json"), {
        "id": pid, "source": "overruled_finding", "ref": f["id"], "kind": "review", "target": c["id"], "change": {},
        "reason": "AI Governance overruled the finding %s on %s (from %s to %s). Check whether the acceptance criteria or the evidence rules need to change." % (
            f["id"], c["id"], f["original_verdict"], args.verdict),
        "status": "open", "created": iso(), "proposed_by": "tool", "projects_affected": [pr.slug]})
    s = riskmod.recompute(ws, pr)
    print("Finding overruled. %s is now %s. Catalog proposal %s filed for review. Residual risk %.1f (%s)." % (
        c["id"], c["state"], pid, s["residual_total"], s["residual_band"]))


def cmd_list(args, ws):
    pr = ws.project(args.project)
    for e in pr.load("evidence", []):
        if args.control and e["control"] != args.control:
            continue
        print("%s  %-9s %-9s %-9s valid until %s  %s" % (e["id"], e["control"], e["status"], e["strength_intake"], e["valid_until"], e.get("original_name", "")))


# --------------------------------------------------------------- expiry ----
def _expire_one(ws, pr, ev, c, why):
    """Mark one piece of evidence expired and move its control if it lost its last valid evidence."""
    ev["status"] = "expired"
    ev["expired_reason"] = why
    ev["expired_time"] = iso()
    evs = pr.load("evidence", [])
    for e in evs:
        if e["id"] == ev["id"]:
            e.update(status="expired", expired_reason=why, expired_time=ev["expired_time"], **({"tampered": True} if ev.get("tampered") else {}))
    pr.save("evidence", evs)
    best = _best(pr, evs, c["id"])
    if best:
        c["current_evidence"], c["strength"] = best["id"], best["strength"]
        pr.save_control(c)
        return
    if c.get("current_evidence") == ev["id"] or c["state"] in CREDIT_STATES:
        c["current_evidence"] = None
        c["strength"] = None
        if c["state"] in CREDIT_STATES:
            ctrlmod.log(c, "tool:aigrceler", c["state"], "expired", why)
            pr.save_control(c)
            if c.get("owner"):
                intro = "The evidence on file for this item is no longer valid (%s). Please send a fresh one." % why
                ctrlmod.issue_request(ws, pr, c["owner"], [c], None, rtype="renewal", intro=intro)
        else:
            pr.save_control(c)


def refresh(ws, pr):
    """Apply everything that depends only on the calendar or the model version:
    evidence past its date, evidence tied to an old model version, waivers past their end date.
    Safe to run any time; it is run before any gate, status view or launch check."""
    info = pr.info()
    t = today()
    n = 0
    evs = pr.load("evidence", [])
    for e in list(evs):
        if e["status"] not in ("accepted", "received"):
            continue
        c = pr.get_control(e["control"])
        fp = pr.root / e["file"] if e.get("file") else None
        if fp is not None and e.get("sha256") and (not fp.exists() or sha256_file(fp) != e["sha256"]):
            e["tampered"] = True
            _expire_one(ws, pr, e, c, "the file no longer matches the fingerprint taken when it arrived (it was changed or removed afterwards)"); n += 1
            pr.journal().append("evidence_tampered", ["ev:" + e["id"], "ctl:" + c["id"]], "tool:aigrceler",
                                "Evidence %s for %s no longer matches the fingerprint taken when it arrived; expired, credit stopped" % (e["id"], c["id"]),
                                labels=["tool", "automatic"], extra={"sha256_at_intake": e.get("sha256"), "file_missing": not fp.exists()})
            print("%s: evidence %s was changed after it arrived. It no longer earns credit and %s needs a fresh copy." % (pr.slug, e["id"], c["id"]))
        elif e["status"] == "accepted" and e["valid_until"] < t:
            _expire_one(ws, pr, e, c, "its valid-until date (%s) has passed" % e["valid_until"]); n += 1
        elif e.get("model_version") and info.get("model_version") and e["model_version"] != info["model_version"]:
            _expire_one(ws, pr, e, c, "the AI model changed from %s to %s" % (e["model_version"], info["model_version"])); n += 1
    for c in pr.all_controls():
        w = c.get("waiver")
        if c["state"] == "waived" and w and w.get("until") and w["until"] < t and not w.get("ended"):
            back = "assigned" if c.get("owner") else "approved"
            ctrlmod.log(c, "tool:aigrceler", "waived", back, "waiver ended %s" % w["until"])
            c["waiver"]["ended"] = iso()
            pr.save_control(c)
            n += 1
            print("%s: the waiver of %s has ended; the control is back in force." % (pr.slug, c["id"]))
    if n:
        riskmod.recompute(ws, pr, refresh_first=False)
    return n


def expire_evidence(ws, pr, why, only_model_bound=True):
    """Kept for callers that change the model version: expire evidence tied to an old version."""
    return refresh(ws, pr)


def cmd_expire_check(args, ws):
    slugs = [args.project] if args.project else ws.project_slugs()
    total = 0
    for sl in slugs:
        pr = ws.project(sl)
        n = refresh(ws, pr)
        total += n
        print("%s: %d item(s) expired or ended." % (sl, n))
    return total
