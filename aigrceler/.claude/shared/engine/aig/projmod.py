"""AI system (project) commands: create, set attributes, screening, lane, blocks."""
import re
from .core import clip
from .core import (
    AigError, Project, DOMAINS, STAGES, LANES, SOURCING_MODES, FLAGS, ESCALATOR_FLAGS,
    iso, slug, require, need_text, resolve_actor, split_list, write_text,
)
import copy

HARD_ESCALATORS = ["decisions_about_people", "eu_high_risk", "safety_impact", "sensitive_data",
                   "consequential_actions", "many_dependencies"]
SOFT_ESCALATORS = ["personal_data", "customer_facing_automated", "regulated_sector"]
LANE_RANK = {"light": 0, "standard": 1, "full": 2}

SCREEN_WORDS = {
    "users": {"few": 0, "many": 1, "very-many": 2},
    "autonomy": {"reviewed": 0, "sampled": 1, "automated": 2},
    "data": {"none": 0, "personal": 1, "sensitive": 2},
    "impact": {"minor": 0, "business": 1, "rights-or-safety": 2},
}


def escalators(info):
    out = [f for f in ESCALATOR_FLAGS if info["flags"].get(f)]
    if info.get("consequential_actions"):
        out.append("consequential_actions")
    if len(info.get("downstream_dependencies") or []) > 3:
        out.append("many_dependencies")
    return out


def tier_from_screen(sc):
    pts = sum(SCREEN_WORDS[k][sc[k]] for k in SCREEN_WORDS)
    return 1 if pts <= 1 else 2 if pts <= 3 else 3 if pts <= 5 else 4


def suggest_lane(info):
    if not info.get("tier"):
        return None
    esc = escalators(info)
    if any(e in HARD_ESCALATORS for e in esc) or info["tier"] >= 3:
        return "full"
    if esc or info["tier"] == 2:
        return "standard"
    return "light"


PLAIN = {
    "decisions_about_people": "it makes or shapes decisions about people",
    "eu_high_risk": "it may be an EU AI Act high-risk or prohibited use (the company's own view; a question for counsel)",
    "safety_impact": "it can affect safety",
    "sensitive_data": "it uses sensitive personal data",
    "consequential_actions": "it takes actions with real consequences",
    "many_dependencies": "more than three other systems depend on it",
    "personal_data": "it uses personal data",
    "customer_facing_automated": "its output goes to customers without review",
    "regulated_sector": "it is used in a regulated sector",
}

LANE_WORDS = {
    "light": ("Light", "one short sitting covering Discover, Assess and Govern together, with a small core set of controls (about 22) and one batch approval. For low-risk systems."),
    "standard": ("Standard", "all six stages with a reduced set of controls chosen for this system. For medium-risk systems."),
    "full": ("Full", "all six stages with every control that applies to this system. For systems that affect people's rights, use sensitive data or are regulated."),
}


def lane_options_text(info):
    """Plain-word description of the three lanes for this system, so the choice is never made blind."""
    esc = escalators(info)
    sug = info.get("lane_suggested") or suggest_lane(info)
    out = ["Lane options (AI Governance chooses one):"]
    for key in ("light", "standard", "full"):
        name, what = LANE_WORDS[key]
        note = ""
        if key == "light" and esc:
            note = " NOT AVAILABLE for this system because " + ", ".join(PLAIN.get(e, e) for e in esc) + "."
        elif key == "standard" and sug == "full":
            note = " Allowed only with a reason, because the suggestion is full."
        elif key == sug:
            note = " Suggested."
        if key == sug and "Suggested" not in note:
            note += " Suggested."
        out.append("  %s: %s%s" % (name, what, note))
    out.append("Choosing below the suggestion needs a reason in the person's own words.")
    return "\n".join(out)


def cmd_lane_options(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    if not (info.get("tier") or info.get("lane_suggested")):
        raise AigError("Run the screening first so there is a suggested lane.")
    print(lane_options_text(info))


def cmd_create(args, ws):
    if not args.name:
        raise AigError("Give the AI system a name (--name).")
    sl = slug(args.name)
    pr = Project(ws, sl)
    if pr.exists():
        raise AigError("An AI system called '%s' already exists." % sl)
    if args.sourcing_mode and args.sourcing_mode not in SOURCING_MODES:
        raise AigError("Sourcing mode must be one of: %s." % ", ".join(SOURCING_MODES))
    for d in ["00-status", "controls", "evidence", "incidents", "decisions/texts", "people", "working-papers", "logs", "data"]:
        pr.p(d).mkdir(parents=True, exist_ok=True)
    info = {
        "slug": sl, "name": args.name, "purpose": args.purpose or "", "users": args.users or "",
        "jurisdictions": split_list(args.jurisdictions), "sourcing_mode": args.sourcing_mode,
        "business_owner_role": args.business_owner_role or "operations",
        "data_sources": [], "techniques": [], "eval_metrics": [], "resources": "",
        "downstream_dependencies": [], "consequential_actions": False,
        "interaction_mode": "", "context_notes": "", "human_review": "", "model_version": args.model_version,
        "flags": {f: False for f in FLAGS}, "screening": None, "tier": None,
        "lane": None, "lane_decided": False, "current_stage": None,
        "stages": {s: {"status": "not_started"} for s in STAGES}, "cycle": 1,
        "blocks": [], "created": iso(),
    }
    pr.save_info(info)
    for n in ("risks", "requests", "evidence", "findings", "indicators", "incidents", "exceptions",
              "obligations", "containment", "reviews"):
        pr.save(n, [])
    pr.journal().append("project_created", ["project:" + sl], "tool:aigrceler",
                        "AI system registered: %s" % args.name, labels=["tool"])
    print("AI system '%s' registered. Next: describe it (project set), run the screening, then AI Governance confirms the lane." % sl)


def _parse_bool(v):
    return str(v).lower() in ("1", "true", "yes", "y", "on")


DRIVING = ("flags", "consequential_actions", "downstream_dependencies", "sourcing_mode", "model_version")


def _driving(info):
    return {k: copy.deepcopy(info.get(k)) for k in DRIVING}


def _lowered(before, after):
    out = []
    for f, v in (before.get("flags") or {}).items():
        if v and not (after.get("flags") or {}).get(f):
            out.append("'%s' switched off" % PLAIN.get(f, f))
    if before.get("consequential_actions") and not after.get("consequential_actions"):
        out.append("'it takes actions with real consequences' switched off")
    if len(after.get("downstream_dependencies") or []) < len(before.get("downstream_dependencies") or []):
        out.append("fewer systems depend on it")
    if before.get("sourcing_mode") and after.get("sourcing_mode") != before.get("sourcing_mode"):
        out.append("sourcing changed from %s to %s" % (before["sourcing_mode"], after.get("sourcing_mode")))
    return out


def cmd_set(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    before = _driving(info)
    changed = []
    for fld in ("purpose", "users", "interaction_mode", "context_notes", "resources", "human_review"):
        v = getattr(args, fld, None)
        if v is not None:
            info[fld] = v
            changed.append(fld)
    if args.jurisdictions is not None:
        info["jurisdictions"] = split_list(args.jurisdictions); changed.append("jurisdictions")
    if args.sourcing_mode:
        if args.sourcing_mode not in SOURCING_MODES:
            raise AigError("Sourcing mode must be one of: %s." % ", ".join(SOURCING_MODES))
        info["sourcing_mode"] = args.sourcing_mode; changed.append("sourcing_mode")
    for fld in ("data_sources", "techniques", "eval_metrics", "downstream_dependencies"):
        v = getattr(args, fld, None)
        if v is not None:
            info[fld] = split_list(v); changed.append(fld)
    if args.business_owner_role:
        info["business_owner_role"] = args.business_owner_role; changed.append("business_owner_role")
    if args.consequential_actions is not None:
        info["consequential_actions"] = _parse_bool(args.consequential_actions); changed.append("consequential_actions")
    for f in split_list(args.flags_on):
        if f not in FLAGS:
            raise AigError("Unknown flag '%s'. Known: %s." % (f, ", ".join(FLAGS)))
        info["flags"][f] = True; changed.append(f)
    for f in split_list(args.flags_off):
        if f not in FLAGS:
            raise AigError("Unknown flag '%s'." % f)
        info["flags"][f] = False; changed.append(f)
    model_changed = False
    if args.model_version and (len(args.model_version) > 60 or len(args.model_version.split()) > 4 or ":" in args.model_version):
        raise AigError("The model version must be the version name only, for example kestrel-rank-4.2, because test reports are matched against it word for word.")
    if args.model_version and args.model_version != info.get("model_version"):
        info["model_version"] = args.model_version; changed.append("model_version"); model_changed = True
    after = _driving(info)
    drove = after != before
    actor = resolve_actor(ws, args.by)
    low = _lowered(before, after)
    text = None
    if low:
        # lowering what the lane, the risk floors and the control choice depend on is a governance decision
        actor = require(ws, args.by, "decide_lane", "Lowering facts that drive the lane and the risk rating (%s)" % "; ".join(low))
        text = need_text(args, "statement", "Lowering facts that drive the lane and the risk rating")
    pr.save_info(info)
    if drove:
        pr.journal().append("project_facts_changed", ["project:" + pr.slug], actor.decided_by,
                            "Facts that drive the lane or risk changed: %s" % ", ".join(
                                [c for c in changed if c in set(DRIVING) | set(FLAGS)]),
                            authority_basis=actor.basis, labels=["tool"] if actor.is_tool else ["unsigned"],
                            text=("Lowered: %s\n\nDecision-maker's words:\n%s" % ("; ".join(low), text)) if low else None)
    if model_changed:
        from .evidmod import refresh
        n = refresh(ws, pr)
        if n:
            print("%d item(s) tied to the old model version have expired; new evidence is needed." % n)
    _auto_lane_up(ws, pr)
    if drove and pr.load("risks", []):
        from .riskmod import recompute
        recompute(ws, pr)
    print("Updated: %s." % (", ".join(changed) or "nothing"))


def _auto_lane_up(ws, pr):
    info = pr.info()
    sug = suggest_lane(info)
    if not sug or not info.get("lane"):
        return
    basis = info.get("lane_basis") or info.get("lane")
    if LANE_RANK[sug] > LANE_RANK[basis] and LANE_RANK[sug] > LANE_RANK[info["lane"]]:
        old = info["lane"]
        info["lane"] = sug
        info["lane_basis"] = sug
        pr.save_info(info)
        why = ", ".join(PLAIN.get(e, e) for e in escalators(info))
        pr.journal().append("lane_change", ["project:" + pr.slug], "tool:aigrceler",
                            "Lane raised automatically from %s to %s (%s)" % (old, sug, why or "tier"),
                            labels=["tool", "automatic"])
        print("The lane was raised from %s to %s because %s. More controls will be drafted." % (old, sug, why or "of its tier"))


def cmd_screen(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    sc = {}
    for k in SCREEN_WORDS:
        v = getattr(args, k)
        if v not in SCREEN_WORDS[k]:
            raise AigError("--%s must be one of: %s." % (k, ", ".join(SCREEN_WORDS[k])))
        sc[k] = v
    info["screening"] = sc
    info["tier"] = tier_from_screen(sc)
    for f in split_list(args.flags_on):
        if f not in FLAGS:
            raise AigError("Unknown flag '%s'." % f)
        info["flags"][f] = True
    if sc["data"] == "personal":
        info["flags"]["personal_data"] = True
    if sc["data"] == "sensitive":
        info["flags"]["personal_data"] = True
        info["flags"]["sensitive_data"] = True
    sug = suggest_lane(info)
    info["lane_suggested"] = sug
    pr.save_info(info)
    pr.journal().append("screening", ["project:" + pr.slug], "tool:aigrceler",
                        "Screening recorded: tier %d, suggested lane %s" % (info["tier"], sug),
                        labels=["tool"], extra={"answers": sc})
    _auto_lane_up(ws, pr)
    info = pr.info()
    why = ", ".join(PLAIN.get(e, e) for e in escalators(info))
    print("Tier %d of 4. Suggested lane: %s%s." % (info["tier"], sug, (" (because " + why + ")") if why else ""))
    print(lane_options_text(info))
    print("AI Governance confirms the lane with: lane set.")


def cmd_lane_set(args, ws):
    a = require(ws, args.by, "decide_lane", "Deciding the lane")
    text = need_text(args, "statement", "Deciding the lane")
    pr = ws.project(args.project)
    info = pr.info()
    if args.lane not in LANES:
        raise AigError("Lane must be light, standard or full.")
    sug = info.get("lane_suggested") or suggest_lane(info)
    if not sug:
        raise AigError("Run the screening first so there is a suggested lane.")
    cur = info.get("lane")
    labels = ["unsigned"]
    if LANE_RANK[args.lane] < LANE_RANK[sug]:
        labels.append("below-suggested")
    if cur and LANE_RANK[args.lane] < LANE_RANK[cur]:
        labels.append("moved-down")
    if args.lane == "light" and escalators(info):
        raise AigError("The light lane is not available: %s. The nearest lane that is allowed is %s." % (
            ", ".join(PLAIN.get(e, e) for e in escalators(info)), "full" if sug == "full" else "standard"))
    info["lane"] = args.lane
    info["lane_basis"] = sug
    info["lane_decided"] = True
    kind = "lane_assignment" if not cur else "lane_change"
    e = pr.journal().append(kind, ["project:" + pr.slug], a.decided_by,
                            "Lane %s: %s (suggested %s)" % ("set" if not cur else "changed", args.lane, sug),
                            authority_basis=a.basis, labels=labels, text=text)
    if args.lane == "light":
        from .stagemod import widen_light_pass
        if widen_light_pass(info, e["seq"]):
            print("DISCOVER had already started; in the light lane it now covers Assess and Govern as one pass.")
    pr.save_info(info)
    print("Lane set to %s." % args.lane)


def cmd_block_add(args, ws):
    pr = ws.project(args.project)
    a = resolve_actor(ws, args.by)
    info = pr.info()
    bid = pr.next_id("BLK", "BLK")
    info["blocks"].append({"id": bid, "reason": args.reason, "by": a.decided_by, "time": iso(), "lifted": None})
    pr.save_info(info)
    pr.journal().append("block_placed", ["project:" + pr.slug, bid], a.decided_by,
                        "Stage starts blocked: %s" % args.reason, authority_basis=a.basis, labels=["unsigned"] if not a.is_tool else ["tool"])
    print("Block %s placed. Discover and Assess can go on, but Assess cannot close and no stage after it can start until AI Governance lifts the block." % bid)


def cmd_block_review(args, ws):
    """Record that a possible legal hard stop was looked at and no block is placed, with the reason."""
    pr = ws.project(args.project)
    a = resolve_actor(ws, args.by)
    if not args.reason or len(str(args.reason).split()) < 10:
        raise AigError("Say in a sentence or two (at least ten words) why no block is needed: what is known, and who has been asked.")
    info = pr.info()
    info["block_review"] = {"reason": str(args.reason).strip(), "by": a.decided_by, "time": iso()}
    pr.save_info(info)
    pr.journal().append("block_review", ["project:" + pr.slug], a.decided_by,
                        "No stage block placed after looking at a possible legal hard stop: %s" % clip(args.reason, 220),
                        authority_basis=a.basis, labels=["unsigned"] if not a.is_tool else ["tool"])
    print("Recorded: no block, because: %s. It is shown on the waiting page. If counsel or new facts change this, place a block with 'stage block'." % str(args.reason).strip())


def cmd_lift_block(args, ws):
    a = require(ws, args.by, "lift_block", "Lifting a block")
    text = need_text(args, "statement", "Lifting a block")
    pr = ws.project(args.project)
    info = pr.info()
    b = next((x for x in info["blocks"] if x["id"] == args.id and not x["lifted"]), None)
    if not b:
        raise AigError("No open block %s." % args.id)
    # what is set aside is recorded at the moment of the lift, so it is not lost when the block leaves the page
    names = {p_["id"]: p_["name"] for p_ in ws.load("people", [])}
    open_reqs = ["%s to %s%s" % (r["id"], names.get(r["to"], r["to"]), (", due " + r["due"]) if r.get("due") else "")
                 for r in pr.load("requests", []) if r.get("status") == "open"]
    risks_ = pr.load("risks", [])
    n_hi = sum(1 for r in risks_ if r.get("inherent_set") and r.get("residual_level") in ("High", "Critical") and not r.get("acceptance"))
    b["lifted"] = {"by": a.person, "time": iso(), "open_requests": open_reqs, "unaccepted_high_risks": n_hi}
    pr.save_info(info)
    e = pr.journal().append("block_lifted", ["project:" + pr.slug, b["id"]], a.decided_by,
                            "Block lifted: %s" % b["reason"], authority_basis=a.basis, labels=["unsigned"], text=text,
                            extra={"set_aside": {"block_reason": b["reason"], "open_requests": open_reqs, "unaccepted_high_or_critical_risks": n_hi}})
    from . import concernmod
    items = pr.load("concerns", [])
    cid = pr.next_id("CON", "CON")
    items.append({"id": cid, "kind": "concern", "carry_to": "GOVERN", "status": "open", "resolved": None, "resolution": None,
                  "raised_by": "AIGRCeler (its own reading)", "asked_to_keep_by": None, "raised": iso(),
                  "text": ("Block %s was lifted by %s (their words are in journal line %d). What it rested on is still open: %s "
                           "Open owner requests at the time: %s. Unaccepted High or Critical risks: %d. "
                           "Govern should take these up when it chooses and approves controls." % (
                               b["id"], a.name, e["seq"], b["reason"], "; ".join(open_reqs) or "none", n_hi))})
    pr.save("concerns", items)
    print("Block lifted. What it was lifted over is recorded in the journal and carried to Govern as %s." % cid)


def cmd_show(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    print("%s | lane: %s | tier: %s | mode: %s | stage: %s" % (
        info["name"], info["lane"], info["tier"], info["sourcing_mode"], info["current_stage"]))
    print("Escalators: %s" % (", ".join(PLAIN.get(e, e) for e in escalators(info)) or "none"))
    for s in STAGES:
        print("  %-9s %s" % (s, info["stages"][s]["status"]))
    for l in (info.get("signoffs") or [])[-1:]:
        print("  Last go decision: %s by %s (journal line %d)" % (l["time"][:10], l["by_name"], l["seq"]))
