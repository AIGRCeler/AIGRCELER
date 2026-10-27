"""The assessments an AI system may need, and where each one stands.

Assess rates risks. It does not do the specialist assessments (fairness analysis, rights impact, data-protection impact,
documentation review, affected-people view); some of those are done in Govern and Assure as controls with evidence. This
list makes Assess say, for each one the system's facts point to, whether it is done, planned (and under which control) or
not needed, so that nothing is silently skipped. It does not say what the law requires (operating rule 14): the facts only
suggest which assessments fit, and counsel or AI Governance decide whether one is required.
"""
from .core import clip
from .core import AigError, iso, resolve_actor, need_text, split_list
from .ctrlmod import active_flags

STATUSES = ("done", "planned", "not-needed")

# key: (title, when it fits (any of these), the reason in plain words, controls that carry it later, who helps)
ITEMS = {
    "fairness": ("Fairness analysis across groups: does anyone get systematically worse results?",
                 ["decisions_about_people"], "it makes or shapes decisions about people", ["MD-04", "TP-05", "DO-02", "GO-17"], "Prism"),
    "rights": ("Impact on people's rights (a fundamental-rights impact assessment)",
               ["decisions_about_people", "eu_high_risk", "safety_impact"],
               "it affects people's rights or safety, or may be an EU high-risk use (a question for counsel)", ["GO-11", "GO-17"], "Auditor"),
    "dpia": ("Data-protection impact assessment: is one needed, and is it done?",
             ["personal_data", "sensitive_data"], "it uses personal data", ["DG-04"], "Auditor"),
    "docs": ("Review of the system's documents (model card, vendor terms, test reports)",
             None, "every system needs its documents read", ["MD-01", "TP-03", "TP-14"], "Verifier"),
    "affected": ("What the people affected would say (an affected-people view)",
                 ["decisions_about_people", "safety_impact", "customer_facing_automated"],
                 "people are affected by its output without choosing it", ["GO-15", "GO-17"], "Auditor"),
}
NEEDS_PERSON = ("rights", "dpia")   # "not needed" on these is a judgment for a person in AI Governance, in their own words


def carrying_controls(ws, info, key):
    """Controls that would carry this assessment for this system: the candidates that exist in the company's catalog and
    apply to the system's sourcing mode, lane and facts. For a purchased system that is not the same set as for one built in house."""
    from .ctrlmod import load_defs, applicable
    defs = load_defs(ws)
    return [c for c in ITEMS[key][3] if c in defs and info.get("lane") and applicable(defs[c], info)]


def govern_gate_items(ws, pr):
    """A planned assessment must have at least one control drafted to carry it."""
    info = pr.info()
    out = []
    for k, h in load(pr).items():
        if h.get("status") != "planned" or k not in ITEMS:
            continue
        if not any(pr.has_control(c) for c in (h.get("controls") or [])):
            options = carrying_controls(ws, info, k)
            out.append("The assessment '%s' is planned, but none of the controls named for it (%s) is on this system. %s" % (
                ITEMS[k][0].split(":")[0].split(" (")[0].lower(), ", ".join(h.get("controls") or []) or "none",
                ("Controls that would carry it here: %s. Record them with 'assess item'." % ", ".join(options)) if options
                else "No control in the catalog carries it for this system; say how it will be done ('assess item') or have one proposed."))
    return out


def required(info):
    """Items that fit this system. Light-lane systems get none: their one-pass covers it with the core controls."""
    if info.get("lane") == "light":
        return []
    fl = set(active_flags(info))
    out = []
    for k, (_t, flags, _why, _ctrls, _who) in ITEMS.items():
        if flags is None or any(f in fl for f in flags):
            out.append(k)
    return out


def load(pr):
    return pr.load("assessments", {})


def gate_items(ws, pr, info=None):
    info = info or pr.info()
    have = load(pr)
    open_ = [k for k in required(info) if k not in have]
    if not open_:
        return []
    names = "; ".join(ITEMS[k][0].split(":")[0].split(" (")[0].lower() for k in open_)
    return ["The assessments this system may need are not all answered yet (done, planned, or not needed with a reason): %s. "
            "'assess show' lists them." % names]


def cmd_item(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    key = (args.item or "").lower()
    if key not in ITEMS:
        raise AigError("Say which assessment (--item): %s." % ", ".join(ITEMS))
    status = (args.status or "").lower()
    if status not in STATUSES:
        raise AigError("Say where it stands (--status): %s." % ", ".join(STATUSES))
    note = (args.note or "").strip()
    if len(note.split()) < 5:
        raise AigError("Say in at least five words what the position is (--note): where the work is, which control will carry it, or why it is not needed.")
    a = resolve_actor(ws, args.by)
    text = None
    if status == "not-needed" and key in NEEDS_PERSON:
        if a.is_tool:
            raise AigError("Whether this assessment is not needed is a judgment for a named person in AI Governance, who may want counsel's view first. "
                           "Repeat with --by <their id> and --statement \"<their words>\".")
        text = need_text(args, "statement", "Saying an assessment is not needed")
    ctrls = split_list(args.control) if args.control else []
    if status == "planned" and not ctrls:
        ctrls = carrying_controls(ws, info, key)
    have = load(pr)
    prev = have.get(key)
    have[key] = {"status": status, "note": note, "controls": ctrls, "by": a.decided_by, "time": iso(),
                 "history": (prev.get("history", []) + [{k: prev[k] for k in ("status", "note", "by", "time")}]) if prev else []}
    pr.save("assessments", have)
    pr.journal().append("assessment_item", ["project:" + pr.slug, key], a.decided_by,
                        "Assessment '%s': %s. %s" % (key, status, clip(note, 200)),
                        authority_basis=a.basis if not a.is_tool else "", labels=["tool"] if a.is_tool else ["unsigned"], text=text)
    left = [k for k in required(info) if k not in have]
    print("Recorded: %s is %s." % (ITEMS[key][0].split(":")[0], status.replace("-", " ")))
    if status == "planned" and not ctrls:
        print("NOTE: no control in the catalog carries this assessment for this system. Say how it will be done in the note, or have a control proposed.")
    elif status == "planned":
        print("Carried by: %s." % ", ".join(ctrls))
    if left:
        print("Still to answer: %s." % ", ".join(left))


def cmd_show(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    have = load(pr)
    req = required(info)
    if info.get("lane") == "light":
        print("Light lane: the one combined pass covers these with its core controls. Nothing to answer here.")
        return
    print("Assessments that may fit this system (from its facts; whether one is required is for counsel and AI Governance):")
    for k in ITEMS:
        t, _f, why, ctrls, who = ITEMS[k]
        fits = k in req
        h = have.get(k)
        if h:
            st = "%s: %s" % (h["status"].replace("-", " "), h["note"])
        elif fits:
            st = "NOT ANSWERED"
        else:
            st = "does not fit this system's facts"
        print("- %s%s\n    %s" % (t, (" [%s helps]" % who) if fits and not h else "", st))
        if fits and not h:
            cc = carrying_controls(ws, info, k)
            print("    why it may fit: %s%s" % (why, ("; controls that would carry it for this system: %s" % ", ".join(cc)) if cc else "; no catalog control carries it for this system"))
    extra = [k for k in have if k not in req]
    if extra:
        print("Also recorded: %s." % ", ".join(extra))


def lines_for_view(pr, info):
    """Plain lines for the risk view: where each assessment stands."""
    if info.get("lane") == "light":
        return []
    have = load(pr)
    out = []
    for k in required(info):
        h = have.get(k)
        out.append((ITEMS[k][0], (h["status"].replace("-", " ") + ": " + h["note"]) if h else "not answered yet"))
    return out
