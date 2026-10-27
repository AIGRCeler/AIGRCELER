"""Workspace-level commands: setup, roles, people, assignments, thresholds,
principles, organizational risks, exceptions, import formats."""
import shutil
from pathlib import Path

from .core import (
    AigError, WS, GOV_CAPS, DOMAINS, DOMAIN_TITLES, slug, iso, today, write_json,
    write_text, read_json, require, need_text, resolve_actor, split_list,
    is_governance_person, active_assignments, parse_date,
)

SHARED = Path(__file__).resolve().parents[2]  # .../shared

DEFAULT_ROLES = [
    {"id": "ai-governance", "name": "AI Governance", "parent": None, "governance": True,
     "default_domains": ["GO", "EA"], "caps": GOV_CAPS,
     "note": "Runs AIGRCeler for this company. Approves and finalizes controls, starts stages, "
             "decides what the tool may not. Never implements a control."},
    {"id": "executive-leadership", "name": "Executive leadership", "parent": None, "governance": False,
     "default_domains": ["GO"], "caps": ["accept_risk"],
     "note": "Accepts the highest residual risks. Owns strategy and funding."},
    {"id": "legal-compliance", "name": "Legal and compliance", "parent": "executive-leadership",
     "governance": False, "default_domains": ["HR", "TP"], "caps": [],
     "note": "Legal duties, contracts, rights of affected people, regulator contact."},
    {"id": "engineering-data-science", "name": "Engineering and data science", "parent": "executive-leadership",
     "governance": False, "default_domains": ["DG", "MD"], "caps": [],
     "note": "Builds, adapts, tests and changes the AI system and its data."},
    {"id": "security", "name": "Security", "parent": "executive-leadership",
     "governance": False, "default_domains": ["DO"], "caps": [],
     "note": "Protects the system, data and access; handles security testing and incidents."},
    {"id": "operations", "name": "Operations", "parent": "executive-leadership",
     "governance": False, "default_domains": ["DO", "HR"], "caps": [],
     "note": "Runs the system day to day, monitoring, support, user training."},
]

DEFAULT_THRESHOLDS = {
    "note": "Who may accept residual risk, by the residual level of the scenario. Edit with 'thresholds set'.",
    "accept_by": {
        "Low": ["ai-governance"],
        "Medium": ["ai-governance"],
        "High": ["ai-governance"],
        "Critical": ["executive-leadership"],
    },
}

DEFAULT_BANDS = {"Green": [0, 20], "Yellow": [21, 40], "Orange": [41, 60], "Red": [61, 100]}
DEFAULT_SCENARIO_BANDS = {"Low": [1, 4], "Medium": [5, 9], "High": [10, 16], "Critical": [17, 25]}

DEFAULT_RETENTION = {
    "full": 10, "standard": 7, "light": 5,
    "note": "Years evidence must be kept after the system is retired or last used. "
            "Provisional: 10 for the full lane follows the EU AI Act documentation period for providers of "
            "high-risk systems. Verify with counsel for your sector and jurisdictions.",
}

DEFAULT_CLOCKS = {
    "critical": {"escalate_hours": 1},
    "high": {"escalate_hours": 4},
    "medium": {"escalate_business_days": 1},
    "low": {"escalate_business_days": 5},
    "note": "Time allowed from opening an incident until AI Governance and the response owner have been told. "
            "Provisional. Regulator notice periods are tracked separately as obligations.",
}


def cmd_init(args, ws):
    if ws.exists():
        raise AigError("This folder already is a workspace.")
    if not args.company or not args.governance_name:
        raise AigError("Setup needs --company and --governance-name (the person who will act as AI Governance).")
    for d in ["00-status", "catalog/current", "catalog/versions", "catalog/proposals", "decisions", "data", "projects"]:
        ws.p(d).mkdir(parents=True, exist_ok=True)
    for code, dom in DOMAINS.items():
        ws.p("catalog", "current", dom).mkdir(parents=True, exist_ok=True)
    settings = {
        "company": args.company,
        "created": iso(),
        "domains_on": list(DOMAINS.keys()),
        "bands": DEFAULT_BANDS,
        "scenario_bands": DEFAULT_SCENARIO_BANDS,
        "retention_years": DEFAULT_RETENTION,
        "incident_clocks": DEFAULT_CLOCKS,
        "catalog_version": None,
        "catalog_dirty": False,
        "principles": "",
        "engine_version": "2.0.0",
    }
    ws.save("workspace", settings)
    ws.save("roles", DEFAULT_ROLES)
    ws.save("thresholds", DEFAULT_THRESHOLDS)
    pid = slug(args.governance_name)
    ws.save("people", [{
        "id": pid, "name": args.governance_name, "contact": args.governance_contact or "",
        "type": "internal", "folder": pid, "active": True, "added": iso()}])
    basis = args.basis or "Engagement start: person named by the company as AI Governance"
    ws.save("assignments", [{
        "id": "ASG-001", "person": pid, "role": "ai-governance", "kind": "primary",
        "from": today(), "to": None, "basis": basis}])
    ws.save("counters", {"ASG": 1})
    ws.save("organizational_risks", [])
    ws.save("exceptions", [])
    ws.save("scenarios", read_json(SHARED / "catalog" / "scenarios.json", {"scenarios": []})["scenarios"])
    ws.save("import_formats", read_json(SHARED / "catalog" / "import-formats.json", {"formats": []})["formats"])
    ws.journal().append(
        "workspace_init", ["workspace"], "setup:" + pid,
        "Workspace for %s created; %s named as AI Governance" % (args.company, args.governance_name),
        authority_basis=basis, labels=["unsigned", "self-attested"])
    print("Workspace created for %s." % args.company)
    print("AI Governance: %s. Next: adopt the starter catalog, add the people and roles, then create the first AI system." % args.governance_name)


# ------------------------------------------------------------ roles ----
def cmd_role_list(args, ws):
    people = {p["id"]: p["name"] for p in ws.load("people", [])}
    asg = active_assignments(ws)
    for r in ws.load("roles", []):
        who = [people.get(a["person"], a["person"]) + (" (deputy)" if a["kind"] == "deputy" else "")
               for a in asg if a["role"] == r["id"]]
        print("%-28s %-30s domains: %-10s people: %s" % (
            r["id"], r["name"], ",".join(r.get("default_domains", [])), "; ".join(who) or "-"))


def cmd_role_add(args, ws):
    require(ws, args.by, "manage_roles", "Changing roles")
    roles = ws.load("roles", [])
    rid = slug(args.name)
    if any(r["id"] == rid for r in roles):
        raise AigError("Role '%s' exists. Use 'role set'." % rid)
    if args.parent and not any(r["id"] == args.parent for r in roles):
        raise AigError("Parent role '%s' does not exist." % args.parent)
    roles.append({"id": rid, "name": args.name, "parent": args.parent, "governance": False,
                  "default_domains": [d.upper() for d in split_list(args.domains)],
                  "caps": [], "note": args.note or ""})
    ws.save("roles", roles)
    a = resolve_actor(ws, args.by)
    ws.journal().append("role_change", ["role:" + rid], a.decided_by, "Role added: %s" % args.name,
                        authority_basis=a.basis, labels=["unsigned"])
    print("Role added: %s" % args.name)


def cmd_role_set(args, ws):
    a = require(ws, args.by, "manage_roles", "Changing roles")
    roles = ws.load("roles", [])
    r = next((x for x in roles if x["id"] == args.role), None)
    if not r:
        raise AigError("No role '%s'." % args.role)
    if args.name:
        r["name"] = args.name
    if args.domains is not None:
        r["default_domains"] = [d.upper() for d in split_list(args.domains)]
    if args.parent is not None:
        r["parent"] = args.parent or None
    if args.note:
        r["note"] = args.note
    if r.get("governance") and args.domains is None and not (args.name or args.note or args.parent is not None):
        raise AigError("Nothing to change.")
    ws.save("roles", roles)
    ws.journal().append("role_change", ["role:" + r["id"]], a.decided_by, "Role changed: %s" % r["name"],
                        authority_basis=a.basis, labels=["unsigned"])
    print("Role updated: %s" % r["name"])


def cmd_person_add(args, ws):
    people = ws.load("people", [])
    pid = slug(args.name)
    if any(p["id"] == pid for p in people):
        raise AigError("Someone called '%s' is already in the directory." % args.name)
    people.append({"id": pid, "name": args.name, "contact": args.contact or "",
                   "type": args.type or "internal", "folder": pid, "active": True, "added": iso()})
    ws.save("people", people)
    print("Added %s. Their folder name is '%s'." % (args.name, pid))


def cmd_person_list(args, ws):
    asg = active_assignments(ws)
    for p in ws.load("people", []):
        rs = [a["role"] for a in asg if a["person"] == p["id"]]
        print("%-22s %-10s %-34s roles: %s" % (p["id"], p["type"], p["contact"], ", ".join(rs) or "-"))


def cmd_assign(args, ws):
    a = require(ws, args.by, "manage_roles", "Assigning a person to a role")
    people = {p["id"] for p in ws.load("people", [])}
    roles = {r["id"]: r for r in ws.load("roles", [])}
    if args.person not in people:
        raise AigError("'%s' is not in the people directory." % args.person)
    if args.role not in roles:
        raise AigError("No role '%s'." % args.role)
    start = parse_date(args.start, "start date") or today()
    end = parse_date(args.end, "end date")
    if end and end < start:
        raise AigError("The end date %s is before the start date %s." % (end, start))
    if args.kind and args.kind not in ("primary", "deputy"):
        raise AigError("--kind must be primary or deputy.")
    asg = ws.load("assignments", [])
    c = ws.load("counters", {})
    c["ASG"] = c.get("ASG", 0) + 1
    ws.save("counters", c)
    rec = {"id": "ASG-%03d" % c["ASG"], "person": args.person, "role": args.role,
           "kind": args.kind or "primary", "from": start, "to": end,
           "basis": args.basis or "assigned by %s" % a.name}
    asg.append(rec)
    ws.save("assignments", asg)
    ws.journal().append("role_assignment", [args.person, "role:" + args.role], a.decided_by,
                        "%s assigned to %s (%s)" % (args.person, roles[args.role]["name"], rec["kind"]),
                        authority_basis=a.basis, labels=["unsigned"])
    print("%s is now %s of %s." % (args.person, rec["kind"], roles[args.role]["name"]))


def cmd_unassign(args, ws):
    a = require(ws, args.by, "manage_roles", "Ending an assignment")
    asg = ws.load("assignments", [])
    end = parse_date(args.end, "end date")
    n = 0
    t = today()
    for r in asg:
        if r["person"] == args.person and r["role"] == args.role and not r.get("revoked") and (not r.get("to") or r["to"] >= t):
            if end:
                r["to"] = end          # ends after the close of that date
            else:
                r["revoked"] = iso()   # no end date given: ends at once, not at the end of today
                r["to"] = t
            n += 1
    if not n:
        raise AigError("No open assignment of %s to %s." % (args.person, args.role))
    ws.save("assignments", asg)
    ws.journal().append("role_assignment", [args.person, "role:" + args.role], a.decided_by,
                        "%s no longer holds role %s" % (args.person, args.role),
                        authority_basis=a.basis, labels=["unsigned"])
    print("Assignment ended%s." % (" after %s" % end if end else " now"))


def cmd_thresholds_set(args, ws):
    a = require(ws, args.by, "manage_roles", "Changing who may accept risk")
    text = need_text(args, "statement", "Changing who may accept risk")
    th = ws.load("thresholds")
    level = args.level.capitalize()
    if level not in th["accept_by"]:
        raise AigError("Level must be one of %s." % ", ".join(th["accept_by"]))
    roles = split_list(args.roles)
    known = {r["id"] for r in ws.load("roles", [])}
    for r in roles:
        if r not in known:
            raise AigError("No role '%s'." % r)
    th["accept_by"][level] = roles
    ws.save("thresholds", th)
    ws.journal().append("threshold_change", ["thresholds"], a.decided_by,
                        "Residual risk at level %s may now be accepted by: %s" % (level, ", ".join(roles)),
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Updated.")


def cmd_principles_set(args, ws):
    a = require(ws, args.by, "manage_roles", "Setting the AI principles statement")
    text = need_text(args, "text", "The AI principles statement")
    s = ws.settings()
    s["principles"] = text
    ws.save("workspace", s)
    write_text(ws.p("catalog", "AI-principles-statement.md"),
               "# AI principles of %s\n\nAdopted %s by %s.\n\n%s\n" % (s["company"], today(), a.name, text))
    ws.journal().append("principles_adopted", ["principles"], a.decided_by,
                        "AI principles statement adopted", authority_basis=a.basis,
                        labels=["unsigned"], text=text)
    print("Principles statement recorded.")


# ---------------------------------------------------- organizational risks ----
def cmd_orgrisk_add(args, ws):
    risks = ws.load("organizational_risks", [])
    c = ws.load("counters", {})
    c["ORG"] = c.get("ORG", 0) + 1
    ws.save("counters", c)
    rec = {"id": "ORG-%03d" % c["ORG"], "title": args.title, "description": args.description or "",
           "inherent": args.inherent or "Medium", "residual": args.residual or args.inherent or "Medium",
           "linked_controls": split_list(args.controls), "owner_role": args.owner_role or "executive-leadership",
           "acceptance": None, "created": iso()}
    risks.append(rec)
    ws.save("organizational_risks", risks)
    print("Organizational risk %s recorded." % rec["id"])


def cmd_orgrisk_accept(args, ws):
    risks = ws.load("organizational_risks", [])
    r = next((x for x in risks if x["id"] == args.id), None)
    if not r:
        raise AigError("No organizational risk %s." % args.id)
    a = require(ws, args.by, "accept_risk", "Accepting an organizational risk")
    text = need_text(args, "statement", "Accepting an organizational risk")
    th = ws.load("thresholds")
    allowed = th["accept_by"].get(r["residual"], [])
    if not any(a.has_role(x) for x in allowed):
        raise AigError("A %s residual risk must be accepted by: %s." % (r["residual"], ", ".join(allowed)))
    r["acceptance"] = {"by": a.person, "time": iso(), "basis": args.basis or a.basis}
    ws.save("organizational_risks", risks)
    ws.journal().append("risk_acceptance", [r["id"]], a.decided_by,
                        "Accepted organizational risk: %s (residual %s)" % (r["title"], r["residual"]),
                        authority_basis=args.basis or a.basis, labels=["unsigned"], text=text)
    print("Accepted.")


def cmd_orgrisk_list(args, ws):
    for r in ws.load("organizational_risks", []):
        print("%s  %-8s %-40s %s" % (r["id"], r["residual"], r["title"], "accepted" if r["acceptance"] else "open"))


# ------------------------------------------------------------ exceptions ----
def cmd_exception_add(args, ws):
    a = require(ws, args.by, "grant_exception", "Recording an exception")
    text = need_text(args, "statement", "Recording an exception")
    if not args.what or not args.why:
        raise AigError("An exception needs what it allows (--what) and why (--why).")
    if not args.expires:
        raise AigError("An exception must have an end date (--expires YYYY-MM-DD).")
    expires = parse_date(args.expires, "expiry date")
    if expires < today():
        raise AigError("The expiry date %s has already passed." % expires)
    if args.person and args.person not in {p["id"] for p in ws.load("people", [])}:
        raise AigError("'%s' is not in the people directory." % args.person)
    if args.project:
        pr = ws.project(args.project)
        store, getid = pr, pr.next_id("EXP", "EXP")   # own prefix: a project exception and a workspace one must never share an ID
        lst = pr.load("exceptions", [])
        scope = "project:" + pr.slug
        journal = pr.journal()
    else:
        lst = ws.load("exceptions", [])
        getid = ws.next_id("EX", "EX")
        scope = "workspace"
        journal = ws.journal()
    rec = {"id": getid, "what": args.what, "why": args.why, "approved_by": a.person,
           "time": iso(), "expires": expires, "scope": scope, "person": args.person,
           "controls": [x.upper() for x in split_list(args.controls)]}
    lst.append(rec)
    if args.project:
        pr.save("exceptions", lst)
    else:
        ws.save("exceptions", lst)
    journal.append("exception", [rec["id"]] + ([args.person] if args.person else []), a.decided_by,
                   "Exception: %s" % args.what, authority_basis=a.basis, labels=["unsigned"],
                   text="%s\n\nReason: %s\nExpires: %s\n\nDecision-maker's words:\n%s" % (args.what, args.why, args.expires, text))
    print("Exception %s recorded." % rec["id"])


def cmd_exception_list(args, ws):
    """Every exception in force or past, company-wide and for each system (or the one named with -p)."""
    from .core import today
    people = {p["id"]: p.get("name", p["id"]) for p in ws.load("people", [])}
    rows = [(e, None) for e in ws.load("exceptions", [])]
    slugs = [args.project] if getattr(args, "project", None) else ws.project_slugs()
    for slug_ in slugs:
        pr = ws.project(slug_)
        rows += [(e, pr) for e in pr.load("exceptions", [])]
    if not rows:
        print("No exceptions recorded.")
        return
    for e, pr in rows:
        ended = e.get("expires") and e["expires"] < today()
        print("%s  %s  %s  %s" % (e["id"], "company-wide" if pr is None else "system: " + pr.slug,
                                  people.get(e.get("person"), e.get("person") or "no one named"),
                                  ("ENDED %s" % e["expires"]) if ended else ("ends %s" % e.get("expires"))))
        print("    %s" % e["what"])
        print("    Covers: %s" % (", ".join(e["controls"]) if e.get("controls") else "any control (no list)"))
        if pr is not None:
            held = sorted(c["id"] for c in pr.all_controls() if c.get("exception") == e["id"])
            print("    Controls on this system that rest on it: %s" % (", ".join(held) if held else "none yet"))
        else:
            used = []
            for slug_ in ws.project_slugs():
                used += ["%s:%s" % (slug_, c["id"]) for c in ws.project(slug_).all_controls()
                         if c.get("exception") == e["id"] and e["id"] not in [x["id"] for x in ws.project(slug_).load("exceptions", [])]]
            print("    Controls that rest on it: %s" % (", ".join(sorted(used)) if used else "none yet"))


def cmd_formats_list(args, ws):
    for f in ws.load("import_formats", []):
        print("%-8s %-12s %s" % (f["id"], f["parser"], f["description"]))


def framework_version():
    """The release this copy of the framework came from; the file is written when a release is built."""
    try:
        return (SHARED / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def cmd_version(args, ws):
    fv = framework_version()
    print("AIGRCeler framework version: %s" % fv if fv else "AIGRCeler framework version: not recorded (this copy was not built from a release)")


def cmd_status(args, ws):
    s = ws.settings()
    fv = framework_version()
    if fv:
        print("AIGRCeler framework version: %s" % fv)
    print("Company: %s | catalog version: %s | projects: %d" % (
        s["company"], s.get("catalog_version") or "none adopted", len(ws.project_slugs())))
    for slug_ in ws.project_slugs():
        info = ws.project(slug_).info()
        print("  %-20s lane: %-9s stage: %s" % (slug_, info.get("lane") or "?", info.get("current_stage") or "not started"))
