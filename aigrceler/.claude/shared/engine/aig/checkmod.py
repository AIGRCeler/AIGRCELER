"""Warden's checks and the journal commands."""
from .core import (
    AigError, iso, today, now, parse_dt, require, need_text, resolve_actor, sha256_file,
    is_governance_person, read_json, STAGES,
)
from .catalogmod import load_defs, legal_index


def run_checks(ws):
    problems, warnings = [], []
    for msg in ws.journal().verify():
        problems.append("Company journal: " + msg)
    s = ws.settings()
    defs = load_defs(ws)
    if s.get("catalog_version"):
        legal = legal_index(defs)
        if not legal:
            warnings.append("No control in the catalog carries a legal mapping.")
    for sl in ws.project_slugs():
        pr = ws.project(sl)
        info = pr.info()
        for msg in pr.journal().verify():
            problems.append("%s journal: %s" % (sl, msg))
        jl = pr.journal().lines()
        intake = {}
        verdict_lines = {}
        for ln in jl:
            for sub in ln.get("subject", []):
                if sub.startswith("ev:") and ln["type"] == "evidence_intake":
                    intake[sub[3:]] = ln
                if sub.startswith("ev:") and ln["type"] in ("finding", "finding_overruled"):
                    verdict_lines.setdefault(sub[3:], []).append(ln)
        findings = pr.load("findings", [])
        evidence_all = pr.load("evidence", [])
        for e in evidence_all:
            p = pr.root / e["file"]
            if not p.exists():
                problems.append("%s: evidence file missing for %s (%s)." % (sl, e["id"], e["file"]))
            elif sha256_file(p) != e["sha256"]:
                problems.append("%s: evidence %s was changed after it arrived (fingerprint mismatch)." % (sl, e["id"]))
            ln = intake.get(e["id"])
            if not ln:
                problems.append("%s: evidence %s has no arrival line in the journal." % (sl, e["id"]))
            else:
                x = ln.get("extra") or {}
                if x.get("sha256") != e["sha256"]:
                    problems.append("%s: the fingerprint of evidence %s differs from the one written in the journal when it arrived." % (sl, e["id"]))
                if x.get("strength") != e["strength_intake"]:
                    problems.append("%s: the strength of evidence %s differs from the one written in the journal when it arrived." % (sl, e["id"]))
        tool_only = []
        for c in pr.all_controls():
            if c.get("owner") and is_governance_person(ws, c["owner"]) and not c.get("exception"):
                problems.append("%s: %s is owned by someone in AI Governance without a recorded exception." % (sl, c["id"]))
            if c.get("owner") and c.get("approved_by") == c["owner"] and not c.get("self_approved"):
                problems.append("%s: %s is approved by its own owner." % (sl, c["id"]))
            if c["state"] in ("verified", "monitored"):
                ev = next((e for e in evidence_all if e["id"] == c.get("current_evidence")), None)
                if not ev:
                    problems.append("%s: %s is %s but has no evidence on record." % (sl, c["id"], c["state"]))
                else:
                    if ev["valid_until"] < today():
                        problems.append("%s: %s is %s but its evidence expired on %s. Run the expiry check." % (sl, c["id"], c["state"], ev["valid_until"]))
                    if ev["control"] != c["id"]:
                        problems.append("%s: %s is verified with evidence %s that belongs to %s." % (sl, c["id"], ev["id"], ev["control"]))
                    if ev["status"] != "accepted":
                        problems.append("%s: %s is %s but evidence %s is '%s', not accepted." % (sl, c["id"], c["state"], ev["id"], ev["status"]))
                    if c.get("strength") != ev.get("strength"):
                        problems.append("%s: %s records strength '%s' but its evidence %s is '%s'." % (sl, c["id"], c.get("strength"), ev["id"], ev.get("strength")))
                    f = next((x for x in findings if x["evidence"] == ev["id"]), None)
                    if not f or f["verdict"] != "satisfied":
                        problems.append("%s: %s is %s but evidence %s has no 'satisfied' finding." % (sl, c["id"], c["state"], ev["id"]))
                    vl = verdict_lines.get(ev["id"], [])
                    if not vl:
                        problems.append("%s: no journal line records the finding on evidence %s." % (sl, ev["id"]))
                    elif f and f.get("reviewed_by", "").startswith("tool:") and not f.get("overruled"):
                        tool_only.append(c["id"])
            if c["state"] not in ("drafted", "retired") and c.get("approved_seq"):
                if not any(e["seq"] == c["approved_seq"] for e in jl):
                    problems.append("%s: %s points to an approval line that does not exist." % (sl, c["id"]))
            elif c["state"] not in ("drafted", "retired", "waived") and not c.get("approved_seq"):
                problems.append("%s: %s is %s without a recorded approval." % (sl, c["id"], c["state"]))
            cur = defs.get(c["id"])
            if cur and cur["version"] != c["definition"]["version"]:
                warnings.append("%s: %s is on version %s; the catalog has %s." % (sl, c["id"], c["definition"]["version"], cur["version"]))
        if tool_only:
            warnings.append("%s: %d control(s) were verified by AIGRCeler alone on strong evidence, with no person reviewing: %s. "
                            "AI Governance may sample these." % (sl, len(tool_only), ", ".join(tool_only[:10])))
        for stg, st in info["stages"].items():
            if st["status"] in ("started", "closed") and not any(e["seq"] == st.get("started_seq") for e in jl):
                problems.append("%s: stage %s has no start decision in the journal." % (sl, stg))
            if st["status"] == "closed_without_start":
                warnings.append("%s: stage %s was closed without a start decision (recorded as such)." % (sl, stg))
        if info.get("lane") == "light":
            from .projmod import escalators, PLAIN
            if escalators(info):
                problems.append("%s: in the light lane but %s." % (sl, ", ".join(PLAIN.get(x, x) for x in escalators(info))))
        for r in pr.load("risks", []):
            acc = r.get("acceptance")
            if acc:
                th = ws.load("thresholds")["accept_by"].get(acc["level"], [])
                roles_ok = False
                for pid in acc["by"]:
                    a = resolve_actor(ws, pid)
                    roles_ok = roles_ok or any(a.has_role(x) for x in th)
                if not roles_ok:
                    problems.append("%s: risk %s was accepted without a person in an allowed role (%s)." % (sl, r["id"], ", ".join(th)))
        for i in pr.load("incidents", []):
            if i["status"] == "open" and not i.get("acknowledged") and now() > parse_dt(i["escalate_due"]):
                warnings.append("%s: incident %s is past its response clock without confirmation." % (sl, i["id"]))
    return problems, warnings


def cmd_check(args, ws):
    problems, warnings = run_checks(ws)
    print("Checks run %s." % iso()[:16].replace("T", " "))
    for p in problems:
        print("PROBLEM: " + p)
    for w in warnings:
        print("Note: " + w)
    if not problems:
        print("No problems found.")
    return 1 if problems else 0


def cmd_verify(args, ws):
    j = ws.project(args.project).journal() if args.project else ws.journal()
    probs = j.verify()
    n = len(j.lines())
    if probs:
        for p in probs:
            print("BROKEN: " + p)
        return 1
    print("Journal intact: %d lines, chain unbroken." % n)
    return 0


def cmd_show(args, ws):
    j = ws.project(args.project).journal() if args.project else ws.journal()
    print(j.render_table())


def cmd_erratum(args, ws):
    a = require(ws, args.by, "adopt_statement", "Correcting a journal entry")
    text = need_text(args, "text", "A correction")
    j = ws.project(args.project).journal() if args.project else ws.journal()
    if not any(e["seq"] == args.seq for e in j.lines()):
        raise AigError("No journal line %s." % args.seq)
    e = j.append("erratum", ["line:%d" % args.seq], a.decided_by, "Correction to line %d" % args.seq,
                 authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Correction recorded as line %d. Line %d itself is not changed." % (e["seq"], args.seq))
