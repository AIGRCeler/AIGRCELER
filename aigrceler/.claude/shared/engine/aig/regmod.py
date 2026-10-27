"""The regulatory map: how AIGRCeler covers ISO/IEC 42001, the EU AI Act and the NIST AI RMF.

The map (shared/catalog/regulatory-map.json) lists every clause, article and subcategory with how it is covered:
by which controls, by which mechanism of the product, and which discovery questions supply the facts.
It is an indicative pointer for traceability, not legal advice and not a statement that the company complies.
Whether a duty applies is a question for counsel."""
from .core import AigError, read_json
from .wsmod import SHARED

DISCLAIMER = ("This is AIGRCeler's own mapping of where each requirement is met. It is not legal advice, "
              "it is not a statement that the company complies, and it is not a certification. Whether a duty applies "
              "to a given system is a question for counsel; certification is decided by an accredited body.")
IN_PLACE = ("verified", "monitored")
LIVE_NOT_IN_PLACE = ("drafted", "approved", "assigned", "implementing", "submitted", "received", "rejected", "expired")
_CACHE = {}


def regmap():
    if "m" not in _CACHE:
        _CACHE["m"] = read_json(SHARED / "catalog" / "regulatory-map.json")
    return _CACHE["m"]


def framework(fid):
    f = (fid or "").lower()
    alias = {"iso": "iso", "42001": "iso", "iso42001": "iso", "eu": "eu", "euaiact": "eu", "ai-act": "eu", "nist": "nist", "rmf": "nist"}
    f = alias.get(f, f)
    for fw in regmap()["frameworks"]:
        if fw["id"] == f:
            return fw
    raise AigError("Framework must be one of: iso, eu, nist.")


def _starter_titles():
    if "t" not in _CACHE:
        _CACHE["t"] = {c["id"]: c["title"] for c in read_json(SHARED / "catalog" / "starter-catalog.json")["controls"]}
    return _CACHE["t"]


def _adopted_ids(ws):
    try:
        from .catalogmod import load_defs
        return set(load_defs(ws).keys())
    except Exception:
        return set()


def counts(fw):
    c = {"covered": 0, "partial": 0, "gap": 0}
    for it in fw["items"]:
        c[it["status"]] += 1
    return c


def cmd_coverage(args, ws):
    m = regmap()
    fws = [framework(args.framework)] if args.framework else m["frameworks"]
    adopted = _adopted_ids(ws)
    print("Regulatory map. " + DISCLAIMER + "\n")
    missing = set()
    for fw in fws:
        c = counts(fw)
        print("%s: %d items. %d covered, %d partly covered, %d not covered." % (fw["name"], len(fw["items"]), c["covered"], c["partial"], c["gap"]))
        for it in fw["items"]:
            if args.status and it["status"] != args.status:
                continue
            if it["status"] != "covered" or args.status:
                print("  - %s %s [%s]: %s" % (fw["tag"], it["ref"], it["status"], it["note"] or "no note"))
            if adopted:
                for cid in it["controls"]:
                    if cid not in adopted:
                        missing.add(cid)
    if missing:
        print("\nControls this map relies on that your adopted catalog does not have: %s." % ", ".join(sorted(missing)))
        print("The starter catalog has newer controls. AI Governance adds them with: catalog sync-starter --by <name> --statement \"<their words>\".")


def cmd_item(args, ws):
    if not args.ref:
        raise AigError("Give the clause, article or subcategory (--ref), for example A.5.2, Art. 27 or MAP 5.1.")
    ref = args.ref.strip().lower().replace("iso 42001", "").replace("eu ai act", "").replace("nist ai rmf", "").strip()
    hits = []
    for fw in regmap()["frameworks"]:
        for it in fw["items"]:
            if it["ref"].lower() == ref or it["ref"].lower() == "art. " + ref:
                hits.append((fw, it))
    if not hits:
        raise AigError("No item '%s' in the map." % args.ref)
    titles = _starter_titles()
    for fw, it in hits:
        print("%s %s: %s\n  Status: %s" % (fw["tag"], it["ref"], it["title"], it["status"]))
        if it["controls"]:
            print("  Controls: " + "; ".join("%s %s" % (c, titles.get(c, "")) for c in it["controls"]))
        if it["mechanisms"]:
            print("  How AIGRCeler works: " + "; ".join(regmap()["mechanisms"][k] for k in it["mechanisms"]))
        if it["profile"]:
            print("  Discovery questions that supply the facts: " + ", ".join(it["profile"]))
        if it["note"]:
            print("  Note: " + it["note"])
        if fw["id"] == "eu":
            print("  Applies to: roles %s, classes %s (a question for counsel)." % (", ".join(it["roles"]), ", ".join(it["classes"])))


# ------------------------------------------------------------ per system ----
def _system_context(ws, pr):
    from . import profmod
    info = pr.info()
    st = profmod.state(ws, pr, info)
    ans = {r["def"]["id"]: profmod.answer_of(r["def"], r["entry"]) for r in st["rows"] if r["entry"]}
    role = ans.get("eu_role")
    cls = {"high-risk": "high-risk", "transparency-duty": "limited", "minimal": "minimal", "prohibited-concern": "prohibited"}.get(ans.get("eu_class_view"))
    if info["flags"].get("eu_high_risk"):
        cls = "high-risk"
    nexus = ans.get("eu_nexus")
    return {"info": info, "role": role if role not in (None, "none", "not-sure") else None, "role_raw": role,
            "cls": cls, "nexus": nexus}


def _applies(it, ctx):
    """True, False or None (not determined)."""
    if ctx["nexus"] == "no":
        return False
    roles, classes = it["roles"], it["classes"]
    rok = True if "any" in roles else (None if ctx["role"] is None else ctx["role"] in roles)
    cok = True if "any" in classes else (None if ctx["cls"] is None else ctx["cls"] in classes)
    if rok is False or cok is False:
        return False
    if rok is None or cok is None:
        return None
    return True


def _item_state(it, controls):
    live = {c["id"]: c for c in controls if c["state"] != "retired"}
    mine = [c for c in it["controls"] if c in live]
    if not it["controls"]:
        return "by how AIGRCeler works", []
    if not mine:
        return "no control applies to this system in its lane", []
    states = [live[c]["state"] for c in mine]
    if all(s in IN_PLACE or s == "waived" for s in states):
        return "in place", mine
    if any(s in IN_PLACE for s in states):
        return "partly in place", mine
    return "in progress", mine


def render_project(ws, pr, fid=None):
    ctx = _system_context(ws, pr)
    cs = pr.all_controls()
    fws = [framework(fid)] if fid else regmap()["frameworks"]
    out = ["# Regulatory view: %s\n" % pr.info()["name"], DISCLAIMER + "\n"]
    for fw in fws:
        out.append("## %s\n" % fw["name"])
        if fw["id"] == "eu":
            n = ctx["nexus"]
            out.append("EU link: %s. Role the company gave: %s. Class the company gave: %s. Which duties apply is a question for counsel; "
                       "the table shows where they would be met if they do.\n" % (
                           {"yes": "yes", "no": "no", "not-sure": "not sure"}.get(n, "not answered yet"), ctx["role_raw"] or "not answered yet", ctx["cls"] or "not answered yet"))
        out.append("| Item | Status in the map | For this system | Controls (state) |")
        out.append("|---|---|---|---|")
        for it in fw["items"]:
            ap = _applies(it, ctx) if fw["id"] == "eu" else True
            if ap is False:
                continue
            stt, mine = _item_state(it, cs)
            if ap is None:
                stt = "applicability not determined (question for counsel); " + stt
            live = {c["id"]: c["state"] for c in cs}
            ctl = ", ".join("%s (%s)" % (c, live.get(c)) for c in mine) or "-"
            out.append("| %s %s | %s | %s | %s |" % (it["ref"], it["title"][:70], it["status"], stt, ctl))
    return "\n".join(out) + "\n"


def cmd_project(args, ws):
    pr = ws.project(args.project)
    print(render_project(ws, pr, args.framework))


# ------------------------------------------------------- product documents ----
def render_framework_doc(fw, mechanisms, titles):
    c = counts(fw)
    out = ["# %s: how AIGRCeler covers it\n" % fw["name"], DISCLAIMER + "\n",
           "%d items: %d covered, %d partly covered, %d not covered.\n" % (len(fw["items"]), c["covered"], c["partial"], c["gap"]),
           "Generated from `shared/catalog/regulatory-map.json`; do not edit by hand.\n",
           "| %s | Requirement | Status | Controls | How AIGRCeler works | Facts from Discover | Note |" % ("Ref"),
           "|---|---|---|---|---|---|---|"]
    for it in fw["items"]:
        ctl = "<br>".join("%s %s" % (x, titles.get(x, "")) for x in it["controls"]) or "-"
        mech = "<br>".join(mechanisms[k] for k in it["mechanisms"]) or "-"
        extra = ""
        if fw["id"] == "eu":
            extra = " Applies to: roles %s; classes %s." % (", ".join(it["roles"]), ", ".join(it["classes"]))
        out.append("| %s | %s | %s | %s | %s | %s | %s |" % (
            it["ref"], it["title"], it["status"], ctl, mech, ", ".join(it["profile"]) or "-", ((it["note"] or "") + extra).strip() or "-"))
    return "\n".join(out) + "\n"
