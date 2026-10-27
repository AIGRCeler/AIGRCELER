"""Generated views. Nothing here is a source of truth; delete them and they are rebuilt."""
from collections import Counter, defaultdict
from pathlib import Path

from .core import (
    DOMAINS, DOMAIN_TITLES, TRUST_PROPERTIES, STAGES, DIMENSIONS, CONTROL_STATES, iso, now, today,
    write_text, write_json, read_json, parse_dt, AigError, active_assignments, norm_stage,
)
from . import ctrlmod, projmod

PROP_TITLE = {
    "validity-and-reliability": "Validity and reliability",
    "safety": "Safety",
    "security-and-resiliency": "Security and resiliency",
    "accountability-and-transparency": "Accountability and transparency",
    "explainability-and-interpretability": "Explainability and interpretability",
    "privacy": "Privacy",
    "fairness": "Fairness",
}
STATE_COLS = ["drafted", "approved", "assigned", "implementing", "evidenced", "verified", "monitored", "expired", "rejected", "waived"]


def table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for r in rows:
        out.append("| " + " | ".join(str(x) for x in r) + " |")
    return "\n".join(out) + "\n"


def active(cs):
    return [c for c in cs if c["state"] != "retired"]


def strength_note(cs):
    cnt = Counter(c.get("strength") for c in cs if c["state"] in ("verified", "monitored"))
    parts = [("%d %s" % (cnt[k], k)) for k in ("strong", "moderate", "weak") if cnt.get(k)]
    return " (%s)" % ", ".join(parts) if parts else ""


def view_by_domain(ws, pr, cs):
    rows = []
    for code, dom in DOMAINS.items():
        sub = [c for c in active(cs) if c["domain"] == code]
        if not sub:
            continue
        cnt = Counter(c["state"] for c in sub)
        row = [DOMAIN_TITLES[code], len(sub)]
        for s in STATE_COLS:
            v = cnt.get(s, 0)
            cell = str(v) if v else ""
            if s in ("verified", "monitored") and v:
                cell += strength_note([c for c in sub if c["state"] == s])
            row.append(cell)
        rows.append(row)
    tot = Counter(c["state"] for c in active(cs))
    rows.append(["**All**", len(active(cs))] + [("**%d**" % tot[s]) if tot.get(s) else "" for s in STATE_COLS])
    return ("# Where the controls stand, by area\n\nGenerated %s. Each row is an area of the program; each column is where a control is in its life. "
            "For verified controls the strength of the proof is shown in brackets.\n\n" % iso()[:16].replace("T", " ")
            + table(["Area", "Controls"] + STATE_COLS, rows))


def view_by_role(ws, pr, cs):
    roles = ws.load("roles", [])
    rows = []
    for code in DOMAINS:
        sub = [c for c in active(cs) if c["domain"] == code]
        if not sub:
            continue
        row = [DOMAIN_TITLES[code]]
        for r in roles:
            if r.get("governance"):
                row.append("approves all")
                continue
            owned = [c for c in sub if c["owner_role"] == r["id"]]
            mark = " **(accountable)**" if code in r.get("default_domains", []) else ""
            done = len([c for c in owned if c["state"] in ("verified", "monitored")])
            row.append(("%d of %d verified" % (done, len(owned)) if owned else "") + mark)
        rows.append(row)
    return ("# Who owns what, by area and by role\n\nGenerated %s. 'Accountable' marks the role that answers for an area by default. "
            "AI Governance approves everything and implements nothing.\n\n" % iso()[:16].replace("T", " ")
            + table(["Area"] + [r["name"] for r in roles], rows))


def view_by_phase(ws, pr, cs):
    risks = pr.load("risks", [])
    inds = pr.load("indicators", [])
    revs = pr.load("reviews", [])
    rows = []
    for code in DOMAINS:
        sub = [c for c in active(cs) if c["domain"] == code]
        if not sub:
            continue
        rk = len([r for r in risks if r.get("domain") == code])
        gov = len([c for c in sub if c["state"] not in ("drafted",)])
        assu = len([c for c in sub if c["state"] in ("verified", "monitored")])
        mon = len([i for i in inds if i["control"].startswith(code + "-")])
        rows.append([DOMAIN_TITLES[code], rk, "%d of %d" % (gov, len(sub)), "%d of %d" % (assu, len(sub)), mon])
    return ("# Coverage by area\n\nUse this to check that every area has been through risk rating, control decisions, proof and watching. It is not the day-to-day view.\n\n"
            + table(["Area", "Risk scenarios (Assess)", "Controls decided (Govern)", "Controls proven (Operate)", "Indicators (Operate: watching)"], rows)
            + "\nReviews recorded: %d.\n" % len(revs))


def view_by_property(ws, pr, cs):
    rows = []
    for p in TRUST_PROPERTIES:
        sub = [c for c in active(cs) if p in c["definition"].get("trust_properties", [])]
        if not sub:
            continue
        cnt = Counter(c["state"] for c in sub)
        waiting = cnt["drafted"] + cnt["approved"] + cnt["assigned"]
        prog = cnt["implementing"] + cnt["evidenced"]
        done = cnt["verified"] + cnt["monitored"]
        prob = cnt["expired"] + cnt["rejected"] + cnt["waived"]
        rows.append([PROP_TITLE[p], len(sub), waiting, prog, str(done) + strength_note([c for c in sub if c["state"] in ("verified", "monitored")]), prob])
    return ("# Where the controls stand, by trustworthiness property\n\nA control can serve more than one property, so rows overlap.\n\n"
            + table(["Property", "Controls", "Waiting to start", "In progress", "Verified", "Expired, rejected or waived"], rows))


def view_risk(ws, pr):
    risks = pr.load("risks", [])
    s = pr.load("risk_summary")
    out = ["# Risk: before and after controls\n"]
    if s:
        out.append("Generated %s. Score out of 100: inherent **%.1f (%s)**, residual **%.1f (%s)**. Scenarios not yet rated: %d.\n" % (
            s["as_of"][:16].replace("T", " "), s["inherent_total"], s["inherent_band"], s["residual_total"], s["residual_band"], s["unrated_scenarios"]))
        rows = [[d["title"], d["max_points"], d["scenarios"], d["inherent_points"], d["residual_points"]] for d in s["dimensions"].values()]
        out.append(table(["Dimension", "Max points", "Scenarios", "Inherent", "Residual"], rows))
    rows = []
    for r in risks:
        credits = "; ".join("%s: %s" % (c["control"], c["why"]) for c in r.get("credits", []) if c.get("steps") or c["state"] in ("verified", "monitored"))
        rows.append([r["id"], r["title"][:70], "%dx%d=%d" % (r["likelihood"], r["impact"], r.get("inherent_score", 0)),
                     "%dx%d=%d (%s)" % (r["residual_l"], r["residual_i"], r.get("residual_score", 0), r.get("residual_level", "")),
                     ("floor %s applied" % r["floor"]) if r.get("floor_applied") else "",
                     "accepted" if r.get("acceptance") else "", credits[:120]])
    out.append("\n## Scenarios\n\n" + table(["Ref", "Scenario", "Before", "After", "Floor", "Accepted?", "What earned credit"], rows))
    from . import assessmod, riskmod
    al = assessmod.lines_for_view(pr, pr.info())
    if al:
        out.append("\n## Assessments this system may need (from its facts; whether one is required is for counsel and AI Governance)\n\n" + table(
            ["Assessment", "Where it stands"], [[a, b] for a, b in al]))
    gaps = riskmod.gap_rows(ws, pr)
    if gaps:
        grows = []
        for g in gaps:
            r = g["risk"]
            ctl = "; ".join("%s (%s)" % (cid, st) for cid, _t, st in g["controls"]) or "**no catalog control addresses it**"
            grows.append([r["id"], r["inherent_level"], r["title"][:60], ctl[:140]])
        out.append("\n## High and Critical risks, and the controls that address them\n\n" + table(
            ["Ref", "Level", "Risk", "Controls (state)"], grows))
    ws_org = ws.load("organizational_risks", [])
    if ws_org:
        out.append("\n## Company-level risks (not added into the score above)\n\n" + table(
            ["Ref", "Risk", "Level", "Status"], [[o["id"], o["title"], o["residual"], "accepted" if o["acceptance"] else "open"] for o in ws_org]))
    return "\n".join(out)


def view_open(ws, pr, cs):
    people = {p["id"]: p["name"] for p in ws.load("people", [])}
    out = ["# What is waiting, and on whom\n", "Generated %s.\n" % iso()[:16].replace("T", " ")]
    gov_wait = [c for c in cs if c["state"] == "drafted"]
    info = pr.info()
    # What is already decided or in force. Report this as settled; never ask for any of it again.
    out.append("## Where it stands (already decided or in force: do not ask again)\n")
    stages = info.get("stages") or {}
    if info.get("lane_decided") and info.get("lane"):
        out.append("- Lane: **%s**, decided by AI Governance." % info["lane"])
    elif info.get("lane_suggested"):
        out.append("- Lane: not decided yet (suggested: %s)." % info["lane_suggested"])
    else:
        out.append("- Lane: not suggested yet (the screening has not been done).")
    states = ["%s %s" % (k.capitalize(), (v.get("status") or "not_started").replace("_", " ")) for k, v in stages.items()
              if (v.get("status") or "not_started") != "not_started"]
    out.append("- Stages: %s." % (", ".join(states) if states else "none started"))
    for b in info.get("blocks") or []:
        if not b.get("lifted"):
            out.append("- Stage block in force (Assess can run but cannot close, and later stages cannot start): %s" % b["reason"])
    for b in info.get("blocks") or []:
        if b.get("lifted"):
            who = {p_["id"]: p_["name"] for p_ in ws.load("people", [])}.get(b["lifted"]["by"], b["lifted"]["by"])
            out.append("- A stage block was lifted by %s on %s, over open items (their words are in the journal; the items are carried forward as a concern, which stays open until it is dealt with)." % (
                who, b["lifted"]["time"][:10]))
    if (info.get("block_review") or {}).get("reason") and not info.get("blocks"):
        out.append("- No stage block: a possible legal hard stop was looked at and none was placed. Reason recorded: %s" % info["block_review"]["reason"])
    for ct in pr.load("containment", []):
        if ct.get("status") == "active":
            if ct.get("confirmed"):
                out.append("- Temporary measure in force until %s (reported in place by %s; not checked): %s" % (ct["ends"], ct["confirmed"]["source"], ct["title"]))
            else:
                out.append("- Temporary measure decided, until %s, **not yet confirmed in place**%s: %s" % (
                    ct["ends"], (" (asked in %s)" % ct["request"]) if ct.get("request") else "", ct["title"]))
    a_status = (info.get("stages") or {}).get("ASSESS", {}).get("status", "not_started")
    if a_status == "started":
        from .stagemod import gate as _agate
        try:
            a_items = [x for x in _agate(ws, pr, "ASSESS") if not x.startswith("A stage block")]
        except Exception:
            a_items = []
        if a_items:
            out.append("")
            out.append("## AIGRCeler to do before Assess can close (its own work: do it, then tell AI Governance; do not hand it back as a decision)\n")
            for x in a_items:
                out.append("- %s" % x)
            out.append("- Only these are for a named person: saying a rights or data-protection assessment is not needed, closing Assess, and lifting a block.")
    out.append("")
    out.append("## Waiting on AI Governance\n")
    d_status = (info.get("stages") or {}).get("DISCOVER", {}).get("status", "not_started")
    if d_status not in ("closed", "closed_without_start"):
        from . import profmod
        gaps = profmod.gate_items(ws, pr, info)
        if not info.get("tier"):
            out.append("- **Discovery has not been done.** The system is registered but not yet described or screened. "
                       "Atlas asks the open questions now, without waiting to be told.")
        elif gaps:
            asked = sorted({people.get(r["to"], r["to"]) for r in pr.load("requests", [])
                            if r.get("type") == "discovery_question" and r["status"] == "open"})
            out.append("- **Discovery is open.** %s%s" % (" ".join(gaps),
                       (" Open questions are with %s (see below); read what each was asked (request list) before asking AI Governance for any of it." % ", ".join(asked)) if asked else ""))
    from . import concernmod
    from .catalogmod import behind_starter
    _bs = behind_starter(ws)
    if _bs:
        out.append("- **The company's control catalog (version %s) is missing %d control(s) this product now ships with:** %s. "
                   "Adding them is AI Governance's decision (the engine can do it on their word); controls for systems not yet past Govern would then include them." % (
                       ws.settings().get("catalog_version"), len(_bs), ", ".join(_bs)))
    for c_ in concernmod.open_items(pr, "proposal"):
        out.append("- **Proposed by AIGRCeler, waiting for your decision:** %s" % c_["text"])
    if info.get("lane_suggested") and not info.get("lane"):
        out.append("- **Choose the lane for this system.** Suggested: %s." % info["lane_suggested"])
        for ln in projmod.lane_options_text(info).splitlines()[1:-1]:
            out.append("  " + ln.strip())
    elif info.get("lane"):
        from .stagemod import STAGES
        nxt = None
        for st_name in STAGES:
            stt = (info.get("stages") or {}).get(st_name, {}).get("status", "not_started")
            if stt == "not_started":
                nxt = st_name
                break
            if stt not in ("closed", "closed_without_start"):
                break
        if nxt and (info["lane"] != "light" or nxt == "DISCOVER"):
            out.append("- Start the %s stage (only AI Governance can start a stage)." % nxt.capitalize())
    out.append("- %d drafted control(s) to approve or decline." % len(gov_wait) if gov_wait else "- No controls waiting for approval.")
    unrated = [r for r in pr.load("risks", []) if not r.get("inherent_set")]
    if unrated:
        out.append("- %d risk scenario(s) not rated yet (Meridian)." % len(unrated))
    props = [f for f in (ws.p("catalog", "proposals").glob("P-*.json") if ws.p("catalog", "proposals").exists() else []) if read_json(f)["status"] == "open"]
    if props:
        out.append("- %d catalog proposal(s) open (company-wide)." % len(props))
    noown = [c for c in cs if c["state"] == "approved"]
    if noown:
        out.append("- %d approved control(s) have no owner yet." % len(noown))
    evs = [e for e in pr.load("evidence", []) if e["status"] == "received"]
    if evs:
        out.append("- %d piece(s) of evidence received but not yet analyzed (Verifier)." % len(evs))
    if (info.get("stages") or {}).get("OPERATE", {}).get("status") == "started":
        from . import chasemod
        rows_ = chasemod.build(ws, pr)
        late_ = [r for r in rows_ if r["late"]]
        us_ = [r for r in rows_ if r["side"] == "us"]
        if late_ or us_:
            out.append("- %d item(s) are late and %d are waiting on us (messages to send or write). See the chase list ('operate chase' or 00-status/7-chase-list.md)." % (len(late_), len(us_)))
        rs_ = chasemod.review_status(ws, pr)
        if rs_ and (rs_["left"] <= 14 or rs_["reasons"]):
            out.append("- " + chasemod.review_line(rs_))
    cons = concernmod.open_items(pr, "concern")
    if cons:
        out.append("\n## Concerns AIGRCeler has raised (its own reading, carried to the stage named; not yet dealt with)\n")
        for c_ in cons:
            out.append("- For %s: %s" % ((norm_stage(c_.get("carry_to")) or "a later stage").capitalize(), c_["text"]))
    out.append("\n## Waiting on owners\n")
    qcount = defaultdict(int)
    try:
        from . import profmod
        for _f, _asks in (profmod.load(pr).get("asked") or {}).items():
            for _a in _asks:
                qcount[_a["request"]] += 1
    except Exception:
        pass
    from .ctrlmod import request_subject as _rs
    by = defaultdict(list)
    for r in pr.load("requests", []):
        if r["status"] == "open":
            by[r["to"]].append(r)
    if not by:
        out.append("- Nothing outstanding.")
    for p, rs in by.items():
        for r in rs:
            late = r["due"] and r["due"] < today()
            nq = qcount.get(r["id"], 0)
            what = (("%d discovery question%s in one message" % (nq, "" if nq == 1 else "s")) if r.get("type") == "discovery_question" and nq > 1 else
                    "a discovery question" if r.get("type") == "discovery_question" else
                    "a request to act (temporary measure)" if r.get("type") == "containment" else
                    "a notice to confirm" if r.get("type") == "notice" else
                    "%d item(s)" % len(r["controls"]) if r["controls"] else "%s (%s)" % (
                        "an evidence request" if r.get("type") == "evidence_request" else "a request", _rs(pr, r)))
            dl = r.get("delivered")
            sent = ("; marked as sent %s%s" % (str(dl.get("time", ""))[:10], (" (said by %s)" % people.get(dl["by"], dl["by"])) if dl.get("by") else "")) if isinstance(dl, dict) and dl else "; not marked as sent yet"
            out.append("- %s: %s, %s%s%s" % (people.get(p, p), what, ("due " + r["due"]) if r["due"] else "no due date set", sent, "  **late**" if late else ""))
    out.append("\n## Needs attention\n")
    flagged = False
    # stages that AI Governance closed over open items: keep saying so until the items are dealt with
    from .stagemod import gate as _gate
    for e in pr.journal().lines():
        if e.get("type") in ("stage_close", "stage_close_without_start", "signoff") and (e.get("extra") or {}).get("open_items"):
            first = norm_stage(((e.get("extra") or {}).get("covers") or ["OPERATE"])[0])
            try:
                still = _gate(ws, pr, first) if first else []
            except Exception:
                still = []
            if still:
                out.append("- %s by AI Governance with items still open: %s" % (
                    "The go decision was recorded" if e.get("type") == "signoff" else "%s was closed" % first.capitalize(), "; ".join(still)))
                flagged = True
    for c in cs:
        if c["state"] in ("expired", "rejected"):
            out.append("- %s is %s: %s" % (c["title"], c["state"], c["history"][-1].get("why", "")))
            flagged = True
    for i in pr.load("indicators", []):
        if i["status"] == "out_of_tolerance":
            out.append("- Indicator out of tolerance: %s (%s)" % (i["metric"], i["control"])); flagged = True
    for i in pr.load("incidents", []):
        if i["status"] == "open":
            late = now() > parse_dt(i["escalate_due"]) and not i.get("acknowledged")
            out.append("- Open incident (%s): %s%s" % (i["severity"], i["title"], "  **response clock passed**" if late else "")); flagged = True
    for r in pr.load("risks", []):
        if r.get("residual_level") in ("High", "Critical") and not r.get("acceptance") and r.get("inherent_set"):
            out.append("- %s residual risk not accepted: %s" % (r["residual_level"], r["title"])); flagged = True
    if not flagged:
        out.append("- Nothing.")
    return "\n".join(out) + "\n"


def view_discovery(ws, pr):
    info = pr.info()
    names = {p["id"]: p["name"] for p in ws.load("people", [])}
    from . import profmod
    out = ["# Discovery record\n", "What is known about this AI system, who said it, and what is still being found out. Generated %s.\n" % iso()[:16].replace("T", " "),
           profmod.render_record(ws, pr)]
    qs = [r for r in pr.load("requests", []) if r.get("type") == "discovery_question"]
    out.append("\n## Questions sent to people\n")
    if not qs:
        out.append("- None.")
    for r in qs:
        try:
            subj = open(pr.root / r["message_file"], encoding="utf-8").readline().lstrip("# ").strip()
        except (OSError, KeyError):
            subj = ""
        out.append("- %s: %s%s (sent %s%s)" % (names.get(r["to"], r["to"]), subj + " - " if subj else "", r["status"], (r.get("sent") or "")[:10],
                                         ", answered " + r["answered"][:10] if r.get("answered") else ""))
    from . import concernmod
    cs_ = pr.load("concerns", [])
    if cs_:
        out.append("\n## What AIGRCeler noticed or proposes (its own reading, not anyone's decision)\n")
        for c in cs_:
            out.append("- %s (%s, %s%s)" % (c["text"], c["kind"], c["status"], (", carried to " + norm_stage(c["carry_to"]).capitalize()) if c.get("carry_to") else ""))
    return "\n".join(out) + "\n"


def launch_status(ws, pr, cs):
    j = pr.journal().last()
    req = [c for c in active(cs) if c["definition"].get("launch_required") or c["definition"].get("critical")]
    items = [{"control": c["id"], "title": c["title"], "state": c["state"], "approved": c["state"] != "drafted",
              "verified": c["state"] in ("verified", "monitored"), "strength": c.get("strength")} for c in req]
    ready = bool(items) and all(i["verified"] or c["state"] == "waived" for i, c in zip(items, req))
    inc_open = [i["id"] for i in pr.load("incidents", []) if i["status"] == "open" and i["severity"] in ("high", "critical")]
    ready = ready and not inc_open
    so = (pr.info().get("signoffs") or [])
    return {"project": pr.slug, "generated": iso(), "ready_to_launch": ready,
            "high_or_critical_incidents_open": inc_open,
            "last_go_decision": ({"seq": so[-1]["seq"], "time": so[-1]["time"], "by": so[-1]["by"], "items_left_open": len(so[-1]["open_items"])} if so else None),
            "required_controls": items, "journal_seq": j["seq"] if j else 0, "journal_hash": j["hash"] if j else None,
            "note": "Published by AIGRCeler. The company's own deployment pipeline may read this file. The framework does not enforce it."}


def person_timelines(ws, pr):
    reqs = pr.load("requests", [])
    evs = pr.load("evidence", [])
    fnd = {f["evidence"]: f for f in pr.load("findings", [])}
    titles = {c["id"]: c["title"] for c in pr.all_controls()}
    for p in ws.load("people", []):
        mine = [r for r in reqs if r["to"] == p["id"]]
        ev = [e for e in evs if e.get("submitted_by") == p["id"]]
        if not mine and not ev:
            continue
        ev_events = []
        for r in mine:
            what = titles.get(r["controls"][0], "") if len(r["controls"]) == 1 else "%d items" % len(r["controls"])
            ev_events.append((r["sent"], "We sent you a message about: %s. Due %s." % (what, r["due"] or "no date")))
            if r.get("answered"):
                ev_events.append((r["answered"], "Your reply to that message was received."))
        for e in ev:
            ev_events.append((e["collected"], "You sent: %s (for: %s)." % (e.get("original_name") or e["type"], titles.get(e["control"], ""))))
            f = fnd.get(e["id"])
            if f:
                ev_events.append((f["time"], "We reviewed %s: %s." % (e.get("original_name") or "it", {"satisfied": "accepted", "partly": "covers part of what was needed",
                                  "not": "does not yet meet what was needed", "cannot-tell": "we need to ask you a question"}[f["verdict"]])))
        ev_events.sort()
        base = pr.p("people", p["folder"])
        lines = ["# Your history with the AI system \"%s\"\n" % pr.info()["name"],
                 "Folder 'to-person' holds what we sent you. Folder 'from-person' is where you put your replies and files.\n"]
        lines += ["- %s  %s" % (t[:10], txt) for t, txt in ev_events]
        write_text(base / "timeline.md", "\n".join(lines) + "\n")


def project_readme(ws, pr):
    info = pr.info()
    return """# %s: folder guide

| Folder | What is in it |
|---|---|
| 00-status | Generated views for AI Governance. Safe to delete; they are rebuilt. |
| controls | One file per control on this AI system, grouped by area. Written by the tool only. |
| evidence | What owners sent, one folder per piece, with a fingerprint on record. Never edited. |
| incidents | One page per incident, with timeline and retrospective. |
| decisions | The decision journal (one line per decision) and the full texts of longer decisions. |
| people | One folder per person who works on this AI system. What we sent them and what they sent back. |
| working-papers | Drafts, reviews and cover notes. May be archived once superseded. |
| logs | Gate runs, import logs, indicator readings. |
| data | The structured records. Written by the tool only; do not edit by hand. |

Lane: %s. Sourcing: %s. Generated %s.
""" % (info["name"], info.get("lane"), info.get("sourcing_mode"), iso()[:16].replace("T", " "))


def regenerate_project(ws, pr):
    cs = pr.all_controls()
    st = pr.p("00-status")
    write_text(st / "1-status-by-area.md", view_by_domain(ws, pr, cs))
    write_text(st / "2-who-owns-what.md", view_by_role(ws, pr, cs))
    write_text(st / "3-coverage-by-stage.md", view_by_phase(ws, pr, cs))
    write_text(st / "4-status-by-trust-property.md", view_by_property(ws, pr, cs))
    write_text(st / "5-risk.md", view_risk(ws, pr))
    write_text(st / "0-what-is-waiting.md", view_open(ws, pr, cs))
    write_text(st / "decision-journal.md", "# Decision journal\n\nOne line per decision. Generated from the journal file.\n\n" + pr.journal().render_table())
    write_text(st / "discovery-record.md", view_discovery(ws, pr))
    from . import regmod
    write_text(st / "6-regulatory-view.md", regmod.render_project(ws, pr))
    write_json(st / "launch-status.json", launch_status(ws, pr, cs))
    if pr.info()["stages"].get("OPERATE", {}).get("status") == "started":
        from . import chasemod
        write_text(st / "7-chase-list.md", "# Chase list\n\n```\n" + chasemod.render(ws, pr) + "```\n")
    write_text(pr.p("README.md"), project_readme(ws, pr))
    person_timelines(ws, pr)


def regenerate_workspace(ws):
    roles = ws.load("roles", [])
    projs = [ws.project(s) for s in ws.project_slugs()]
    st = ws.p("00-status")
    rows = []
    for code in DOMAINS:
        row = [DOMAIN_TITLES[code]]
        for r in roles:
            if r.get("governance"):
                row.append("approves all")
                continue
            tot = ver = 0
            for pr in projs:
                for c in active(pr.all_controls()):
                    if c["domain"] == code and c["owner_role"] == r["id"]:
                        tot += 1
                        ver += c["state"] in ("verified", "monitored")
            row.append(("%d of %d verified" % (ver, tot) if tot else "") + (" **(accountable)**" if code in r.get("default_domains", []) else ""))
        rows.append(row)
    write_text(st / "who-owns-what-across-all-systems.md",
               "# Who owns what, across all AI systems\n\nGenerated %s.\n\n" % iso()[:16].replace("T", " ") + table(["Area"] + [r["name"] for r in roles], rows))
    prow = []
    for pr in projs:
        info = pr.info()
        s = pr.load("risk_summary") or {}
        cs = active(pr.all_controls())
        prow.append([info["name"], info.get("lane") or "?", info.get("current_stage") or "not started",
                     "%d of %d" % (len([c for c in cs if c["state"] in ("verified", "monitored")]), len(cs)),
                     "%s (%s)" % (s.get("residual_total", "-"), s.get("residual_band", "-"))])
    write_text(st / "ai-systems.md", "# AI systems in scope\n\n" + table(["AI system", "Lane", "Stage", "Controls verified", "Residual risk"], prow))
    org = ws.load("organizational_risks", [])
    write_text(st / "company-level-risks.md", "# Company-level risks\n\nTracked here, not added into any one AI system's score.\n\n" + (
        table(["Ref", "Risk", "Inherent", "Residual", "Status"], [[o["id"], o["title"], o["inherent"], o["residual"], "accepted" if o["acceptance"] else "open"] for o in org]) if org else "None recorded yet.\n"))
    write_text(st / "decision-journal.md", "# Company-level decision journal\n\n" + ws.journal().render_table())
    props = []
    pdir = ws.p("catalog", "proposals")
    if pdir.exists():
        for f in sorted(pdir.glob("P-*.json")):
            p = read_json(f)
            props.append([p["id"], p["status"], p["kind"], p["target"], p["source"], p["reason"][:90]])
    write_text(st / "catalog-proposals.md", "# Catalog proposals\n\n" + (table(["Ref", "Status", "Kind", "Control", "Source", "Why"], props) if props else "None.\n"))
    for pr in projs:
        regenerate_project(ws, pr)


def _refresh_all(ws, slugs):
    from .evidmod import refresh
    for sl in slugs:
        refresh(ws, ws.project(sl))


def cmd_regenerate(args, ws):
    _refresh_all(ws, [args.project] if args.project else ws.project_slugs())
    if args.project:
        regenerate_project(ws, ws.project(args.project))
        print("Views for %s rebuilt." % args.project)
    else:
        regenerate_workspace(ws)
        print("Views for the workspace and all AI systems rebuilt.")


def cmd_launch_status(args, ws):
    pr = ws.project(args.project)
    _refresh_all(ws, [pr.slug])
    ls = launch_status(ws, pr, pr.all_controls())
    write_json(pr.p("00-status", "launch-status.json"), ls)
    print("Ready to launch: %s (%d required controls)." % (ls["ready_to_launch"], len(ls["required_controls"])))
