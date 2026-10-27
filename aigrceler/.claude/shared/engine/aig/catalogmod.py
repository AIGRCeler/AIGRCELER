"""The control catalog: AI Governance owns it. Changes begin as proposals."""
import json
import re
from pathlib import Path

from .core import (
    AigError, DOMAINS, TRUST_PROPERTIES, SOURCING_MODES, LANES, iso, today,
    read_json, write_json, require, need_text, resolve_actor, split_list, domain_of,
    CREDIT_STATES, read_any_text,
)
from .wsmod import SHARED

REQUIRED = ["id", "title", "trust_properties", "objective", "requirement", "applies", "scenarios",
            "type", "max_steps", "acceptance", "evidence_types", "valid_days", "owner_role"]


ID_RE = re.compile(r"^[A-Z]{2}-[0-9]{2,3}$")


def validate_def(d):
    if not isinstance(d, dict):
        raise AigError("A control definition must be a set of named fields.")
    miss = [k for k in REQUIRED if k not in d]
    if miss:
        raise AigError("Control definition is missing: %s." % ", ".join(miss))
    if not isinstance(d["id"], str) or not ID_RE.match(d["id"]):
        raise AigError("A control ID looks like GO-01 or DG-12 (two capital letters, a dash, two or three digits).")
    if domain_of(d["id"]) not in DOMAINS:
        raise AigError("Control ID %s must start with one of %s-." % (d["id"], "-, ".join(DOMAINS)))
    if d["type"] not in ("preventive", "detective", "corrective"):
        raise AigError("Type must be preventive, detective or corrective.")
    for t in d["trust_properties"]:
        if t not in TRUST_PROPERTIES:
            raise AigError("Unknown trust property '%s'." % t)
    ap = d["applies"]
    for m in ap.get("modes", []):
        if m != "any" and m not in SOURCING_MODES:
            raise AigError("Unknown sourcing mode '%s' in %s." % (m, d["id"]))
    for l in ap.get("lanes", []):
        if l not in LANES:
            raise AigError("Unknown lane '%s' in %s." % (l, d["id"]))
    if not isinstance(d["max_steps"], int) or not 0 <= d["max_steps"] <= 2:
        raise AigError("max_steps must be 0, 1 or 2.")
    return d


def defpath(ws, cid, status_dir="current"):
    return ws.p("catalog", status_dir, DOMAINS[domain_of(cid)], cid + ".json")


def load_defs(ws, include_retired=False):
    out = {}
    base = ws.p("catalog", "current")
    if base.exists():
        for f in sorted(base.glob("*/*.json")):
            d = read_json(f)
            if d.get("status", "active") == "retired" and not include_retired:
                continue
            out[d["id"]] = d
    return out


def bump(version):
    major, minor = str(version).split(".")
    return "%s.%d" % (major, int(minor) + 1)


def legal_index(defs):
    idx = {}
    for d in defs.values():
        for ref in d.get("legal", []):
            idx.setdefault(ref, []).append(d["id"])
    return idx


def cmd_adopt_starter(args, ws):
    a = require(ws, args.by, "approve_catalog", "Adopting the starter catalog")
    text = need_text(args, "statement", "Adopting the starter catalog")
    s = ws.settings()
    if s.get("catalog_version"):
        raise AigError("A catalog is already adopted (version %s)." % s["catalog_version"])
    src = read_json(SHARED / "catalog" / "starter-catalog.json")
    n = 0
    for d in src["controls"]:
        validate_def(d)
    for d in src["controls"]:
        d = dict(d)
        d.setdefault("status", "active")
        d.setdefault("version", "1.0")
        write_json(defpath(ws, d["id"]), d)
        n += 1
    s["catalog_version"] = "1.0"
    s["catalog_dirty"] = False
    s["catalog_origin"] = {"starter": src.get("name"), "starter_version": src.get("version"), "adopted": iso()}
    ws.save("workspace", s)
    snap = {"version": "1.0", "date": iso(), "approved_by": a.person, "changes": [
        {"id": d["id"], "change": "adopted from starter catalog", "def_version": d.get("version", "1.0")}
        for d in src["controls"]], "definitions": {d["id"]: d.get("version", "1.0") for d in src["controls"]}}
    write_json(ws.p("catalog", "versions", "catalog-v1.0.json"), snap)
    ws.journal().append("catalog_version", ["catalog:1.0"], a.decided_by,
                        "Adopted the starter catalog (%d controls) as the company's own, version 1.0" % n,
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Catalog adopted: %d controls, version 1.0. From now on AI Governance owns every change." % n)


def cmd_list(args, ws):
    defs = load_defs(ws)
    for d in defs.values():
        if args.domain and domain_of(d["id"]) != args.domain.upper():
            continue
        print("%-7s v%-4s %-9s %-12s %s" % (d["id"], d["version"], d["type"],
                                         ("critical" if d.get("critical") else ""), d["title"]))
    print("%d controls (catalog version %s)" % (len(defs), ws.settings().get("catalog_version")))


def cmd_show(args, ws):
    defs = load_defs(ws, True)
    if args.id not in defs:
        raise AigError("No control %s in the catalog." % args.id)
    print(json.dumps(defs[args.id], indent=2, ensure_ascii=False))


def cmd_coverage(args, ws):
    idx = legal_index(load_defs(ws))
    for ref in sorted(idx):
        print("%-40s %s" % (ref, ", ".join(idx[ref])))
    print("%d legal references covered." % len(idx))


def cmd_impact(args, ws):
    cur = load_defs(ws, True).get(args.id)
    if not cur:
        raise AigError("No control %s in the catalog." % args.id)
    n = 0
    for slug_ in ws.project_slugs():
        pr = ws.project(slug_)
        if pr.has_control(args.id):
            c = pr.get_control(args.id)
            old = c["definition"].get("version")
            flag = "" if old == cur["version"] else "  (on version %s; catalog has %s)" % (old, cur["version"])
            print("%-20s state: %-12s%s" % (slug_, c["state"], flag))
            n += 1
    print("%d AI systems carry this control." % n)


# ---------------------------------------------------------- proposals ----
def _prop_dir(ws):
    return ws.p("catalog", "proposals")


def _load_prop(ws, pid):
    p = read_json(_prop_dir(ws) / (pid + ".json"))
    if p is None:
        raise AigError("No proposal %s." % pid)
    return p


def cmd_propose(args, ws):
    """Anyone, including the tool, may propose. Only AI Governance decides."""
    if args.kind not in ("add", "edit", "retire", "review"):
        raise AigError("Kind must be add, edit, retire or review.")
    defs = load_defs(ws, True)
    if args.kind in ("edit", "retire", "review") and args.id and args.id not in defs:
        raise AigError("No control %s to %s." % (args.id, args.kind))
    change = {}
    if args.change:
        src = args.change.strip()
        if src.startswith("{"):
            try:
                change = json.loads(src)
            except ValueError as e:
                raise AigError("The change is not valid JSON: %s" % e)
        else:
            p = Path(src)
            if not p.is_file():
                raise AigError("Change file not found: %s" % src)
            try:
                change = json.loads(read_any_text(p))
            except ValueError as e:
                raise AigError("The change file is not valid JSON: %s" % e)
        if not isinstance(change, dict):
            raise AigError("The change must be a set of named fields.")
    if args.kind == "add":
        validate_def(change)
    if not args.reason or len(args.reason.strip()) < 10:
        raise AigError("A proposal needs a reason in a sentence (--reason).")
    pid = ws.next_id("P", "P")
    affected = []
    if args.kind in ("edit", "retire", "review") and args.id:
        for slug_ in ws.project_slugs():
            if ws.project(slug_).has_control(args.id):
                affected.append(slug_)
    rec = {"id": pid, "source": args.source or "manual", "ref": args.ref, "kind": args.kind,
           "target": args.id or (change.get("id") if change else None), "change": change,
           "reason": args.reason, "status": "open", "created": iso(), "proposed_by": resolve_actor(ws, args.by).decided_by,
           "projects_affected": affected}
    write_json(_prop_dir(ws) / (pid + ".json"), rec)
    print("Proposal %s filed (%s %s). Waiting for AI Governance. Affects: %s" % (
        pid, args.kind, rec["target"], ", ".join(affected) or "no AI system yet"))


def cmd_proposals(args, ws):
    for f in sorted(_prop_dir(ws).glob("P-*.json")):
        p = read_json(f)
        if args.status and p["status"] != args.status:
            continue
        print("%s  %-8s %-8s %-9s %s (source: %s)" % (p["id"], p["status"], p["kind"], p["target"], p["reason"][:70], p["source"]))


def cmd_proposal_show(args, ws):
    print(json.dumps(_load_prop(ws, args.id), indent=2, ensure_ascii=False))


def cmd_proposal_decline(args, ws):
    a = require(ws, args.by, "approve_catalog", "Declining a catalog proposal")
    text = need_text(args, "statement", "Declining a catalog proposal")
    p = _load_prop(ws, args.id)
    if p["status"] != "open":
        raise AigError("Proposal %s is already %s." % (p["id"], p["status"]))
    p.update(status="declined", decided_by=a.person, decided=iso(), decision_text=text)
    write_json(_prop_dir(ws) / (p["id"] + ".json"), p)
    ws.journal().append("catalog_proposal_decided", [p["id"]], a.decided_by,
                        "Declined proposal %s (%s %s)" % (p["id"], p["kind"], p["target"]),
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Declined.")


def cmd_proposal_approve(args, ws):
    a = require(ws, args.by, "approve_catalog", "Approving a catalog proposal")
    text = need_text(args, "statement", "Approving a catalog proposal")
    p = _load_prop(ws, args.id)
    if p["status"] != "open":
        raise AigError("Proposal %s is already %s." % (p["id"], p["status"]))
    defs = load_defs(ws, True)
    warn = []
    if p["kind"] == "review":
        p.update(status="approved", decided_by=a.person, decided=iso(), decision_text=text)
        write_json(_prop_dir(ws) / (p["id"] + ".json"), p)
        ws.journal().append("catalog_proposal_decided", [p["id"]], a.decided_by,
                            "Reviewed proposal %s (%s); no change to the control text" % (p["id"], p["target"]),
                            authority_basis=a.basis, labels=["unsigned"], text=text + "\n\nReason on the proposal: " + p["reason"])
        print("Review recorded. If the control text should change, file an edit proposal.")
        return
    if p["kind"] == "add":
        d = dict(p["change"])
        if d["id"] in defs:
            raise AigError("Control %s already exists." % d["id"])
        d.setdefault("status", "active")
        d["version"] = "1.0"
        validate_def(d)
        write_json(defpath(ws, d["id"]), d)
    else:
        d = dict(defs[p["target"]])
        legal = d.get("legal", [])
        if legal and len((p["reason"] or "").strip()) < 15:
            raise AigError("%s is tied to legal requirements (%s). Editing or retiring it needs a recorded reason of at least a sentence." % (d["id"], ", ".join(legal)))
        if p["kind"] == "retire":
            d["status"] = "retired"
            d["version"] = bump(d["version"])
            others = legal_index({k: v for k, v in defs.items() if k != d["id"] and v.get("status", "active") != "retired"})
            for ref in legal:
                if ref not in others:
                    warn.append(ref)
        else:
            old_legal = set(d.get("legal", []))
            for k, v in p["change"].items():
                if k in ("id", "version", "status"):
                    continue
                d[k] = v
            d["version"] = bump(d["version"])
            others = legal_index({k: v for k, v in defs.items() if k != d["id"] and v.get("status", "active") != "retired"})
            for ref in old_legal - set(d.get("legal", [])):
                if ref not in others:
                    warn.append(ref)
        validate_def(d)
        write_json(defpath(ws, d["id"]), d)
    s = ws.settings()
    s["catalog_dirty"] = True
    ws.save("workspace", s)
    p.update(status="approved", decided_by=a.person, decided=iso(), decision_text=text, applied_version=d["version"])
    if warn:
        p["uncovered_after_change"] = warn
    write_json(_prop_dir(ws) / (p["id"] + ".json"), p)
    ws.journal().append("catalog_proposal_decided", [p["id"], d["id"]], a.decided_by,
                        "Approved proposal %s: %s %s (now version %s)%s" % (
                            p["id"], p["kind"], d["id"], d["version"],
                            "; leaves uncovered: " + ", ".join(warn) if warn else ""),
                        authority_basis=a.basis, labels=["unsigned"],
                        text=text + "\n\nReason on the proposal: " + p["reason"])
    if p["kind"] == "retire":
        pass
    print("Approved. %s is now version %s. Release a new catalog version when you have finished editing." % (d["id"], d["version"]))
    if warn:
        print("WARNING: no other control now covers: %s" % ", ".join(warn))
    if p["projects_affected"]:
        print("AI systems on an older version of this control (upgrade needs AI Governance): %s" % ", ".join(p["projects_affected"]))


def cmd_release(args, ws):
    a = require(ws, args.by, "approve_catalog", "Releasing a catalog version")
    text = need_text(args, "statement", "Releasing a catalog version")
    s = ws.settings()
    if not s.get("catalog_version"):
        raise AigError("Adopt the starter catalog first.")
    if not s.get("catalog_dirty"):
        raise AigError("Nothing has changed since version %s." % s["catalog_version"])
    old = read_json(ws.p("catalog", "versions", "catalog-v%s.json" % s["catalog_version"]))
    defs = load_defs(ws, True)
    cur = {k: v["version"] for k, v in defs.items()}
    changes = []
    for k, v in cur.items():
        if old["definitions"].get(k) != v:
            changes.append({"id": k, "change": "new" if k not in old["definitions"] else "changed", "def_version": v})
    newv = bump(s["catalog_version"])
    write_json(ws.p("catalog", "versions", "catalog-v%s.json" % newv),
               {"version": newv, "date": iso(), "approved_by": a.person, "changes": changes, "definitions": cur})
    s["catalog_version"] = newv
    s["catalog_dirty"] = False
    ws.save("workspace", s)
    ws.journal().append("catalog_version", ["catalog:" + newv], a.decided_by,
                        "Released catalog version %s (%d changes)" % (newv, len(changes)),
                        authority_basis=a.basis, labels=["unsigned"], text=text)
    print("Catalog version %s released with %d changes." % (newv, len(changes)))


def behind_starter(ws):
    """Starter controls this version of the product ships with that the company's catalog does not have yet."""
    if not ws.settings().get("catalog_version"):
        return []
    src = read_json(SHARED / "catalog" / "starter-catalog.json")
    defs = load_defs(ws, True)
    return [d["id"] for d in src["controls"] if d["id"] not in defs]


def cmd_sync_starter(args, ws):
    """Add the starter controls the company's catalog does not have yet. Existing controls are never changed: the company owns them."""
    a = require(ws, args.by, "approve_catalog", "Adding new starter controls to the catalog")
    text = need_text(args, "statement", "Adding new starter controls to the catalog")
    s = ws.settings()
    if not s.get("catalog_version"):
        raise AigError("Adopt the starter catalog first.")
    src = read_json(SHARED / "catalog" / "starter-catalog.json")
    defs = load_defs(ws, True)
    missing = [d for d in src["controls"] if d["id"] not in defs]
    differ = [d["id"] for d in src["controls"] if d["id"] in defs and
              (d.get("requirement") != defs[d["id"]].get("requirement") or d.get("acceptance") != defs[d["id"]].get("acceptance"))]
    if not missing:
        print("Nothing to add: the catalog already has every starter control.")
    else:
        for d in missing:
            validate_def(d)
        for d in missing:
            d = dict(d)
            d.setdefault("status", "active")
            d.setdefault("version", "1.0")
            write_json(defpath(ws, d["id"]), d)
        old = read_json(ws.p("catalog", "versions", "catalog-v%s.json" % s["catalog_version"]))
        cur = {k: v["version"] for k, v in load_defs(ws, True).items()}
        newv = bump(s["catalog_version"])
        write_json(ws.p("catalog", "versions", "catalog-v%s.json" % newv),
                   {"version": newv, "date": iso(), "approved_by": a.person,
                    "changes": [{"id": d["id"], "change": "new (from starter catalog %s)" % src.get("version"), "def_version": d.get("version", "1.0")} for d in missing],
                    "definitions": cur})
        s["catalog_version"] = newv
        s["catalog_dirty"] = False
        ws.save("workspace", s)
        ws.journal().append("catalog_version", ["catalog:" + newv], a.decided_by,
                            "Added %d new starter control(s) to the catalog: %s. Released version %s." % (len(missing), ", ".join(d["id"] for d in missing), newv),
                            authority_basis=a.basis, labels=["unsigned"], text=text)
        print("Added %d new control(s): %s. Catalog version %s. Systems already past Govern keep what they have; the new controls appear when controls are next drafted." % (
            len(missing), ", ".join(d["id"] for d in missing), newv))
    if differ:
        print("The starter wording differs from the company's for: %s. The company's own wording was left as it is; see 'catalog propose' to adopt a change." % ", ".join(differ))
