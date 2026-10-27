"""The dashboard. One fixed page template, filled with facts the engine reads from the records.

Rules:
- The page shape lives only in shared/templates/dashboard/template.html. Nobody writes dashboard HTML by hand and no AI generates it.
- This module only READS the records. It never changes one, never expires anything, never sends anything.
- The output (dashboard/index.html and dashboard/dashboard.json) is rebuilt from the records at any time; delete it and it comes back.
- A failure to build must never stop the command that triggered it."""
import datetime
import json
import os
import re
from pathlib import Path

from .core import (
    DOMAINS, DOMAIN_TITLES, STAGES, CONTROL_STATES, SEVERITIES, iso, now, today, parse_dt, read_json, write_text, write_json,
    sha256_file, AigError,
)
from .wsmod import SHARED
from . import chasemod, profmod, regmod, stagemod

CONTRACT = "1"
TEMPLATE = SHARED / "templates" / "dashboard" / "template.html"
SECTIONS = ["attention", "portfolio", "dates", "people", "company", "trends", "controls", "risk", "evidence", "watch", "chase", "discovery", "regulatory", "decisions"]
GROUPS = {
    "in_place": ("verified", "monitored"),
    "in_progress": ("implementing", "evidenced"),
    "waiting": ("drafted", "approved", "assigned"),
    "problem": ("expired", "rejected"),
    "waived": ("waived",),
}
SEV_RANK = {"critical": 0, "serious": 1, "warning": 2, "info": 3}
OK_STATES = ("verified", "monitored", "waived")
EXPIRY_WARN_DAYS = 30
HISTORY_DAYS = 120
READ_ONLY_COMMANDS = {"list", "show", "status", "gate", "readiness", "chase", "due", "coverage", "impact", "proposals",
                      "launch-status", "gaps", "for", "run", "build", "path"}


# ------------------------------------------------------------ helpers ----
def _short(text, n=160):
    return chasemod._short(text or "", n)


def _days_to(date_str):
    """Whole days from today to a YYYY-MM-DD date (negative = past). None when there is no date."""
    if not date_str:
        return None
    try:
        return chasemod._days(today(), str(date_str)[:10])
    except ValueError:
        return None


def _who(names, key):
    if not key:
        return None
    k = str(key)
    if k.startswith("tool:"):
        return "AIGRCeler"
    if ":" in k:
        k = k.split(":", 1)[1]
    return names.get(k, k)


def _stage_info(info):
    out = []
    for sid in STAGES:
        st = (info.get("stages") or {}).get(sid) or {}
        out.append({"id": sid, "status": st.get("status") or "not_started", "started": (st.get("started") or "")[:10] or None,
                    "closed": (st.get("closed") or "")[:10] or None})
    return out


def _controls(pr, names, chase_by_ctl):
    td = today()
    rows = []
    for c in pr.all_controls():
        if c["state"] == "retired":
            continue
        d = c["definition"]
        due = c.get("due")
        done = c["state"] in OK_STATES
        late = max(0, -_days_to(due)) if (due and not done and due < td) else 0
        w = chase_by_ctl.get(c["id"])
        rows.append({"id": c["id"], "title": c["title"], "area": c["domain"], "state": c["state"], "owner": _who(names, c.get("owner")),
                     "due": due, "late": late, "strength": c.get("strength"), "critical": bool(d.get("critical")),
                     "launch_required": bool(d.get("launch_required")), "waiting_on": w})
    return rows


def _by_area(rows):
    out = []
    for code in DOMAINS:
        sub = [r for r in rows if r["area"] == code]
        if not sub:
            continue
        states = {s: 0 for s in CONTROL_STATES if s != "retired"}
        for r in sub:
            states[r["state"]] = states.get(r["state"], 0) + 1
        out.append({"code": code, "title": DOMAIN_TITLES[code], "total": len(sub), "states": states,
                    "in_place": sum(states[s] for s in GROUPS["in_place"]),
                    "strength": {k: sum(1 for r in sub if r["state"] in GROUPS["in_place"] and r["strength"] == k) for k in ("strong", "moderate", "weak")}})
    return out


def _groups(rows):
    g = {k: 0 for k in GROUPS}
    for r in rows:
        for k, v in GROUPS.items():
            if r["state"] in v:
                g[k] += 1
    return g


def _risk(pr, names):
    summ = pr.load("risk_summary")
    risks = pr.load("risks", [])
    scen = []
    acc = []
    for r in risks:
        a = r.get("acceptance")
        scen.append({"id": r["id"], "title": r["title"], "dimension": r.get("dimension"),
                     "before": r.get("inherent_score"), "before_level": r.get("inherent_level"),
                     "after": r.get("residual_score"), "after_level": r.get("residual_level"),
                     "floor_applied": bool(r.get("floor_applied")), "rated": bool(r.get("inherent_set")),
                     "accepted": bool(a), "credits": len([c for c in r.get("credits", []) if c.get("steps")])})
        if a:
            acc.append({"risk": r["id"], "title": r["title"], "level": a.get("level"), "by": [names.get(x, x) for x in a.get("by", [])],
                        "time": (a.get("time") or "")[:10], "until": a.get("until"), "days_left": _days_to(a.get("until"))})
    out = {"scored": bool(summ), "scenarios": scen, "acceptances": acc}
    if summ:
        out.update({"as_of": summ["as_of"][:16].replace("T", " "), "inherent": summ["inherent_total"], "residual": summ["residual_total"],
                    "inherent_band": summ["inherent_band"], "residual_band": summ["residual_band"], "unrated": summ["unrated_scenarios"],
                    "dimensions": [{"key": k, "title": d["title"], "max": d["max_points"], "scenarios": d["scenarios"],
                                    "inherent": d["inherent_points"], "residual": d["residual_points"]} for k, d in summ["dimensions"].items()]})
    return out


def _evidence(pr, names):
    evs = pr.load("evidence", [])
    td = today()
    by_status = {}
    for e in evs:
        by_status[e["status"]] = by_status.get(e["status"], 0) + 1
    expiring = []
    tampered = []
    for e in evs:
        if e["status"] in ("accepted", "received") and e.get("valid_until"):
            left = _days_to(e["valid_until"])
            if left is not None and left <= EXPIRY_WARN_DAYS:
                expiring.append({"id": e["id"], "control": e["control"], "valid_until": e["valid_until"], "days_left": left})
        fp = pr.root / e["file"] if e.get("file") else None
        bad = bool(e.get("tampered"))
        if not bad and fp is not None and e.get("sha256") and e["status"] in ("accepted", "received"):
            try:
                bad = (not fp.exists()) or sha256_file(fp) != e["sha256"]
            except OSError:
                bad = True
        if bad:
            tampered.append({"id": e["id"], "control": e["control"], "status": e["status"]})
    expiring.sort(key=lambda x: x["days_left"])
    return {"total": len(evs), "by_status": by_status, "expiring": expiring, "mismatch": tampered}


def _incidents(pr, names):
    out = []
    nw = now()
    for i in pr.load("incidents", []):
        late = False
        if i["status"] == "open" and not i.get("acknowledged") and i.get("escalate_due"):
            try:
                late = parse_dt(i["escalate_due"]) < nw
            except ValueError:
                late = False
        out.append({"id": i["id"], "title": i["title"], "severity": i["severity"], "status": i["status"], "opened": (i["opened"] or "")[:10],
                    "escalate_due": (i.get("escalate_due") or "")[:16].replace("T", " "), "acknowledged": bool(i.get("acknowledged")),
                    "overdue_ack": late, "response_owner": _who(names, i.get("response_owner")), "reportable": bool(i.get("reportable")),
                    "closed": (i.get("closed") or "")[:10] or None, "lesson": _short(i.get("lesson"), 200) if i.get("lesson") else None})
    out.sort(key=lambda x: (x["status"] != "open", -SEVERITIES.index(x["severity"]), x["opened"]))
    return out


def _indicators(pr):
    out = []
    for i in pr.load("indicators", []):
        out.append({"id": i["id"], "control": i["control"], "metric": _short(i["metric"], 140), "current": i.get("current"), "min": i.get("min"),
                    "max": i.get("max"), "unit": i.get("unit"), "status": i.get("status"), "updated": (i.get("updated") or "")[:10],
                    "history": [h.get("value") for h in (i.get("history") or [])][-12:]})
    return out


def _chase_rows(rows, names):
    out = []
    for r in rows:
        out.append({"who": _who(names, r["who"]) or r["who"], "kind": r["kind"], "id": r["id"], "title": _short(r["title"], 90),
                    "priority": r["prio"], "due": r["due"], "late": r["late"], "side": r["side"], "action": _short(r["action"], 220)})
    return out


def _regulatory(ws, pr):
    ctx = regmod._system_context(ws, pr)
    cs = pr.all_controls()
    out = []
    for fw in regmod.regmap()["frameworks"]:
        c = {"in place": 0, "partly in place": 0, "in progress": 0, "not determined": 0, "by how AIGRCeler works": 0, "no control applies": 0}
        n = 0
        for it in fw["items"]:
            ap = regmod._applies(it, ctx) if fw["id"] == "eu" else True
            if ap is False:
                continue
            stt, _mine = regmod._item_state(it, cs)
            n += 1
            if ap is None:
                c["not determined"] += 1
            elif stt in c:
                c[stt] += 1
            elif stt.startswith("no control applies"):
                c["no control applies"] += 1
            else:
                c["in progress"] += 1
        out.append({"id": fw["id"], "name": fw["name"], "items": n, "counts": c})
    return out


def _decisions(pr, names, limit=25):
    j = pr.journal()
    ls = j.lines()
    problems = j.verify()
    rows = [{"seq": e["seq"], "time": e["time"][:16].replace("T", " "), "type": e["type"], "by": _who(names, e.get("decided_by")),
             "summary": _short(e["summary"], 240)} for e in ls[-limit:]]
    rows.reverse()
    return {"count": len(ls), "intact": not problems, "problems": [_short(p, 200) for p in problems[:5]], "recent": rows,
            "head": ls[-1]["hash"][:12] if ls else None}


def _attention(slug, name, s):
    """The fixed rules for what needs a person's attention. (severity, text, where on the system page)."""
    out = []

    def add(sev, text, tab="overview"):
        out.append({"system": slug, "system_name": name, "severity": sev, "text": text, "tab": tab})

    if not s["decisions"]["intact"]:
        add("critical", "The decision journal does not check out: %s" % (s["decisions"]["problems"][0] if s["decisions"]["problems"] else "see the Decisions tab"), "decisions")
    for b in s["blocks"]:
        add("critical", "Stage block in force: %s" % _short(b, 140), "discovery")
    if s["evidence"]["mismatch"]:
        ids = ", ".join(x["id"] for x in s["evidence"]["mismatch"][:4])
        add("critical", "%d piece(s) of evidence no longer match the fingerprint taken on arrival (%s). They cannot earn credit." % (len(s["evidence"]["mismatch"]), ids), "evidence")
    for i in s["incidents"]:
        if i["status"] != "open":
            continue
        if i["overdue_ack"]:
            add("critical", "%s incident %s has not been acknowledged and its response time has passed: %s" % (i["severity"].capitalize(), i["id"], _short(i["title"], 90)), "watch")
        elif i["severity"] in ("critical", "high"):
            add("serious", "Open %s incident %s: %s" % (i["severity"], i["id"], _short(i["title"], 90)), "watch")
        else:
            add("warning", "Open %s incident %s: %s" % (i["severity"], i["id"], _short(i["title"], 90)), "watch")
    late_req = [c for c in s["control_rows"] if c["late"] and (c["critical"] or c["launch_required"])]
    if late_req:
        add("serious", "%d required control(s) are past their due date (longest %d days late)." % (len(late_req), max(c["late"] for c in late_req)), "controls")
    late_other = [c for c in s["control_rows"] if c["late"] and not (c["critical"] or c["launch_required"])]
    if late_other:
        add("warning", "%d other control(s) are past their due date." % len(late_other), "controls")
    rv = s["review"]
    if rv:
        if rv["left"] < 0:
            add("serious", "The review was due %s (%d days ago)." % (rv["due"], -rv["left"]), "watch")
        elif rv["left"] <= 14:
            add("warning", "The next review is due %s (in %d days)." % (rv["due"], rv["left"]), "watch")
        for r in rv.get("reasons", []):
            add("warning", "A review is also called for: %s." % r, "watch")
    for o in s["obligations"]:
        if o["status"] != "open" or o["days_left"] is None:
            continue
        if o["days_left"] < 0:
            add("critical", "Obligation overdue (%d days): %s" % (-o["days_left"], _short(o["title"], 100)), "watch")
        elif o["days_left"] <= 7:
            add("serious", "Obligation due in %d day(s), %s: %s" % (o["days_left"], o["due"], _short(o["title"], 100)), "watch")
        elif o["days_left"] <= 30:
            add("warning", "Obligation due %s (in %d days): %s" % (o["due"], o["days_left"], _short(o["title"], 100)), "watch")
    for e in s["evidence"]["expiring"]:
        if e["days_left"] < 0:
            add("warning", "Evidence %s for %s has passed its valid-until date." % (e["id"], e["control"]), "evidence")
        elif e["days_left"] <= 14:
            add("warning", "Evidence %s for %s expires in %d day(s)." % (e["id"], e["control"], e["days_left"]), "evidence")
    for a in s["risk"]["acceptances"]:
        if a["days_left"] is not None and a["days_left"] <= 30:
            add("warning", "The acceptance of risk %s ends %s%s." % (a["risk"], a["until"], " (already ended)" if a["days_left"] < 0 else ""), "risk")
    for c in s["containment"]:
        if c["status"] != "active":
            continue
        if not c["confirmed"]:
            add("warning", "Temporary measure not confirmed in place: %s" % _short(c["title"], 100), "watch")
        elif c["days_left"] is not None and c["days_left"] <= 14:
            add("warning", "Temporary measure ends %s: %s" % (c["ends"], _short(c["title"], 90)), "watch")
    us = [r for r in s["chase"] if r["side"] == "us"]
    if us:
        add("warning", "%d item(s) are waiting on us (messages not written or not marked as sent, or no owner)." % len(us), "chase")
    ver = [r for r in s["chase"] if r["side"] == "verifier"]
    if ver:
        add("info", "%d control(s) have evidence waiting for an independent check." % len(ver), "chase")
    pf = s["profile"]
    if pf["required"] and pf["rate"] > pf["limit"] + 1e-9:
        add("warning", "Too many discovery answers are \"not known\" or skipped (%d%%, the limit is %d%%)." % (round(pf["rate"] * 100), round(pf["limit"] * 100)), "discovery")
    if s["go"]["state"] == "ready":
        add("info", "Every required control is in place. A go decision can be recorded.", "overview")
    return out


# ------------------------------------------------------------ collect ----
def _system(ws, pr, names, roles_by_person):
    info = pr.info()
    raw = chasemod.build(ws, pr)
    chase = _chase_rows(raw, names)
    chase_by_ctl = {r["id"]: r["side"] for r in raw if r["kind"] == "control"}
    rows = _controls(pr, names, chase_by_ctl)
    blockers, nums = stagemod.readiness(ws, pr, fresh=False)
    signoffs = info.get("signoffs") or []
    op = (info.get("stages") or {}).get("OPERATE", {}).get("status") == "started"
    if signoffs:
        gstate = "decided"
    elif op and not blockers:
        gstate = "ready"
    elif op:
        gstate = "not_ready"
    else:
        gstate = "not_in_operate"
    last = None
    if signoffs:
        l = signoffs[-1]
        last = {"time": l["time"][:10], "by": l.get("by_name") or _who(names, l.get("by")), "seq": l["seq"], "items_left_open": len(l.get("open_items") or [])}
    pstate = profmod.state(ws, pr, info)["counts"]
    rs = chasemod.review_status(ws, pr)
    reviews = pr.load("reviews", [])
    inds = _indicators(pr)
    obs = [{"id": o["id"], "title": _short(o["title"], 140), "authority": _short(o.get("authority"), 80), "due": o.get("due"),
            "days_left": _days_to(o.get("due")), "status": o["status"]} for o in pr.load("obligations", [])]
    cont = [{"id": c["id"], "title": _short(c["title"], 160), "ends": c.get("ends"), "days_left": _days_to(c.get("ends")),
             "status": c["status"], "confirmed": bool(c.get("confirmed"))} for c in pr.load("containment", [])]
    exc = [{"id": e["id"], "what": _short(e["what"], 160), "approved_by": _who(names, e.get("approved_by")), "expires": e.get("expires"),
            "days_left": _days_to(e.get("expires"))} for e in pr.load("exceptions", [])]
    con = pr.load("concerns", [])
    open_con = [c for c in con if c["status"] == "open"]
    concerns = {"open": len(open_con), "resolved": len(con) - len(open_con),
                "list": [{"id": c["id"], "kind": c["kind"], "text": _short(c["text"], 220), "carry_to": c.get("carry_to"),
                          "raised": (c.get("raised") or "")[:10]} for c in open_con[:40]]}
    ass = [{"key": k, "status": v.get("status"), "note": _short(v.get("note"), 200)} for k, v in (pr.load("assessments", {}) or {}).items()]
    blocks = [b["reason"] for b in (info.get("blocks") or []) if not b.get("lifted")]
    risk = _risk(pr, names)
    dec = _decisions(pr, names)
    owners = {}
    for r in chase:
        o = owners.setdefault(r["who"], {"who": r["who"], "open": 0, "late": 0})
        o["open"] += 1
        o["late"] += 1 if r["late"] else 0
    s = {
        "slug": pr.slug, "name": info["name"], "purpose": _short(info.get("purpose"), 240), "lane": info.get("lane"), "lane_decided": bool(info.get("lane_decided")),
        "lane_suggested": info.get("lane_suggested"), "tier": info.get("tier"), "sourcing": info.get("sourcing_mode"),
        "current_stage": info.get("current_stage"), "stages": _stage_info(info),
        "go": {"state": gstate, "required": nums["required"], "done": nums["done"], "blockers": blockers, "last": last, "count": len(signoffs)},
        "profile": {"level": pstate["level"], "required": pstate["required"], "answered": pstate["answered"], "unknown": pstate["unknown"],
                    "open": pstate["open"] + pstate["inferred"], "rate": pstate["rate"], "limit": pstate["limit"]},
        "controls": {"total": len(rows), "groups": _groups(rows), "by_area": _by_area(rows)},
        "control_rows": rows,
        "risk": risk, "evidence": _evidence(pr, names), "incidents": _incidents(pr, names), "indicators": inds, "obligations": obs,
        "containment": cont, "exceptions": exc, "concerns": concerns, "assessments": ass, "blocks": blocks,
        "review": ({"every": rs["every"], "custom": rs["custom"], "last": rs["last"], "due": rs["due"], "left": rs["left"], "reasons": rs["reasons"],
                    "count": len(reviews)} if rs else None),
        "chase": chase, "owners": sorted(owners.values(), key=lambda o: (-o["late"], -o["open"], o["who"])),
        "regulatory": _regulatory(ws, pr), "decisions": dec,
    }
    s["counts"] = {
        "open_incidents": len([i for i in s["incidents"] if i["status"] == "open"]),
        "serious_incidents": len([i for i in s["incidents"] if i["status"] == "open" and i["severity"] in ("high", "critical")]),
        "late": len([c for c in rows if c["late"]]),
        "waiting_us": len([r for r in chase if r["side"] == "us"]),
        "verifier_queue": len([r for r in chase if r["side"] == "verifier"]),
        "indicators_out": len([i for i in inds if i["status"] and i["status"] != "in_tolerance"]),
    }
    s["attention"] = _attention(pr.slug, info["name"], s)
    s["attention"].sort(key=lambda a: SEV_RANK[a["severity"]])
    return s


def _history(ws):
    d = ws.p("dashboard", "history")
    out = []
    if d.exists():
        for f in sorted(d.glob("*.json"))[-HISTORY_DAYS:]:
            v = read_json(f)
            if v:
                out.append(v)
    return out


def _snapshot(data):
    snap = {"date": today(), "systems": {}}
    for s in data["systems"]:
        snap["systems"][s["slug"]] = {
            "residual": s["risk"].get("residual"), "inherent": s["risk"].get("inherent"),
            "required_done": s["go"]["done"], "required_total": s["go"]["required"],
            "in_place": s["controls"]["groups"]["in_place"], "controls": s["controls"]["total"],
            "open_incidents": s["counts"]["open_incidents"], "late": s["counts"]["late"], "waiting_us": s["counts"]["waiting_us"],
        }
    return snap


def _config(ws):
    cfg = read_json(ws.p("dashboard", "config.json"), {}) or {}
    out = {"title": None, "accent": None, "hide": [], "logo": None}
    if isinstance(cfg.get("title"), str):
        out["title"] = cfg["title"][:80]
    if isinstance(cfg.get("accent"), str) and re.fullmatch(r"#[0-9a-fA-F]{6}", cfg["accent"]):
        out["accent"] = cfg["accent"]
    if isinstance(cfg.get("hide"), list):
        out["hide"] = [h for h in cfg["hide"] if h in SECTIONS]
    logo = cfg.get("logo")
    if isinstance(logo, str):
        p = (ws.p("dashboard") / logo).resolve()
        ext = p.suffix.lower()
        mime = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".svg": "image/svg+xml"}.get(ext)
        try:
            if mime and p.is_file() and ws.p("dashboard").resolve() in p.parents and p.stat().st_size <= 150000:
                import base64
                out["logo"] = "data:%s;base64,%s" % (mime, base64.b64encode(p.read_bytes()).decode("ascii"))
        except OSError:
            pass
    return out


def collect(ws):
    s = ws.settings()
    names = {p["id"]: p["name"] for p in ws.load("people", [])}
    role_name = {r["id"]: r["name"] for r in ws.load("roles", [])}
    roles_by_person = {}
    from .core import active_assignments
    for a in active_assignments(ws):
        roles_by_person.setdefault(a["person"], []).append(role_name.get(a["role"], a["role"]))
    systems = [_system(ws, ws.project(sl), names, roles_by_person) for sl in ws.project_slugs()]
    wj = ws.journal()
    wprob = wj.verify()
    wl = wj.last()
    people = []
    for p in ws.load("people", []):
        if not p.get("active", True):
            continue
        mine = [(sy, r) for sy in systems for r in sy["chase"] if r["who"] == p["name"]]
        people.append({"name": p["name"], "type": p.get("type"), "roles": roles_by_person.get(p["id"], []),
                       "open": len(mine), "late": len([1 for _s, r in mine if r["late"]]),
                       "systems": sorted({sy["name"] for sy, _r in mine})})
    people.sort(key=lambda x: (-x["late"], -x["open"], x["name"]))
    orgrisks = [{"id": o["id"], "title": _short(o["title"], 140), "inherent": o.get("inherent"), "residual": o.get("residual"),
                 "accepted": bool(o.get("acceptance"))} for o in ws.load("organizational_risks", [])]
    exc = [{"id": e["id"], "what": _short(e["what"], 160), "expires": e.get("expires"), "days_left": _days_to(e.get("expires"))}
           for e in ws.load("exceptions", [])]
    obligations = [dict(o, system=sy["name"], slug=sy["slug"]) for sy in systems for o in sy["obligations"] if o["status"] == "open"]
    obligations.sort(key=lambda o: (o["due"] or "9999"))
    expiring = [dict(e, system=sy["name"], slug=sy["slug"]) for sy in systems for e in sy["evidence"]["expiring"]]
    expiring.sort(key=lambda e: e["days_left"])
    accept = [dict(a, system=sy["name"], slug=sy["slug"]) for sy in systems for a in sy["risk"]["acceptances"]]
    accept.sort(key=lambda a: (a["until"] or "9999"))
    attention = [a for sy in systems for a in sy["attention"]]
    if wprob:
        attention.append({"system": None, "system_name": "Company", "severity": "critical",
                          "text": "The company-level decision journal does not check out: %s" % _short(wprob[0], 160), "tab": None})
    for o in exc:
        if o["days_left"] is not None and o["days_left"] <= 14:
            attention.append({"system": None, "system_name": "Company", "severity": "warning",
                              "text": "Exception %s %s: %s" % (o["id"], "ended" if o["days_left"] < 0 else "ends %s" % o["expires"], _short(o["what"], 90)), "tab": None})
    attention.sort(key=lambda a: SEV_RANK[a["severity"]])
    data = {
        "contract": CONTRACT, "generated": iso(), "engine_version": s.get("engine_version"), "template_version": None,
        "config": _config(ws),
        "company": {"name": s["company"], "catalog_version": s.get("catalog_version"),
                    "journal": {"intact": not wprob, "problems": [_short(p, 200) for p in wprob[:5]], "count": len(wj.lines()),
                                "head": wl["hash"][:12] if wl else None}},
        "totals": {
            "systems": len(systems),
            "in_operate": len([x for x in systems if any(st["id"] == "OPERATE" and st["status"] == "started" for st in x["stages"])]),
            "ready": len([x for x in systems if x["go"]["state"] == "ready"]),
            "serious_incidents": sum(x["counts"]["serious_incidents"] for x in systems),
            "late": sum(x["counts"]["late"] for x in systems),
            "waiting_us": sum(x["counts"]["waiting_us"] for x in systems),
            "attention_critical": len([a for a in attention if a["severity"] == "critical"]),
            "attention_serious": len([a for a in attention if a["severity"] == "serious"]),
        },
        "attention": attention, "systems": systems, "people": people, "orgrisks": orgrisks, "exceptions": exc,
        "obligations": obligations, "expiring": expiring, "acceptances": accept,
        "notes": {"regulatory": regmod.DISCLAIMER},
    }
    snap = _snapshot(data)
    data["history"] = [h for h in _history(ws) if h.get("date") != snap["date"]] + [snap]
    return data


# ------------------------------------------------------------- render ----
def template_version(html):
    m = re.search(r'<meta name="aig-template-version" content="([^"]+)"', html)
    return m.group(1) if m else None


def render(data, template_text=None):
    """Fill the fixed template. The only thing that changes between runs is the data block."""
    html = template_text if template_text is not None else TEMPLATE.read_text(encoding="utf-8")
    data = dict(data)
    data["template_version"] = template_version(html)
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    # Keep the data from ever closing the script element or being read as markup.
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    if "{{AIG_DATA}}" not in html:
        raise AigError("The dashboard template has no data placeholder. Replace the framework folder with a fresh copy.")
    return html.replace("{{AIG_DATA}}", blob, 1), data


def build(ws):
    data = collect(ws)
    html, data = render(data)
    out = ws.p("dashboard")
    out.mkdir(parents=True, exist_ok=True)
    write_text(out / "index.html", html)
    write_json(out / "dashboard.json", {k: v for k, v in data.items() if k != "history"})
    snap = data["history"][-1]
    write_json(out / "history" / (snap["date"] + ".json"), snap)
    err = out / "build-error.txt"
    if err.exists():
        try:
            err.unlink()
        except OSError:
            pass
    return out / "index.html"


def try_build(ws):
    """Rebuild after a change. Never raises: a dashboard problem must not stop a record from being written."""
    try:
        build(ws)
        return True
    except Exception as e:  # noqa: BLE001
        try:
            d = ws.p("dashboard")
            d.mkdir(parents=True, exist_ok=True)
            write_text(d / "build-error.txt", "The dashboard could not be rebuilt at %s: %s: %s\nRun 'dashboard build' to see it again.\n" % (
                iso(), type(e).__name__, str(e)[:300]))
        except Exception:  # noqa: BLE001
            pass
        return False


def auto_enabled():
    return os.environ.get("AIGRCELER_NO_DASHBOARD") != "1"


def cmd_build(args, ws):
    path = build(ws)
    print("Dashboard rebuilt: %s" % path)
    print("Open it in any browser. It only reads the records; changes go through the normal commands.")
    if args.open:
        try:
            if os.name == "nt":
                os.startfile(str(path))  # noqa: S606
            else:
                import webbrowser
                webbrowser.open(Path(path).resolve().as_uri())
        except Exception as e:  # noqa: BLE001
            print("(Could not open it automatically: %s. Open the file by hand.)" % e)


def cmd_path(args, ws):
    print(ws.p("dashboard", "index.html"))
