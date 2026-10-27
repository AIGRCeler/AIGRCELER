"""Builds the sample data for the dashboard template: two invented AI systems at a fictional company.
It is used to look at the template, to test it, and to check that a real build has the same fields.
  py -3 make_dashboard_sample.py            writes dashboard-sample.json and ../templates/dashboard/sample.html
Dates are worked out from today, so the sample always looks current. Nothing here is a real company."""
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine"))
from aig import dashmod  # noqa: E402
from aig.core import DOMAIN_TITLES  # noqa: E402

TODAY = datetime.date.today()
NOW = datetime.datetime.now().astimezone().replace(microsecond=0)


def D(n):
    return (TODAY + datetime.timedelta(days=n)).isoformat()


def left(date_str):
    return (datetime.date.fromisoformat(date_str) - TODAY).days


CAT = json.load(open(os.path.join(HERE, "..", "catalog", "starter-catalog.json"), encoding="utf-8"))["controls"]
PEOPLE = {"executive-leadership": "Raj Patel", "legal-compliance": "Oren Weiss", "security": "Dario Fontana", "operations": "Tamsin Clarke",
          "engineering-data-science": "Mei Lin Chen", "ai-governance": "Elena Marchetti", "hr-operations": "Jonas Berg"}
FLAGS_OK = {"decisions_about_people", "personal_data", "customer_facing_automated", "regulated_sector"}


def pick(lane, mode, flags):
    out = []
    for c in CAT:
        a = c["applies"]
        if lane not in a["lanes"]:
            continue
        if "any" not in a["modes"] and mode not in a["modes"]:
            continue
        if a["requires_flags"] and not (set(a["requires_flags"]) & flags):
            continue
        out.append(c)
    return out


def rows_for(controls, plan):
    """plan: function(index, control) -> (state, due offset, strength)."""
    rows = []
    for i, c in enumerate(controls):
        state, due_off, strength = plan(i, c)
        due = D(due_off) if due_off is not None else None
        done = state in ("verified", "monitored", "waived")
        late = (-due_off if (due_off is not None and due_off < 0 and not done) else 0)
        rows.append({"id": c["id"], "title": c["title"], "area": c["id"][:2], "state": state, "owner": PEOPLE.get(c["owner_role"], "Tamsin Clarke") if state != "drafted" and state != "approved" else None,
                     "due": due, "late": late, "strength": strength, "critical": bool(c.get("critical")), "launch_required": bool(c.get("launch_required")), "waiting_on": None})
    return rows


def talentlens_plan(i, c):
    crit = c.get("critical") or c.get("launch_required")
    if i % 11 == 0:
        return ("monitored", None, "strong")
    if i % 5 == 0:
        return ("verified", None, "strong" if i % 2 else "moderate")
    if i % 17 == 3:
        return ("expired", -3, None)
    if i % 13 == 4:
        return ("rejected", -5, None)
    if i % 7 == 2:
        return ("evidenced", 6 if crit else 30, None)
    if i % 3 == 0:
        return ("implementing", -4 if (crit and i % 2) else (9 if crit else 35), None)
    if i % 29 == 1:
        return ("waived", None, None)
    if i % 4 == 0:
        return ("approved", None, None)
    return ("assigned", 10 if crit else 40, None)


def handbook_plan(i, c):
    if i % 3 == 0:
        return ("verified", None, "moderate")
    if i % 4 == 0:
        return ("evidenced", 12, None)
    if i % 2 == 0:
        return ("assigned", 20, None)
    return ("drafted", None, None)


def chase_rows(rows, us_ids, who_for):
    out = []
    for r in rows:
        st = r["state"]
        if st in ("verified", "monitored", "waived"):
            continue
        late = r["late"]
        if st == "evidenced":
            side, action = "verifier", "Evidence is filed. Someone who neither owns the control nor sent the evidence must judge it (finding record)."
        elif st in ("approved", "drafted"):
            continue
        elif r["id"] in us_ids:
            side, action = "us", "Message is written but not marked as sent. Send it, then tell the tool (control mark-sent)."
        elif st == "rejected":
            side, action = "owner", "The evidence was not accepted (see the finding). Ask %s for better evidence." % r["owner"]
        elif st == "expired":
            side, action = "owner", "Evidence expired. Ask %s for fresh evidence (request create)." % r["owner"]
        else:
            side, action = "owner", "Asked on %s (REQ-%03d); waiting for the answer." % (D(-9 - (len(out) % 5)), 30 + len(out))
        r["waiting_on"] = side
        out.append({"who": r["owner"], "kind": "control", "id": r["id"], "title": r["title"][:90], "priority": 0 if r["critical"] else 1 if r["launch_required"] else 2,
                    "due": r["due"], "late": late, "side": side, "action": action})
    out.sort(key=lambda x: (-x["late"], x["priority"], x["due"] or "9999", x["id"]))
    return out


def decisions(items, count):
    rows = [{"seq": count - i, "time": "%s %s" % (D(-1 - i // 2), "%02d:%02d" % (9 + i % 8, (i * 13) % 60)), "type": t, "by": by, "summary": s} for i, (t, by, s) in enumerate(items)]
    return {"count": count, "intact": True, "problems": [], "recent": rows, "head": "9f3c2a71be04"}


def system_talentlens():
    controls = pick("full", "embedded-in-vendor-product", FLAGS_OK)
    rows = rows_for(controls, talentlens_plan)
    us = {r["id"] for r in rows if r["state"] in ("implementing", "assigned")}
    us = set(sorted(us)[:5])
    chase = chase_rows(rows, us, None)
    for r in rows:
        if r["state"] in ("approved",):
            r["waiting_on"] = "us"
    req = [r for r in rows if r["critical"] or r["launch_required"]]
    done_req = [r for r in req if r["state"] in ("verified", "monitored", "waived")]
    s = {
        "slug": "talentlens", "name": "TalentLens", "purpose": "The candidate-ranking and automatic-rejection feature inside Kestrel, our applicant tracking system. It scores every applicant and used to reject those below a cut-off without a person looking.",
        "lane": "full", "lane_decided": True, "lane_suggested": "full", "tier": 4, "sourcing": "embedded-in-vendor-product", "current_stage": "OPERATE",
        "stages": [{"id": "DISCOVER", "status": "closed", "started": D(-27), "closed": D(-24)}, {"id": "ASSESS", "status": "closed", "started": D(-24), "closed": D(-19)},
                   {"id": "GOVERN", "status": "closed", "started": D(-19), "closed": D(-13)}, {"id": "OPERATE", "status": "started", "started": D(-13), "closed": None}],
        "go": {"state": "not_ready", "required": len(req), "done": len(done_req), "last": None, "count": 0,
               "blockers": ["%d critical control(s) are not verified yet: %s." % (len([r for r in req if r["critical"] and r not in done_req]), ", ".join([r["id"] for r in req if r["critical"] and r not in done_req][:6])),
                            "High or critical incidents are still open: INC-001."]},
        "profile": {"level": "full", "required": 41, "answered": 34, "unknown": 3, "open": 4, "rate": 3 / 41.0, "limit": 0.2},
        "controls": {"total": len(rows), "groups": dashmod._groups(rows), "by_area": dashmod._by_area(rows)},
        "control_rows": rows,
        "risk": {"scored": True, "as_of": "%s 08:40" % D(-1), "inherent": 64.5, "residual": 52.8, "inherent_band": "Red", "residual_band": "Orange", "unrated": 0,
                 "dimensions": [{"key": "accuracy", "title": "Accuracy", "max": 20, "scenarios": 5, "inherent": 14.0, "residual": 11.0},
                                {"key": "fairness", "title": "Fairness", "max": 20, "scenarios": 4, "inherent": 16.0, "residual": 14.5},
                                {"key": "data", "title": "Data", "max": 15, "scenarios": 5, "inherent": 10.0, "residual": 7.0},
                                {"key": "security", "title": "Security", "max": 15, "scenarios": 5, "inherent": 8.5, "residual": 6.0},
                                {"key": "oversight", "title": "Oversight", "max": 15, "scenarios": 4, "inherent": 8.0, "residual": 6.3},
                                {"key": "regulatory", "title": "Regulatory", "max": 15, "scenarios": 6, "inherent": 8.0, "residual": 8.0}],
                 "scenarios": [
                     {"id": "R-001", "title": "The AI gives wrong or invented answers that people act on", "dimension": "accuracy", "before": 16, "before_level": "Critical", "after": 12, "after_level": "High", "floor_applied": False, "rated": True, "accepted": False, "credits": 2},
                     {"id": "R-004", "title": "The system treats groups of applicants unfairly", "dimension": "fairness", "before": 16, "before_level": "Critical", "after": 16, "after_level": "Critical", "floor_applied": False, "rated": True, "accepted": False, "credits": 0},
                     {"id": "R-007", "title": "Applicants are rejected with no human look at the decision", "dimension": "oversight", "before": 12, "before_level": "High", "after": 6, "after_level": "Medium", "floor_applied": False, "rated": True, "accepted": False, "credits": 2},
                     {"id": "R-011", "title": "Applicant data is used or kept in ways applicants were not told about", "dimension": "data", "before": 9, "before_level": "High", "after": 6, "after_level": "Medium", "floor_applied": False, "rated": True, "accepted": False, "credits": 1},
                     {"id": "R-018", "title": "The vendor changes the model and nobody notices", "dimension": "accuracy", "before": 12, "before_level": "High", "after": 9, "after_level": "High", "floor_applied": False, "rated": True, "accepted": False, "credits": 1},
                     {"id": "R-026", "title": "Brightwell cannot show a client how the tool decides", "dimension": "regulatory", "before": 20, "before_level": "Critical", "after": 20, "after_level": "Critical", "floor_applied": True, "rated": True, "accepted": True, "credits": 0},
                     {"id": "R-029", "title": "Security weakness at the vendor exposes candidate records", "dimension": "security", "before": 8, "before_level": "Medium", "after": 4, "after_level": "Low", "floor_applied": False, "rated": True, "accepted": False, "credits": 2}],
                 "acceptances": [{"risk": "R-026", "title": "Brightwell cannot show a client how the tool decides", "level": "Critical", "by": ["Raj Patel"], "time": D(-6), "until": D(75), "days_left": 75}]},
        "evidence": {"total": 16, "by_status": {"accepted": 9, "received": 3, "expired": 2, "not-accepted": 2},
                     "expiring": [{"id": "EV-004", "control": "TP-04", "valid_until": D(9), "days_left": 9}, {"id": "EV-011", "control": "DG-05", "valid_until": D(24), "days_left": 24}],
                     "mismatch": []},
        "incidents": [
            {"id": "INC-001", "title": "Fairness reading for the lowest-scoring group is below the company's limit (version 4.2)", "severity": "high", "status": "open", "opened": D(-4), "escalate_due": "%s 16:20" % D(-4), "acknowledged": True, "overdue_ack": False, "response_owner": "Mei Lin Chen", "reportable": False, "closed": None, "lesson": None},
            {"id": "INC-003", "title": "A candidate complained they were rejected without any human review", "severity": "low", "status": "open", "opened": D(-1), "escalate_due": "%s 09:00" % D(4), "acknowledged": False, "overdue_ack": False, "response_owner": "Tamsin Clarke", "reportable": False, "closed": None, "lesson": None},
            {"id": "INC-002", "title": "Automatic rejection ran for two days after the pause was agreed", "severity": "medium", "status": "closed", "opened": D(-11), "escalate_due": "%s 10:00" % D(-10), "acknowledged": True, "overdue_ack": False, "response_owner": "Tamsin Clarke", "reportable": False, "closed": D(-8), "lesson": "A pause needs someone to confirm in writing that it is in place."}],
        "indicators": [
            {"id": "IND-001", "control": "TP-05", "metric": "Monthly fairness: selection-rate ratio of the lowest group to the best-off group", "current": 0.72, "min": 0.8, "max": None, "unit": "ratio", "status": "out_of_tolerance", "updated": D(-4), "history": [0.81, 0.79, 0.72]},
            {"id": "IND-002", "control": "HR-04", "metric": "Candidate complaints per 1,000 applicants", "current": 1.2, "min": None, "max": 2.0, "unit": "per 1,000", "status": "in_tolerance", "updated": D(-2), "history": [1.9, 1.6, 1.4, 1.3, 1.2]}],
        "obligations": [{"id": "OB-001", "title": "Halvorsen Logistics: AI hiring-tool assurance pack due to the client", "authority": "Client contract with Halvorsen Logistics", "due": D(18), "days_left": 18, "status": "open"},
                        {"id": "OB-002", "title": "Candidate notice that AI scores applications is published", "authority": "Internal commitment", "due": D(25), "days_left": 25, "status": "open"}],
        "containment": [{"id": "CT-001", "title": "Automatic rejection in Kestrel switched off; every candidate below the cut-off goes to a recruiter queue", "ends": D(40), "days_left": 40, "status": "active", "confirmed": True}],
        "exceptions": [{"id": "EX-001", "what": "Oren Weiss owns the legal controls although he holds an AI Governance role; he does not verify his own evidence.", "approved_by": "Elena Marchetti", "expires": D(60), "days_left": 60}],
        "concerns": {"open": 5, "resolved": 21, "list": [
            {"id": "CON-012", "kind": "concern", "text": "Postal code and graduation year may stand in for protected characteristics.", "carry_to": "OPERATE", "raised": D(-22)},
            {"id": "CON-019", "kind": "concern", "text": "Nobody at Brightwell has tested how well the vendor's model works on Brightwell's own candidates.", "carry_to": "OPERATE", "raised": D(-20)},
            {"id": "CON-031", "kind": "proposal", "text": "Ask Kestrel for a change notice at least 30 days before any model update.", "carry_to": "OPERATE", "raised": D(-14)},
            {"id": "CON-040", "kind": "concern", "text": "The go decision was recorded with items still open (see the record).", "carry_to": "OPERATE", "raised": D(-12)},
            {"id": "CON-044", "kind": "concern", "text": "No confirmation yet that candidates in the EU have been told AI scores them.", "carry_to": "OPERATE", "raised": D(-9)}]},
        "assessments": [{"key": "fairness", "status": "planned", "note": "Planned as analysis once the vendor's own fairness results arrive or are confirmed not to exist."},
                        {"key": "rights", "status": "planned", "note": "Carried by the human-oversight and notice controls."},
                        {"key": "dpia", "status": "planned", "note": "Counsel to say whether a data-protection assessment is needed."}],
        "blocks": [],
        "review": {"every": 90, "custom": False, "last": None, "due": D(77), "left": 77, "reasons": ["incident INC-002 (medium) closed since the last review"], "count": 0},
        "chase": chase,
        "owners": None,
        "regulatory": [{"id": "iso", "name": "ISO/IEC 42001", "items": 38, "counts": {"in place": 11, "partly in place": 9, "in progress": 12, "not determined": 0, "by how AIGRCeler works": 4, "no control applies": 2}},
                       {"id": "eu", "name": "EU AI Act", "items": 31, "counts": {"in place": 6, "partly in place": 8, "in progress": 9, "not determined": 5, "by how AIGRCeler works": 2, "no control applies": 1}},
                       {"id": "nist", "name": "NIST AI RMF", "items": 72, "counts": {"in place": 24, "partly in place": 17, "in progress": 21, "not determined": 0, "by how AIGRCeler works": 7, "no control applies": 3}}],
        "decisions": decisions([("risk_acceptance", "Raj Patel", "Accepted residual risk R-026 at level Critical until %s" % D(75)), ("incident_acknowledged", "Elena Marchetti", "Incident INC-001 seen by AI Governance"),
                                ("incident_opened", "Elena Marchetti", "Incident INC-001 opened: fairness reading below the limit"), ("evidence_finding", "Oren Weiss", "Evidence EV-009 judged satisfied for TP-05 (strong)"),
                                ("request_sent", "Elena Marchetti", "Message REQ-054 to Lila Brandt marked sent"), ("signoff_refused", "Elena Marchetti", "Go decision not recorded: critical controls still open"),
                                ("stage_started", "Elena Marchetti", "Operate started"), ("stage_closed", "Elena Marchetti", "Govern closed")], 187),
    }
    owners = {}
    for r in chase:
        o = owners.setdefault(r["who"], {"who": r["who"], "open": 0, "late": 0})
        o["open"] += 1
        o["late"] += 1 if r["late"] else 0
    s["owners"] = sorted(owners.values(), key=lambda o: (-o["late"], -o["open"], o["who"]))
    s["counts"] = {"open_incidents": 2, "serious_incidents": 1, "late": len([r for r in rows if r["late"]]), "waiting_us": len([r for r in chase if r["side"] == "us"]),
                   "verifier_queue": len([r for r in chase if r["side"] == "verifier"]), "indicators_out": 1}
    return s


def system_handbook():
    controls = pick("light", "third-party-service", set())
    rows = rows_for(controls, handbook_plan)
    chase = chase_rows(rows, set(), None)
    req = [r for r in rows if r["critical"] or r["launch_required"]]
    done_req = [r for r in req if r["state"] in ("verified", "monitored", "waived")]
    s = {
        "slug": "handbookbot", "name": "HandbookBot", "purpose": "An internal chatbot that answers staff questions from the public employee handbook. A third-party service; no personal data on its face.",
        "lane": "light", "lane_decided": True, "lane_suggested": "light", "tier": 1, "sourcing": "third-party-service", "current_stage": "GOVERN",
        "stages": [{"id": "DISCOVER", "status": "closed", "started": D(-9), "closed": D(-8)}, {"id": "ASSESS", "status": "closed", "started": D(-8), "closed": D(-7)},
                   {"id": "GOVERN", "status": "started", "started": D(-7), "closed": None}, {"id": "OPERATE", "status": "not_started", "started": None, "closed": None}],
        "go": {"state": "not_in_operate", "required": len(req), "done": len(done_req), "last": None, "count": 0, "blockers": []},
        "profile": {"level": "light", "required": 14, "answered": 14, "unknown": 0, "open": 0, "rate": 0.0, "limit": 0.2},
        "controls": {"total": len(rows), "groups": dashmod._groups(rows), "by_area": dashmod._by_area(rows)},
        "control_rows": rows,
        "risk": {"scored": True, "as_of": "%s 11:02" % D(-6), "inherent": 21.5, "residual": 12.4, "inherent_band": "Yellow", "residual_band": "Green", "unrated": 0,
                 "dimensions": [{"key": "accuracy", "title": "Accuracy", "max": 20, "scenarios": 1, "inherent": 6.0, "residual": 4.0}, {"key": "fairness", "title": "Fairness", "max": 20, "scenarios": 0, "inherent": 0.0, "residual": 0.0},
                                {"key": "data", "title": "Data", "max": 15, "scenarios": 1, "inherent": 5.0, "residual": 3.0}, {"key": "security", "title": "Security", "max": 15, "scenarios": 1, "inherent": 5.5, "residual": 3.4},
                                {"key": "oversight", "title": "Oversight", "max": 15, "scenarios": 1, "inherent": 5.0, "residual": 2.0}, {"key": "regulatory", "title": "Regulatory", "max": 15, "scenarios": 0, "inherent": 0.0, "residual": 0.0}],
                 "scenarios": [{"id": "R-001", "title": "The chatbot gives a wrong answer about leave or pay that staff act on", "dimension": "accuracy", "before": 6, "before_level": "Medium", "after": 4, "after_level": "Low", "floor_applied": False, "rated": True, "accepted": False, "credits": 1},
                               {"id": "R-002", "title": "Staff paste personal details into the chatbot", "dimension": "data", "before": 6, "before_level": "Medium", "after": 3, "after_level": "Low", "floor_applied": False, "rated": True, "accepted": False, "credits": 1}],
                 "acceptances": []},
        "evidence": {"total": 5, "by_status": {"accepted": 3, "received": 2}, "expiring": [], "mismatch": []},
        "incidents": [], "indicators": [], "obligations": [], "containment": [], "exceptions": [],
        "concerns": {"open": 1, "resolved": 4, "list": [{"id": "CON-003", "kind": "concern", "text": "The handbook itself is out of date in two places, so correct answers may still be wrong.", "carry_to": "GOVERN", "raised": D(-5)}]},
        "assessments": [], "blocks": [], "review": None, "chase": chase, "owners": None,
        "regulatory": [{"id": "iso", "name": "ISO/IEC 42001", "items": 38, "counts": {"in place": 3, "partly in place": 2, "in progress": 4, "not determined": 0, "by how AIGRCeler works": 4, "no control applies": 25}},
                       {"id": "eu", "name": "EU AI Act", "items": 31, "counts": {"in place": 1, "partly in place": 1, "in progress": 1, "not determined": 2, "by how AIGRCeler works": 2, "no control applies": 24}},
                       {"id": "nist", "name": "NIST AI RMF", "items": 72, "counts": {"in place": 6, "partly in place": 4, "in progress": 6, "not determined": 0, "by how AIGRCeler works": 7, "no control applies": 49}}],
        "decisions": decisions([("stage_started", "Elena Marchetti", "Govern started (light lane)"), ("risk_rescored", "AIGRCeler", "Risk rescored: before 21.5, after 12.4"), ("stage_closed", "Elena Marchetti", "Assess closed")], 64),
    }
    owners = {}
    for r in chase:
        o = owners.setdefault(r["who"], {"who": r["who"], "open": 0, "late": 0})
        o["open"] += 1
    s["owners"] = sorted(owners.values(), key=lambda o: (-o["late"], -o["open"], o["who"]))
    s["counts"] = {"open_incidents": 0, "serious_incidents": 0, "late": 0, "waiting_us": len([r for r in chase if r["side"] == "us"]),
                   "verifier_queue": len([r for r in chase if r["side"] == "verifier"]), "indicators_out": 0}
    return s


def build():
    systems = [system_talentlens(), system_handbook()]
    for s in systems:
        s["attention"] = dashmod._attention(s["slug"], s["name"], s)
        s["attention"].sort(key=lambda a: dashmod.SEV_RANK[a["severity"]])
    attention = [a for s in systems for a in s["attention"]]
    attention.sort(key=lambda a: dashmod.SEV_RANK[a["severity"]])
    people = []
    for nm, roles in (("Mei Lin Chen", ["Engineering and data science"]), ("Tamsin Clarke", ["Operations"]), ("Dario Fontana", ["Security"]), ("Oren Weiss", ["Legal and compliance", "AI Governance deputy"]),
                      ("Jonas Berg", ["Operations"]), ("Raj Patel", ["Executive leadership"]), ("Elena Marchetti", ["AI Governance"]), ("Lila Brandt", [])):
        mine = [(s, r) for s in systems for r in s["chase"] if r["who"] == nm]
        people.append({"name": nm, "type": "external" if nm == "Lila Brandt" else "internal", "roles": roles, "open": len(mine), "late": len([1 for _s, r in mine if r["late"]]), "systems": sorted({s["name"] for s, _r in mine})})
    people.sort(key=lambda x: (-x["late"], -x["open"], x["name"]))
    hist = []
    for k in range(20, -1, -1):
        date = (TODAY - datetime.timedelta(days=k)).isoformat()
        p = (20 - k) / 20.0
        hist.append({"date": date, "systems": {
            "talentlens": {"residual": round(64.5 - 11.7 * p, 1), "inherent": 64.5, "required_done": int(2 + (systems[0]["go"]["done"] - 2) * p), "required_total": systems[0]["go"]["required"],
                           "in_place": int(3 + (systems[0]["controls"]["groups"]["in_place"] - 3) * p), "controls": systems[0]["controls"]["total"], "open_incidents": 0 if k > 4 else (1 if k > 1 else 2),
                           "late": int(systems[0]["counts"]["late"] * min(1.0, p * 1.4)), "waiting_us": max(0, int(9 - 9 * p) + systems[0]["counts"]["waiting_us"] // 2)},
            "handbookbot": {"residual": round(21.5 - 9.1 * p, 1), "inherent": 21.5, "required_done": int(systems[1]["go"]["done"] * p), "required_total": systems[1]["go"]["required"],
                            "in_place": int(systems[1]["controls"]["groups"]["in_place"] * p), "controls": systems[1]["controls"]["total"], "open_incidents": 0, "late": 0, "waiting_us": 1}}})
    data = {
        "contract": dashmod.CONTRACT, "generated": NOW.isoformat(), "engine_version": "2.0.0", "template_version": None, "config": {"title": None, "accent": None, "hide": [], "logo": None},
        "company": {"name": "Brightwell Talent Partners (sample data)", "catalog_version": "1.0", "journal": {"intact": True, "problems": [], "count": 41, "head": "c47a90de1b22"}},
        "totals": {"systems": 2, "in_operate": 1, "ready": 0, "serious_incidents": 1, "late": sum(s["counts"]["late"] for s in systems), "waiting_us": sum(s["counts"]["waiting_us"] for s in systems),
                   "attention_critical": len([a for a in attention if a["severity"] == "critical"]), "attention_serious": len([a for a in attention if a["severity"] == "serious"])},
        "attention": attention, "systems": systems, "people": people,
        "orgrisks": [{"id": "ORG-001", "title": "Kestrel can switch on new AI features without telling us", "inherent": "High", "residual": "High", "accepted": False}],
        "exceptions": [{"id": "EX-001", "what": "Oren Weiss owns the legal controls although he holds an AI Governance role.", "expires": D(60), "days_left": 60}],
        "obligations": sorted([dict(o, system="TalentLens", slug="talentlens") for o in systems[0]["obligations"]], key=lambda o: o["due"]),
        "expiring": [dict(e, system="TalentLens", slug="talentlens") for e in systems[0]["evidence"]["expiring"]],
        "acceptances": [dict(a, system="TalentLens", slug="talentlens") for a in systems[0]["risk"]["acceptances"]],
        "notes": {"regulatory": "This is AIGRCeler's own mapping of where each requirement is met. It is not legal advice, it is not a statement that the company complies, and it is not a certification. Whether a duty applies to a given system is a question for counsel; certification is decided by an accredited body."},
        "history": hist,
    }
    return data


if __name__ == "__main__":
    data = build()
    json.dump(data, open(os.path.join(HERE, "dashboard-sample.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    html, _ = dashmod.render(data)
    out = os.path.join(HERE, "..", "templates", "dashboard", "sample.html")
    open(out, "w", encoding="utf-8").write(html)
    print("Wrote dashboard-sample.json and", os.path.normpath(out))
