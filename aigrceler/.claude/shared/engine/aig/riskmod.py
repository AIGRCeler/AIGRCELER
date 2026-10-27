"""Risk: scenarios, inherent rating, credit from verified controls, roll-up.

Method (provisional, see claude/shared/methodology/RISK-METHOD.md):
- inherent likelihood and impact, 1 to 5 each, per scenario, before controls
- only verified or monitored controls with valid evidence earn credit
- strong evidence full, moderate half, weak none; expired evidence none
- whole steps; at most two steps in total per scenario; floors for some scenarios
- credit is suspended while the control's indicator is out of tolerance
- scenario scores roll up into six dimensions (20/20/15/15/15/15 = 100) and the existing bands
"""
import math

from .core import clip
from .core import (
    AigError, DIMENSIONS, CREDIT_STATES, iso, now, parse_dt, require, need_text, resolve_actor,
    split_list, read_json, write_json, write_text, evidence_usable, parse_date, today,
)
from .ctrlmod import active_flags
from . import profmod

STRENGTH_FACTOR = {"strong": 1.0, "moderate": 0.5, "weak": 0.0}
STRENGTH_RANK = {"weak": 0, "moderate": 1, "strong": 2}
FLOOR_SCORE = {"Medium": 5, "High": 10, "Critical": 17}
LEVEL_RANK = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}


def level_of(ws, score):
    for name, (lo, hi) in ws.settings()["scenario_bands"].items():
        if lo <= score <= hi:
            return name
    return "Critical"


def band_of(ws, total):
    for name, (lo, hi) in ws.settings()["bands"].items():
        if lo <= round(total) <= hi:
            return name
    return "Red"


def pseudo_flags(info):
    f = set(active_flags(info))
    if (info.get("screening") or {}).get("autonomy") == "automated":
        f.add("automated")
    if info.get("sourcing_mode"):
        f.add("mode:" + info["sourcing_mode"])
    return f


def scenario_applies(sc, info):
    ap = sc.get("applies") or {}
    modes = ap.get("modes")
    if modes and info["sourcing_mode"] not in modes:
        return False
    if ap.get("always"):
        return True
    fl = pseudo_flags(info)
    anyf = ap.get("flags_any") or []
    return any(f in fl for f in anyf)


def cmd_init(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    if not info.get("sourcing_mode"):
        raise AigError("Say how the AI system is sourced first.")
    risks = pr.load("risks", [])
    have = {r["scenario"] for r in risks}
    fl = pseudo_flags(info)
    n = 0
    raised = 0
    for sc in ws.load("scenarios", []):
        if sc["id"] in have or not scenario_applies(sc, info):
            continue
        l, i = sc.get("default_l", 3), sc.get("default_i", 3)
        for flag, b in (sc.get("bump") or {}).items():
            if flag in fl:
                l = min(5, l + b.get("l", 0)); i = min(5, i + b.get("i", 0))
        rid = pr.next_id("R", "R")
        reason = "starting point from the standard scenario; not yet rated by Meridian"
        unsure = profmod.uncertain_for(ws, pr, info, sc["id"])
        if unsure:
            l = min(5, l + 1)
            reason += ("; raised one step in likelihood because this is not known: %s. Confirm the facts and re-rate." % ", ".join(unsure))
            raised += 1
        risks.append({"id": rid, "scenario": sc["id"], "title": sc["title"], "dimension": sc["dimension"],
                      "domain": sc.get("domain"), "likelihood": l, "impact": i, "inherent_set": False,
                      "inherent_reason": reason,
                      "residual_l": l, "residual_i": i, "credits": [], "floor": None,
                      "floor_applied": False, "acceptance": None})
        n += 1
    pr.save("risks", risks)
    print("%d risk scenarios opened for rating. Meridian rates each one (risk set)." % n)
    if raised:
        print("%d of them start one step worse because facts from Discover are not known. Each says which; answering those questions is the way to bring them down." % raised)


def cmd_set(args, ws):
    pr = ws.project(args.project)
    risks = pr.load("risks", [])
    if args.all_defaults:
        if not args.reason:
            raise AigError("Accepting the starting ratings for all scenarios needs a reason (--reason).")
        for r in risks:
            if not r["inherent_set"]:
                r["inherent_set"] = True
                r["inherent_reason"] = "starting rating confirmed: " + args.reason
        pr.save("risks", risks)
        recompute(ws, pr)
        print("All starting ratings confirmed.")
        return
    r = next((x for x in risks if x["id"] == args.id), None)
    if not r:
        raise AigError("No risk %s." % args.id)
    if not args.reason:
        raise AigError("Say why (--reason): the rating must be explainable to a regulator.")
    for fld, v in (("likelihood", args.likelihood), ("impact", args.impact)):
        if v is not None:
            if not 1 <= v <= 5:
                raise AigError("%s must be 1 to 5." % fld)
            r[fld] = v
    if args.like:
        like = [x.strip() for x in args.like.split(",") if x.strip()]
        known = {s_["id"] for s_ in ws.load("scenarios", [])}
        bad = [x for x in like if x not in known]
        if bad:
            raise AigError("Unknown standard scenario(s) in --like: %s." % ", ".join(bad))
        if not r.get("custom"):
            raise AigError("--like links standard controls to a risk added for this system. %s is a standard scenario and already has its own." % r["id"])
        r["credit_from"] = like
    r["inherent_set"] = True
    r["inherent_reason"] = args.reason
    pr.save("risks", risks)
    recompute(ws, pr)
    print("%s rated: likelihood %d, impact %d." % (r["id"], r["likelihood"], r["impact"]))


def cmd_add(args, ws):
    """A risk specific to this system that the standard scenarios miss. It is rated on the spot and counts like the others."""
    pr = ws.project(args.project)
    info = pr.info()
    if not args.title or not args.title.strip():
        raise AigError("Say what could go wrong (--title), in plain words.")
    dim = (args.dimension or "").lower()
    if dim not in DIMENSIONS:
        raise AigError("Say which dimension it belongs to (--dimension): %s." % ", ".join(DIMENSIONS))
    for fld, v in (("likelihood", args.likelihood), ("impact", args.impact)):
        if v is None or not 1 <= v <= 5:
            raise AigError("Give %s as 1 to 5 (--%s)." % (fld, fld))
    if not args.reason or len(args.reason.split()) < 5:
        raise AigError("Say why in at least five words (--reason): which facts it rests on.")
    like = [x.strip() for x in (args.like or "").split(",") if x.strip()]
    known = {s_["id"] for s_ in ws.load("scenarios", [])}
    bad = [x for x in like if x not in known]
    if bad:
        raise AigError("Unknown standard scenario(s) in --like: %s. They are listed by 'catalog coverage'." % ", ".join(bad))
    risks = pr.load("risks", [])
    if any(r["title"].strip().lower() == args.title.strip().lower() for r in risks):
        raise AigError("A risk with that title is already on the list.")
    rid = pr.next_id("R", "R")
    risks.append({"id": rid, "scenario": "X-" + rid, "title": args.title.strip(), "dimension": dim, "domain": None,
                  "likelihood": args.likelihood, "impact": args.impact, "inherent_set": True,
                  "inherent_reason": args.reason.strip(), "custom": True, "credit_from": like,
                  "residual_l": args.likelihood, "residual_i": args.impact, "credits": [], "floor": None,
                  "floor_applied": False, "acceptance": None})
    pr.save("risks", risks)
    pr.journal().append("risk_added", ["project:" + pr.slug, rid], "tool:aigrceler",
                        "Added a risk specific to %s: %s (%dx%d)" % (info["name"], clip(args.title, 140), args.likelihood, args.impact),
                        labels=["tool"])
    recompute(ws, pr)
    print("%s added and rated: likelihood %d, impact %d. %s" % (
        rid, args.likelihood, args.impact,
        ("Controls for %s also count against it." % ", ".join(like)) if like else
        "No standard control is linked to it; use --like <scenario ids> to link one, or propose a control to Curator."))


def gap_rows(ws, pr, levels=("High", "Critical")):
    """For each High or Critical risk: which controls would address it, and whether any exists yet."""
    from .ctrlmod import load_defs, applicable
    info = pr.info()
    out = []
    if not info.get("lane"):
        return out
    defs = load_defs(ws)
    for r in pr.load("risks", []):
        if not r.get("inherent_set") or r.get("inherent_level") not in levels:
            continue
        links = [r["scenario"]] + list(r.get("credit_from") or [])
        cs = [d for d in defs.values() if any(x in d.get("scenarios", []) for x in links) and applicable(d, info)]
        have = {c["id"]: c for c in pr.all_controls()}
        rows = []
        for d in sorted(cs, key=lambda d: d["id"]):
            c = have.get(d["id"])
            rows.append((d["id"], d["title"], c["state"] if c else "to be drafted in Govern"))
        out.append({"risk": r, "controls": rows})
    return out


def cmd_gaps(args, ws):
    pr = ws.project(args.project)
    rows = gap_rows(ws, pr)
    if not rows:
        print("No High or Critical risks are rated yet.")
        return
    for g in rows:
        r = g["risk"]
        print("%s %s (%dx%d=%d): %s" % (r["id"], r["inherent_level"], r["likelihood"], r["impact"], r["inherent_score"], r["title"]))
        if not g["controls"]:
            print("    NO catalog control addresses this. Govern needs a system-specific control, or someone must accept the risk. "
                  "Propose a control to Curator ('catalog propose').")
        for cid, title, st in g["controls"]:
            print("    - %s %s [%s]" % (cid, title, st))


def _floor_for(sc, info):
    fl = sc.get("floor")
    if not fl:
        return None
    pf = pseudo_flags(info)
    if all(f in pf for f in fl.get("when_all", [])):
        return fl["level"]
    return None


def recompute(ws, pr, quiet=True, refresh_first=False):
    if refresh_first:
        from .evidmod import refresh
        refresh(ws, pr)
    info = pr.info()
    risks = pr.load("risks", [])
    scs = {s["id"]: s for s in ws.load("scenarios", [])}
    controls = pr.all_controls()
    evs = {e["id"]: e for e in pr.load("evidence", [])}
    inds = pr.load("indicators", [])
    out_of_tol = {i["control"] for i in inds if i.get("status") == "out_of_tolerance"}
    lapsed = []
    for r in risks:
        sc = scs.get(r["scenario"], {})
        r["floor"] = _floor_for(sc, info)
        credL = credI = 0.0
        credits = []
        for c in controls:
            d = c["definition"]
            if not any(x in d.get("scenarios", []) for x in [r["scenario"]] + list(r.get("credit_from") or [])):
                continue
            entry = {"control": c["id"], "state": c["state"], "type": d["type"], "max_steps": d["max_steps"]}
            ev = evs.get(c.get("current_evidence"))
            if c["state"] not in CREDIT_STATES:
                entry.update(strength=None, steps=0.0, why="not verified yet (%s)" % c["state"])
            elif not ev or ev.get("control") != c["id"] or not evidence_usable(ev, info):
                entry.update(strength=None, steps=0.0,
                             why="no valid evidence today (missing, past its date, or tied to an older model version)")
            elif c["id"] in out_of_tol:
                entry.update(strength=c.get("strength"), steps=0.0, why="credit suspended: indicator is out of tolerance")
            else:
                st = ev["strength"]
                if st not in STRENGTH_FACTOR:
                    st = "weak"
                steps = max(0.0, min(float(d["max_steps"]), 2.0)) * STRENGTH_FACTOR[st]
                entry.update(strength=st, steps=steps,
                             why="verified with %s evidence" % st)
                if d["type"] == "preventive":
                    credL += steps
                else:
                    credI += steps
            credits.append(entry)
        sl = min(int(math.floor(credL + 1e-9)), 2)
        si = min(int(math.floor(credI + 1e-9)), 2 - sl)
        rl = max(1, r["likelihood"] - sl)
        ri = max(1, r["impact"] - si)
        r["floor_applied"] = False
        if r["floor"]:
            fs = FLOOR_SCORE[r["floor"]]
            while rl * ri < fs and (rl < r["likelihood"] or ri < r["impact"]):
                if (r["likelihood"] - rl) >= (r["impact"] - ri) and rl < r["likelihood"]:
                    rl += 1
                else:
                    ri += 1
                r["floor_applied"] = True
        r["residual_l"], r["residual_i"] = rl, ri
        r["steps_l"], r["steps_i"] = r["likelihood"] - rl, r["impact"] - ri
        r["credits"] = credits
        r["inherent_score"] = r["likelihood"] * r["impact"]
        r["residual_score"] = rl * ri
        r["inherent_level"] = level_of(ws, r["inherent_score"])
        r["residual_level"] = level_of(ws, r["residual_score"])
        acc = r.get("acceptance")
        if acc and LEVEL_RANK[r["residual_level"]] > LEVEL_RANK[acc["level"]]:
            lapsed.append((r, acc, "the residual level rose from %s to %s" % (acc["level"], r["residual_level"])))
            r["acceptance"] = None
            r.setdefault("lapsed_acceptances", []).append(dict(acc, lapsed=iso()))
        elif acc and acc.get("until") and acc["until"] < today():
            lapsed.append((r, acc, "its end date %s has passed" % acc["until"]))
            r["acceptance"] = None
            r.setdefault("lapsed_acceptances", []).append(dict(acc, lapsed=iso()))
    pr.save("risks", risks)
    summary = rollup(ws, pr, risks)
    pr.save("risk_summary", summary)
    for r, acc, why in lapsed:
        pr.journal().append("risk_acceptance_lapsed", [r["id"]], "tool:aigrceler",
                            "Acceptance of %s lapsed: %s" % (r["id"], why),
                            labels=["tool", "automatic"])
        print("NOTE: the acceptance of risk %s lapsed because %s." % (r["id"], why))
    return summary


def rollup(ws, pr, risks):
    dims = {}
    for key, (title, pts) in DIMENSIONS.items():
        rs = [r for r in risks if r["dimension"] == key and r.get("inherent_set")]
        row = {"title": title, "max_points": pts, "scenarios": len(rs)}
        for kind in ("inherent", "residual"):
            scores = [r["%s_score" % kind] for r in rs]
            if scores:
                ratio = (0.7 * max(scores) + 0.3 * (sum(scores) / len(scores))) / 25.0
                row[kind + "_points"] = round(pts * ratio, 1)
            else:
                row[kind + "_points"] = 0.0
        dims[key] = row
    ti = round(sum(d["inherent_points"] for d in dims.values()), 1)
    tr = round(sum(d["residual_points"] for d in dims.values()), 1)
    unrated = sum(1 for r in risks if not r.get("inherent_set"))
    return {"as_of": iso(), "dimensions": dims, "inherent_total": ti, "residual_total": tr,
            "inherent_band": band_of(ws, ti), "residual_band": band_of(ws, tr), "unrated_scenarios": unrated}


def cmd_recompute(args, ws):
    pr = ws.project(args.project)
    s = recompute(ws, pr, refresh_first=True)
    print("Inherent %.1f (%s) -> residual %.1f (%s). %d scenario(s) not yet rated." % (
        s["inherent_total"], s["inherent_band"], s["residual_total"], s["residual_band"], s["unrated_scenarios"]))


def cmd_show(args, ws):
    pr = ws.project(args.project)
    s = pr.load("risk_summary")
    for r in pr.load("risks", []):
        flag = "" if r.get("inherent_set") else " [unrated]"
        print("%-6s %-9s %dx%d=%-2d -> %dx%d=%-2d %-9s %s%s" % (
            r["id"], r["dimension"], r["likelihood"], r["impact"], r.get("inherent_score", 0),
            r["residual_l"], r["residual_i"], r.get("residual_score", 0), r.get("residual_level", ""),
            r["title"][:50], flag))
    if s:
        print("Inherent %.1f (%s); residual %.1f (%s)." % (s["inherent_total"], s["inherent_band"], s["residual_total"], s["residual_band"]))


def cmd_accept(args, ws):
    if args.with_person:
        raise AigError("Each person records their own acceptance. Ask %s to run this command themselves, in their own words." % args.with_person)
    a = require(ws, args.by, "accept_risk", "Accepting residual risk")
    text = need_text(args, "statement", "Accepting residual risk")
    until = parse_date(args.until, "end date for the acceptance")
    if until and until < today():
        raise AigError("The end date %s has already passed." % until)
    pr = ws.project(args.project)
    risks = pr.load("risks", [])
    r = next((x for x in risks if x["id"] == args.id), None)
    if not r:
        raise AigError("No risk %s." % args.id)
    if not r.get("inherent_set"):
        raise AigError("This scenario has not been rated yet.")
    lvl = r["residual_level"]
    if r.get("acceptance") and r["acceptance"]["level"] == lvl:
        raise AigError("This risk is already accepted at level %s (by %s)." % (lvl, ", ".join(r["acceptance"]["by"])))
    th = ws.load("thresholds")
    allowed = th["accept_by"].get(lvl, [])
    if not any(a.has_role(x) for x in allowed):
        raise AigError("A residual risk at level %s must be accepted by: %s. %s is not in that role." % (lvl, ", ".join(allowed), a.name))
    if not args.basis and not a.basis:
        raise AigError("Record the authority basis (--basis), for example the charter or board resolution.")
    r["acceptance"] = {"by": [a.person], "level": lvl, "time": iso(),
                       "basis": args.basis or a.basis, "until": until}
    pr.save("risks", risks)
    pr.journal().append("risk_acceptance", [r["id"]], a.decided_by,
                        "Accepted residual risk %s at level %s: %s" % (r["id"], lvl, r["title"]),
                        authority_basis=args.basis or a.basis, labels=["unsigned"], text=text)
    print("Accepted at level %s%s." % (lvl, " until %s" % until if until else ""))
