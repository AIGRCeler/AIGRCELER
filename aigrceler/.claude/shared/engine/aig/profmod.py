"""The discovery profile: what DISCOVER learns about one AI system, who said it and when.

The questions live in shared/catalog/discovery-profile.json. How many are required depends on the lane
(core for light, plus standard for standard, everything for full) and on the system (some questions are asked
only when they apply). Answers are recorded with their source. A required question may be left "unknown"
only after a named person was really asked, only if it does not decide the lane, and only up to a limit
(20% of the required questions by default); each unknown is carried to ASSESS as a concern and makes the matching
risk scenarios start one step worse. Mapped answers are also written to the system record, and answers that
raise a factor raise it (never lower it: lowering is AI Governance's decision)."""
import json
import re

from .core import clip
from .core import (
    AigError, iso, today, read_json, write_json, split_list, resolve_actor, active_assignments,
    is_governance_person, SOURCING_MODES, FLAGS,
)
from .wsmod import SHARED

LEVEL_RANK = {"core": 0, "standard": 1, "full": 2}
LANE_LEVEL = {"light": "core", "standard": "standard", "full": "full"}
DEFAULT_UNKNOWN_LIMIT = 0.20
PLACEHOLDER = re.compile(r"\s*(unknown|not known|don'?t know|do not know|asked\b|to be confirmed|tbc|tbd|n/?a|pending|none yet|not sure)\b", re.I)
GUESS = re.compile(r"\b(guess|guessed|assum\w*|inferred|probably|presumably|likely)\b", re.I)
SCREEN_FIELDS = {"user_scale": "users", "autonomy": "autonomy", "data_kind": "data", "impact_level": "impact"}

_CACHE = {}


def catalog():
    if "c" not in _CACHE:
        _CACHE["c"] = read_json(SHARED / "catalog" / "discovery-profile.json")
        _CACHE["by"] = {f["id"]: f for f in _CACHE["c"]["fields"]}
    return _CACHE["c"]


def fields():
    return catalog()["fields"]


def field_def(fid):
    catalog()
    fd = _CACHE["by"].get(fid)
    if not fd:
        raise AigError("There is no discovery question '%s'. See 'profile show' for the list." % fid)
    return fd


# ------------------------------------------------------------------ storage ----
def load(pr):
    p = pr.load("profile", None)
    if not p:
        p = {"version": catalog().get("version", "1.0"), "fields": {}, "asked": {}, "docs": []}
    p.setdefault("fields", {})
    p.setdefault("asked", {})
    p.setdefault("docs", [])
    return p


def save(pr, prof):
    pr.save("profile", prof)


# ----------------------------------------------------------------- values ----
def _is_placeholder(v):
    items = v if isinstance(v, list) else [v]
    return not any(str(i).strip() and not PLACEHOLDER.match(str(i)) for i in items)


def norm_yesno(v):
    t = str(v).strip().lower()
    m = re.match(r"(yes|y|true|no|n|false)\b", t)
    if not m:
        return None
    return "yes" if m.group(1) in ("yes", "y", "true") else "no"


def norm_choice(fd, v):
    t = re.sub(r"\s+", "-", str(v).strip().lower())
    t = t.replace("authorized-representative", "authorised-representative")
    return t if t in fd["choices"] else None


def check_value(fd, raw):
    """Return the value to store, or raise in plain words."""
    if raw is None or (isinstance(raw, str) and not raw.strip()) or raw == []:
        raise AigError("'%s' has no value. Leave the question open instead." % fd["id"])
    if isinstance(raw, list):
        raw = "; ".join(str(x) for x in raw)
    raw = str(raw).strip()
    if fd["kind"] == "choice":
        c = norm_choice(fd, raw)
        if c is not None:
            return c
    if _is_placeholder(raw):
        raise AigError("'%s' is not an answer to \"%s\". If the person truly does not know, use 'profile unknown' after asking them. Otherwise leave it open." % (raw[:40], fd["label"]))
    k = fd["kind"]
    if fd["id"] == "model_version":
        # compared word for word with the version named in evidence reports, so it must be a name, not a sentence
        if len(raw) > 60 or len(raw.split()) > 4 or ":" in raw or raw.endswith("."):
            raise AigError("The model version must be the version name only, for example kestrel-rank-4.2, because test reports are matched against it word for word. Put the story (who said so, what is known) in --source.")
    if k == "yesno":
        if norm_yesno(raw) is None:
            raise AigError("The answer to \"%s\" must start with yes or no (then, if useful, what). Got: %s" % (fd["label"], raw[:60]))
    elif k == "choice":
        c = norm_choice(fd, raw)
        if c is None:
            raise AigError("The answer to \"%s\" must be one of: %s." % (fd["label"], ", ".join(fd["choices"])))
        return c
    return raw


def answer_of(fd, entry):
    """The normalized answer (yes/no, the choice, or the text) when answered; else None."""
    if not entry or entry.get("status") not in ("answered",):
        return None
    v = entry.get("value")
    if fd["kind"] == "yesno":
        return norm_yesno(v)
    return v


# ------------------------------------------------------------ applicability ----
def lane_level(info):
    ln = info.get("lane") if info.get("lane_decided") else (info.get("lane_suggested") or info.get("lane"))
    return LANE_LEVEL.get(ln, "core")


def _prefill(fd, info):
    """Facts already recorded on the system before the profile existed count as answered (source: earlier record)."""
    m = fd.get("maps")
    v = None
    if m == "purpose":
        v = info.get("purpose")
    elif m in ("users", "human_review", "model_version", "resources"):
        v = info.get(m)
    elif m == "sourcing_mode":
        v = info.get("sourcing_mode")
    elif m in ("data_sources", "eval_metrics", "downstream_dependencies"):
        v = info.get(m)
        if m == "downstream_dependencies" and isinstance(v, list) and v:
            v = "; ".join(v)
    elif m in ("techniques", "jurisdictions"):
        v = info.get(m)
    elif m == "consequential_actions":
        v = "yes" if info.get("consequential_actions") else None
    if isinstance(v, list):
        v = "; ".join(str(x) for x in v)
    if v and not _is_placeholder(v):
        return {"status": "answered", "value": v if fd["kind"] not in ("choice",) else norm_choice(fd, v) or v,
                "source": "recorded earlier on the system record", "recorded": None, "prefilled": True}
    sc = info.get("screening") or {}
    for fid, key in SCREEN_FIELDS.items():
        if fd["id"] == fid and sc.get(key):
            return {"status": "answered", "value": sc[key], "source": "the screening recorded earlier", "recorded": None, "prefilled": True}
    fl = info.get("flags") or {}
    flagmap = {"generative": "generative", "about_people": "decisions_about_people", "customer_output": "customer_facing_automated",
               "safety_impact": "safety_impact", "regulated_sector": "regulated_sector"}
    if fd["id"] in flagmap and fl.get(flagmap[fd["id"]]):
        return {"status": "answered", "value": "yes", "source": "the factor recorded earlier on the system record", "recorded": None, "prefilled": True}
    return None


def _when_ok(fd, info, answers):
    when = fd.get("when") or []
    if not when:
        return True
    fl = {k for k, v in (info.get("flags") or {}).items() if v}
    if info.get("consequential_actions"):
        fl.add("consequential_actions")
    for alt in when:
        ok = True
        if "flags_any" in alt and not any(f in fl for f in alt["flags_any"]):
            ok = False
        if ok and "sourcing_in" in alt and info.get("sourcing_mode") not in alt["sourcing_in"]:
            ok = False
        if ok and "sourcing_not" in alt and (not info.get("sourcing_mode") or info.get("sourcing_mode") in alt["sourcing_not"]):
            ok = False
        if ok and "answers" in alt:
            for dep, vals in alt["answers"].items():
                a = answers.get(dep)
                # a dependency not yet answered (or unknown) is treated as "could apply": ask rather than skip
                if a is not None and a not in vals:
                    ok = False
        if ok:
            return True
    return False


def unknown_limit(ws):
    try:
        v = ws.settings().get("discovery_unknown_limit")
        return float(v) if v is not None else DEFAULT_UNKNOWN_LIMIT
    except (TypeError, ValueError, AigError):
        return DEFAULT_UNKNOWN_LIMIT


def state(ws, pr, info=None, prof=None):
    """Work out where each question stands for this system today. Pure: writes nothing."""
    info = info or pr.info()
    prof = prof or load(pr)
    level = lane_level(info)
    entries = {}
    for fd in fields():
        e = prof["fields"].get(fd["id"])
        if not e:
            e = _prefill(fd, info)
        entries[fd["id"]] = e
    answers = {}
    for fd in fields():
        a = answer_of(fd, entries.get(fd["id"]))
        if a is not None:
            answers[fd["id"]] = a
    rows = []
    for fd in fields():
        e = entries.get(fd["id"])
        applies = _when_ok(fd, info, answers)
        required = applies and LEVEL_RANK[fd["level"]] <= LEVEL_RANK[level]
        if e and e.get("status") == "na":
            st = "na"
        elif e and e.get("status") in ("answered", "unknown", "inferred"):
            st = e["status"]
        else:
            st = "open"
        rows.append({"def": fd, "entry": e, "status": st, "applies": applies, "required": required})
    req = [r for r in rows if r["required"]]
    counts = {"required": len(req)}
    for s in ("answered", "unknown", "inferred", "na", "open"):
        counts[s] = sum(1 for r in req if r["status"] == s)
    skipped = counts["unknown"] + sum(1 for r in req if r["status"] == "na" and not r["def"]["when"])
    counts["skipped"] = skipped
    counts["rate"] = (skipped / float(len(req))) if req else 0.0
    counts["limit"] = unknown_limit(ws)
    counts["level"] = level
    return {"rows": rows, "counts": counts, "level": level}


def _names(rows, n=10):
    labs = [r["def"]["label"] for r in rows]
    return ", ".join(labs[:n]) + (" and %d more" % (len(labs) - n) if len(labs) > n else "")


def gate_items(ws, pr, info=None):
    """The reasons DISCOVER cannot close because of the profile, in plain words."""
    info = info or pr.info()
    st = state(ws, pr, info)
    c = st["counts"]
    out = []
    fl = info.get("flags") or {}
    if fl.get("decisions_about_people") and (fl.get("regulated_sector") or fl.get("eu_high_risk")) \
            and not info.get("blocks") and not info.get("block_review"):
        out.append("A possible legal hard stop has not been looked at: this system shapes decisions about people in a regulated field. "
                   "Place a stage block now (stage block --reason \"<the facts; whether rules apply is a question for counsel>\") "
                   "or record why none is needed (stage block-review --reason \"<at least ten words>\").")
    openr = [r for r in st["rows"] if r["required"] and r["status"] in ("open", "inferred")]
    if openr:
        openr.sort(key=lambda r: (not r["def"]["crit"], LEVEL_RANK[r["def"]["level"]]))
        out.append("Still to find out (%d of %d discovery questions): %s." % (len(openr), c["required"], _names(openr, 16)))
    if c["rate"] > c["limit"] + 1e-9:
        out.append("Too many answers are \"not known\" or skipped (%d of %d required questions, %d%%; the limit is %d%%). "
                   "The risk assessment would rest on guesses. Ask the people who might know, or AI Governance closes Discover knowingly."
                   % (c["skipped"], c["required"], round(c["rate"] * 100), round(c["limit"] * 100)))
    return out


def summary_line(ws, pr, info=None):
    c = state(ws, pr, info)["counts"]
    return ("Discovery profile (%s depth): %d of %d required questions answered, %d not known after asking (%d%%, limit %d%%), %d still open."
            % (c["level"], c["answered"], c["required"], c["unknown"], round(c["rate"] * 100), round(c["limit"] * 100), c["open"] + c["inferred"]))


def uncertain_for(ws, pr, info, scenario_id):
    """Labels of required questions that feed this scenario and are not answered (for the risk starting point)."""
    st = state(ws, pr, info)
    return [r["def"]["label"] for r in st["rows"]
            if r["required"] and scenario_id in r["def"]["scen"] and r["status"] in ("unknown", "inferred", "open")]


# ---------------------------------------------------------------- concerns ----
def _add_concern(pr, kind, text, carry_to, key):
    items = pr.load("concerns", [])
    for c in items:
        if c.get("key") == key and c["status"] == "open":
            return c["id"]
    cid = pr.next_id("CON", "CON")
    items.append({"id": cid, "kind": kind, "text": text, "carry_to": carry_to,
                  "raised_by": "AIGRCeler (its own reading)", "asked_to_keep_by": None,
                  "raised": iso(), "status": "open", "resolved": None, "resolution": None, "key": key})
    pr.save("concerns", items)
    return cid


def _resolve_concern(pr, key, note):
    items = pr.load("concerns", [])
    done = False
    for c in items:
        if c.get("key") == key and c["status"] == "open":
            c["status"] = "resolved"
            c["resolved"] = iso()
            c["resolution"] = note
            done = True
    if done:
        pr.save("concerns", items)
    return done


# ------------------------------------------------------------- derivations ----
class _A:
    """Arguments for calling another command from here; anything not given is None."""
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __getattr__(self, name):
        if name.startswith("__"):
            raise AttributeError(name)
        return None


FLAG_ON = {   # an answer of 'yes' (or the value) raises this factor
    "generative": ("yes", "generative"),
    "about_people": ("yes", "decisions_about_people"),
    "customer_output": ("yes", "customer_facing_automated"),
    "safety_impact": ("yes", "safety_impact"),
    "regulated_sector": ("yes", "regulated_sector"),
}


def _derive(ws, pr, changed):
    """Write mapped answers to the system record, raise factors, run the screening, and report. Never lowers anything."""
    from . import projmod
    info = pr.info()
    prof = load(pr)
    st = state(ws, pr, info, prof)
    ent = {r["def"]["id"]: r for r in st["rows"]}
    notes = []
    kw = {}
    flags_on = []
    lowering = []

    def ans(fid):
        r = ent[fid]
        return answer_of(r["def"], r["entry"]) if r["entry"] else None

    def raw(fid):
        r = ent[fid]
        return r["entry"]["value"] if r["entry"] and r["entry"].get("status") == "answered" else None

    for fid in changed:
        fd = ent[fid]["def"]
        m = fd.get("maps")
        v = raw(fid)
        if v is None:
            continue
        if m in ("purpose", "users", "human_review", "model_version", "resources", "jurisdictions", "data_sources",
                 "eval_metrics", "downstream_dependencies", "techniques"):
            if m == "downstream_dependencies":
                items = split_list(v)
                if items and len(items) == 1 and re.match(r"\s*(nothing|none)\b", items[0], re.I):
                    items = []
                    notes.append("Nothing depends on it (recorded).")
                if len(items) < len(info.get("downstream_dependencies") or []):
                    lowering.append("fewer systems depend on it")
                    continue
                kw[m] = ";".join(items) if items else ""
                if not items:
                    info["downstream_dependencies"] = []
                    pr.save_info(info)
                    kw.pop(m)
            else:
                kw[m] = v
        elif m == "sourcing_mode":
            if v in SOURCING_MODES:
                if info.get("sourcing_mode") and info["sourcing_mode"] != v:
                    lowering.append("sourcing changed from %s to %s" % (info["sourcing_mode"], v))
                else:
                    kw["sourcing_mode"] = v
        elif m == "consequential_actions":
            if ans(fid) == "yes":
                kw["consequential_actions"] = "true"
            elif info.get("consequential_actions"):
                lowering.append("'it takes actions with real consequences' switched off")
        if fid in FLAG_ON:
            want, flag = FLAG_ON[fid]
            if ans(fid) == want:
                if not info["flags"].get(flag):
                    flags_on.append(flag)
            elif info["flags"].get(flag):
                lowering.append("'%s' switched off" % projmod.PLAIN.get(flag, flag))
        if fid == "data_kind":
            if v == "personal" and not info["flags"].get("personal_data"):
                flags_on.append("personal_data")
            if v == "sensitive":
                for f_ in ("personal_data", "sensitive_data"):
                    if not info["flags"].get(f_):
                        flags_on.append(f_)
            if v == "none" and (info["flags"].get("personal_data") or info["flags"].get("sensitive_data")):
                lowering.append("'it uses personal data' switched off")
        if fid == "eu_class_view":
            if v == "high-risk" and not info["flags"].get("eu_high_risk"):
                flags_on.append("eu_high_risk")
            elif v == "prohibited-concern":
                _add_concern(pr, "proposal",
                             "The answer on its EU AI Act class raises a possible prohibited use. AIGRCeler proposes placing a stage block until counsel has said whether the use is allowed "
                             "(stage block --reason \"possible prohibited use; a question for counsel\").",
                             None, "eu-prohibited")
                notes.append("A possible prohibited use was raised as a proposal for AI Governance to decide.")
            elif v == "not-sure":
                _add_concern(pr, "concern",
                             "Nobody could say how the EU AI Act classifies this use. It is a question for counsel; until counsel answers, treat the legal risk as unresolved.",
                             "ASSESS", "eu-class-unknown")
    if flags_on or kw:
        a = _A(project=pr.slug, flags_on=",".join(sorted(set(flags_on))) if flags_on else None, **kw)
        projmod.cmd_set(a, ws)
    for l in lowering:
        _add_concern(pr, "concern",
                     "A discovery answer says the opposite of what the system record has (%s). The record was not changed: lowering what drives the lane and the risk floors is a decision for AI Governance "
                     "(project set ... --by <name> --statement \"<their words>\")." % l, "ASSESS", "lowering:" + l)
        notes.append("This answer would lower something the lane depends on (%s); AI Governance has to decide that. Not changed." % l)
    # screening: all four answered and none recorded yet -> run it (do and tell)
    info = pr.info()
    scr = {SCREEN_FIELDS[f]: ans(f) for f in SCREEN_FIELDS if ans(f)}
    if len(scr) == 4:
        if not info.get("screening"):
            print("All four screening questions are answered; running the screening.")
            projmod.cmd_screen(_A(project=pr.slug, users=scr["users"], autonomy=scr["autonomy"], data=scr["data"], impact=scr["impact"]), ws)
        else:
            diff = [k for k in scr if info["screening"].get(k) != scr[k]]
            if diff and any(f in changed for f in SCREEN_FIELDS):
                _add_concern(pr, "concern",
                             "The discovery answers (%s) differ from the screening on record (%s). AI Governance should confirm which is right; the recorded tier was not changed."
                             % (", ".join("%s: %s" % (k, scr[k]) for k in diff), ", ".join("%s: %s" % (k, info["screening"].get(k)) for k in diff)),
                             "ASSESS", "screening-differs")
                notes.append("These answers differ from the screening on record; AI Governance should confirm which is right.")
    return notes


# ---------------------------------------------------------------- commands ----
def _load_file(path):
    from .core import check_file, read_any_text
    p = check_file(path, "answers file")
    try:
        data = json.loads(read_any_text(p))
    except ValueError:
        raise AigError("The answers file must be JSON: {\"field\": \"answer\", ...} (optionally {\"field\": {\"value\": ..., \"source\": ...}}).")
    if not isinstance(data, dict):
        raise AigError("The answers file must be one JSON object of question: answer.")
    return data


def cmd_set(args, ws):
    pr = ws.project(args.project)
    items = {}
    default_source = args.source
    if args.file:
        data = _load_file(args.file)
        default_source = data.pop("_source", None) or default_source
        for k, v in data.items():
            if isinstance(v, dict):
                items[k] = (v.get("value"), v.get("source") or default_source)
            else:
                items[k] = (v, default_source)
    if args.field:
        if args.value is None:
            raise AigError("Give the answer (--value).")
        items[args.field] = (args.value, default_source)
    if not items:
        raise AigError("Give --field and --value, or --file with several answers.")
    prof = load(pr)
    info = pr.info()
    done, changed = [], []
    for fid, (val, src) in items.items():
        fd = field_def(fid)
        if not src or not str(src).strip():
            raise AigError("Say who told you, or which document says it (--source), for '%s'. Do not record a fact from a guess." % fid)
        inferred = bool(args.inferred)
        if GUESS.search(str(src)) and not inferred:
            raise AigError("\"%s\" is not a source. If you inferred the answer, say so with --inferred: it is kept, but stays open until a person confirms it." % str(src)[:50])
        value = check_value(fd, val)
        old = prof["fields"].get(fid)
        entry = {"status": "inferred" if inferred else "answered", "value": value, "source": str(src).strip(),
                 "recorded": iso(), "history": (old or {}).get("history", [])}
        if old:
            entry["history"] = entry["history"] + [{k: old.get(k) for k in ("status", "value", "source", "recorded", "reason", "asked")}]
        if old and old.get("concern"):
            if _resolve_concern(pr, "unknown:" + fid, "answered later: %s" % str(src).strip()[:80]):
                done.append("%s no longer unknown" % fd["label"])
        prof["fields"][fid] = entry
        changed.append(fid)
    save(pr, prof)
    pr.journal().append("profile_recorded", ["project:" + pr.slug], "tool:aigrceler",
                        "Discovery answers recorded (%d): %s" % (len(changed), clip(", ".join(changed), 220)),
                        labels=["tool"], extra={"fields": changed, "sources": sorted({str(s).strip() for _, s in items.values()})[:6]})
    notes = _derive(ws, pr, changed)
    print("Recorded %d answer(s): %s." % (len(changed), ", ".join(field_def(f)["label"] for f in changed)))
    for n in done + notes:
        print("  - " + n)
    print(summary_line(ws, pr))
    gaps = gate_items(ws, pr)
    for g in gaps:
        print("  - " + g)


def _holder(ws, role):
    best = None
    for a in active_assignments(ws):
        if a["role"] == role:
            if a.get("kind") == "primary":
                return a["person"]
            best = best or a["person"]
    return best


def respondent(ws, info, who):
    """(person id or None, description) for a respondent token."""
    gov = [r["id"] for r in ws.load("roles", []) if r.get("governance")]
    if who == "vendor":
        return None, "the vendor contact (AI Governance names who that is)"
    if who == "ai-governance":
        for g in gov:
            p = _holder(ws, g)
            if p:
                return p, "AI Governance"
        return None, "AI Governance"
    role = info.get("business_owner_role") or "operations" if who == "business-owner" else who
    p = _holder(ws, role)
    names = {x["id"]: x["name"] for x in ws.load("people", [])}
    return p, ("%s (%s)" % (names.get(p, p), role)) if p else ("whoever holds the %s role (nobody is named yet)" % role)


def _plan(ws, pr):
    info = pr.info()
    st = state(ws, pr, info)
    prof = load(pr)
    openr = [r for r in st["rows"] if r["required"] and r["status"] in ("open", "inferred")]
    groups = {}
    for r in openr:
        p, desc = respondent(ws, info, r["def"]["who"])
        groups.setdefault(p or ("role:" + r["def"]["who"]), {"person": p, "desc": desc, "rows": []})["rows"].append(r)
    return st, prof, groups


def _message(info, rows):
    pu = (info.get("purpose") or "").strip()
    if len(pu) > 100:
        pu = pu[:100].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    what = (" (%s)" % pu) if pu else ""
    lines = ["Some questions about \"%s\"%s. Please answer each one in your own words, in a few lines. If you do not know, say so and tell us who might: that is a useful answer too, and we will ask them.\n" % (
        info["name"], what)]
    for i, r in enumerate(rows, 1):
        lines.append("%d. %s" % (i, r["def"]["q"]))
    return "\n".join(lines)


def cmd_plan(args, ws):
    from .ctrlmod import _write_request, _default_due, person_name
    from .core import parse_date
    pr = ws.project(args.project)
    info = pr.info()
    st, prof, groups = _plan(ws, pr)
    c = st["counts"]
    print(summary_line(ws, pr, info))
    if not groups:
        print("Nothing is open: every required question is answered or recorded as not known.")
        return
    gov_p, _ = respondent(ws, info, "ai-governance")
    send = bool(args.send)
    due = parse_date(args.due, "due date") if args.due else _default_due()
    sent_any = False
    for key, g in groups.items():
        p = g["person"]
        rows = g["rows"]
        # skip questions already asked of this person whose request is still open
        reqs = {r["id"]: r for r in pr.load("requests", [])}
        fresh = []
        for r in rows:
            asked = [a for a in prof["asked"].get(r["def"]["id"], []) if a["to"] == p and reqs.get(a["request"], {}).get("status") == "open"]
            if not asked:
                fresh.append(r)
        if p and p == gov_p:
            print("\nAsk AI Governance in the conversation, all in one message (%d questions):" % len(rows))
            for i, r in enumerate(rows, 1):
                print("  %d. %s" % (i, r["def"]["q"]))
            continue
        if not p:
            print("\n%d question(s) for %s. Ask AI Governance who that is:" % (len(rows), g["desc"]))
            for r in rows:
                print("  - %s" % r["def"]["label"])
            continue
        if not fresh:
            print("\n%s: %d question(s) already sent and waiting for a reply." % (person_name(ws, p), len(rows)))
            continue
        print("\nTo %s (%d question(s)):" % (person_name(ws, p), len(fresh)))
        for i, r in enumerate(fresh, 1):
            print("  %d. %s" % (i, r["def"]["q"]))
        if send:
            subject = "Questions about %s" % info["name"]
            rid = _write_request(ws, pr, p, "discovery_question", subject, _message(info, fresh), due)
            for r in fresh:
                prof["asked"].setdefault(r["def"]["id"], []).append({"to": p, "request": rid, "at": iso()})
            save(pr, prof)
            sent_any = True
            print("  -> message %s written to %s's folder, reply wanted by %s." % (rid, person_name(ws, p), due))
    if not send:
        print("\nThis is a draft. Once AI Governance agrees, send it with: profile plan --send")
    elif sent_any:
        print("\nTell AI Governance who was asked what. Discover stays open until these are answered.")


def cmd_unknown(args, ws):
    pr = ws.project(args.project)
    ids = split_list(args.field) if args.field else []
    if not ids:
        raise AigError("Say which question (--field).")
    if not args.asked or not args.reason:
        raise AigError("A question can be recorded as \"not known\" only after a named person was asked: give who (--asked) and what they said or why it cannot be found out (--reason).")
    people = {p["id"]: p for p in ws.load("people", [])}
    if args.asked not in people:
        raise AigError("'%s' is not in the people directory." % args.asked)
    if len(str(args.reason).split()) < 5 or _is_placeholder(args.reason):
        raise AigError("Say in a sentence why it is not known (at least five words): what the person said, or what was tried.")
    prof = load(pr)
    info = pr.info()
    st = state(ws, pr, info, prof)
    rows = {r["def"]["id"]: r for r in st["rows"]}
    for fid in ids:
        fd = field_def(fid)
        if fd["crit"]:
            raise AigError("\"%s\" decides the tier, the lane or a risk floor, so it cannot be left unknown. Keep asking, or ask someone who knows." % fd["label"])
        if not rows[fid]["required"]:
            raise AigError("\"%s\" is not required for this system, so there is nothing to record." % fd["label"])
    reqs = pr.load("requests", [])
    if not is_governance_person(ws, args.asked) and not any(r["to"] == args.asked for r in reqs):
        raise AigError("%s has not been sent a question yet. Ask them first (profile plan --send), then record the answer or that they do not know." % people[args.asked]["name"])
    done = []
    for fid in ids:
        fd = field_def(fid)
        old = prof["fields"].get(fid) or {}
        key = "unknown:" + fid
        cid = _add_concern(pr, "concern",
                           "Not known after asking %s: %s. Assess treats the related risks (%s) as less certain and starts them one step worse until this is answered. Reason: %s"
                           % (people[args.asked]["name"], fd["label"], ", ".join(fd["scen"]) or "none", str(args.reason).strip()),
                           "ASSESS", key)
        hist = old.get("history", [])
        if old.get("status"):
            hist = hist + [{k: old.get(k) for k in ("status", "value", "source", "recorded", "reason", "asked")}]
        prof["fields"][fid] = {"status": "unknown", "value": None, "reason": str(args.reason).strip(), "asked": args.asked,
                               "source": "asked %s" % people[args.asked]["name"], "recorded": iso(), "concern": cid, "history": hist}
        done.append(fd["label"])
    save(pr, prof)
    pr.journal().append("profile_unknown", ["project:" + pr.slug], "tool:aigrceler",
                        "Recorded as not known after asking %s: %s" % (people[args.asked]["name"], ", ".join(ids)),
                        labels=["tool"], extra={"fields": ids, "asked": args.asked})
    print("Recorded as not known after asking %s: %s." % (people[args.asked]["name"], ", ".join(done)))
    print("Each is now a concern carried to Assess, and the related risk scenarios will start one step worse.")
    print(summary_line(ws, pr))
    for g in gate_items(ws, pr):
        print("  - " + g)


def cmd_na(args, ws):
    pr = ws.project(args.project)
    ids = split_list(args.field) if args.field else []
    if not ids or not args.reason:
        raise AigError("Give the question (--field) and why it does not apply to this system (--reason).")
    if len(str(args.reason).split()) < 5:
        raise AigError("Say in a sentence why it does not apply (at least five words).")
    prof = load(pr)
    for fid in ids:
        fd = field_def(fid)
        if fd["crit"]:
            raise AigError("\"%s\" applies to every system; it cannot be marked as not applicable." % fd["label"])
        prof["fields"][fid] = {"status": "na", "value": None, "reason": str(args.reason).strip(), "source": "not applicable",
                               "recorded": iso(), "history": (prof["fields"].get(fid) or {}).get("history", [])}
    save(pr, prof)
    pr.journal().append("profile_na", ["project:" + pr.slug], "tool:aigrceler",
                        "Marked not applicable: %s (%s)" % (", ".join(ids), str(args.reason).strip()[:120]), labels=["tool"])
    print("Marked as not applicable: %s. (A question that applies to every system but is skipped counts toward the limit.)" % ", ".join(field_def(f)["label"] for f in ids))
    print(summary_line(ws, pr))


def cmd_doc(args, ws):
    pr = ws.project(args.project)
    prof = load(pr)
    cat = {d["kind"]: d for d in catalog().get("documents", [])}
    if not args.kind:
        raise AigError("Give the kind of document (--kind): %s." % ", ".join(cat))
    if args.kind not in cat:
        raise AigError("Unknown kind '%s'. Known: %s." % (args.kind, ", ".join(cat)))
    status = args.status or "requested"
    if status not in ("requested", "received", "does-not-exist"):
        raise AigError("The status must be requested, received or does-not-exist.")
    rec = next((d for d in prof["docs"] if d["kind"] == args.kind), None)
    if not rec:
        rec = {"kind": args.kind}
        prof["docs"].append(rec)
    rec.update({"name": args.name or cat[args.kind]["name"], "status": status, "from": args.source or rec.get("from"), "updated": iso()})
    save(pr, prof)
    print("Document noted: %s (%s)." % (rec["name"], status))


def _docs_expected(ws, pr, info):
    st = state(ws, pr, info)
    out = []
    answers = {r["def"]["id"]: answer_of(r["def"], r["entry"]) for r in st["rows"] if r["entry"]}
    for d in catalog().get("documents", []):
        if LEVEL_RANK[d["level"]] > LEVEL_RANK[st["level"]]:
            continue
        if _when_ok(d, info, answers):
            out.append(d)
    return out


def _fmt(v):
    return "" if v is None else str(v)


def render_record(ws, pr):
    """Markdown for the discovery record: every question, the answer, who said it and when."""
    info = pr.info()
    prof = load(pr)
    st = state(ws, pr, info, prof)
    c = st["counts"]
    names = {p["id"]: p["name"] for p in ws.load("people", [])}
    out = []
    out.append("**%s**" % summary_line(ws, pr, info))
    out.append("")
    out.append("Depth follows the lane: light asks the core questions, standard adds more, full asks everything. "
               "A question may be left \"not known\" only after a named person was asked, never if it decides the lane, and not beyond %d%% of the required questions. "
               "Each unknown is carried to Assess and makes the related risks start one step worse." % round(c["limit"] * 100))
    secs = {s["id"]: s["title"] for s in catalog()["sections"]}
    for sid, title in secs.items():
        rs = [r for r in st["rows"] if r["def"]["section"] == sid and r["applies"]]
        if not rs:
            continue
        out.append("\n### %s. %s\n" % (sid, title))
        out.append("| Question | Answer | Who said it, and when |")
        out.append("|---|---|---|")
        for r in rs:
            fd, e = r["def"], r["entry"]
            mark = "" if r["required"] else " *(asked in a deeper lane)*"
            if r["status"] == "answered":
                src = _fmt(e.get("source")) + ((" · " + e["recorded"][:10]) if e.get("recorded") else "")
                out.append("| %s%s | %s | %s |" % (fd["label"].capitalize(), mark, _fmt(e.get("value")).replace("\n", " ").replace("|", "/"), src))
            elif r["status"] == "inferred":
                out.append("| %s%s | %s | **inferred, needs a person to confirm** (%s) |" % (fd["label"].capitalize(), mark, _fmt(e.get("value")), _fmt(e.get("source"))))
            elif r["status"] == "unknown":
                out.append("| %s%s | **not known after asking** | %s: %s (%s) |" % (fd["label"].capitalize(), mark, names.get(e.get("asked"), e.get("asked")), _fmt(e.get("reason")), (e.get("recorded") or "")[:10]))
            elif r["status"] == "na":
                out.append("| %s%s | not applicable | %s |" % (fd["label"].capitalize(), mark, _fmt(e.get("reason"))))
            else:
                out.append("| %s%s | **not recorded yet** | |" % (fd["label"].capitalize(), mark))
    miss = [r for r in st["rows"] if r["required"] and r["status"] in ("open", "inferred", "unknown")]
    if miss:
        out.append("\n## What is missing, and why it matters\n")
        for r in miss:
            fd = r["def"]
            lab = {"open": "open", "inferred": "inferred", "unknown": "not known"}[r["status"]]
            out.append("- **%s** (%s): %s Used for: %s%s." % (fd["label"], lab, fd["why"], ", ".join(fd["scen"]) or "-",
                                                         ("; controls " + ", ".join(fd["ctl"])) if fd["ctl"] else ""))
    docs = _docs_expected(ws, pr, info)
    have = {d["kind"]: d for d in prof["docs"]}
    if docs:
        out.append("\n## Documents to collect\n")
        for d in docs:
            h = have.get(d["kind"])
            out.append("- %s: %s" % (d["name"], ("%s%s" % (h["status"], (" from " + h["from"]) if h.get("from") else "")) if h else "not asked for yet"))
    return "\n".join(out) + "\n"


def cmd_show(args, ws):
    pr = ws.project(args.project)
    info = pr.info()
    st = state(ws, pr, info)
    print(summary_line(ws, pr, info))
    names = {p["id"]: p["name"] for p in ws.load("people", [])}
    for r in st["rows"]:
        if not r["required"]:
            continue
        if args.open and r["status"] in ("answered", "na"):
            continue
        fd, e = r["def"], r["entry"]
        who = respondent(ws, info, fd["who"])[1]
        extra = ""
        if r["status"] == "answered":
            extra = "%s [%s]" % (_fmt(e.get("value"))[:70], _fmt(e.get("source"))[:40])
        elif r["status"] == "unknown":
            extra = "asked %s: %s" % (names.get(e.get("asked"), e.get("asked")), _fmt(e.get("reason"))[:60])
        elif r["status"] == "na":
            extra = _fmt(e.get("reason"))[:60]
        else:
            extra = "ask: " + who
        print("  %-8s %-12s %-32s %s%s" % (r["status"], fd["id"][:12], fd["label"][:32], extra, "  (decides the lane)" if fd["crit"] else ""))


def cmd_for(args, ws):
    """Which recorded facts bear on a risk scenario, a control, or one question."""
    pr = ws.project(args.project)
    info = pr.info()
    st = state(ws, pr, info)
    sel = [r for r in st["rows"]
           if (args.scenario and args.scenario in r["def"]["scen"]) or (args.control and args.control in r["def"]["ctl"])
           or (args.field and args.field == r["def"]["id"])]
    if not (args.scenario or args.control or args.field):
        raise AigError("Give --scenario, --control or --field.")
    if not sel:
        print("No discovery question feeds that.")
        return
    for r in sel:
        fd, e = r["def"], r["entry"]
        val = _fmt(e.get("value")) if e and r["status"] == "answered" else ("not known after asking" if r["status"] == "unknown" else "not recorded")
        print("- %s: %s%s" % (fd["label"], val[:200], ("  [%s]" % e["source"]) if e and e.get("source") and r["status"] == "answered" else ""))
