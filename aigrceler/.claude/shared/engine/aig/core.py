"""AIGRCeler v2 core: storage, ids, journal (hash chain), authority.

Python standard library only. Every structured record in a workspace is written
by this engine and by nothing else. Agents call the commands; they never edit
records, status, fingerprints or the journal by hand.
"""
import datetime
import hashlib
import json
import os
import re
import shutil
from pathlib import Path


class AigError(Exception):
    """A refusal or a usage problem, worded for a person to read."""


DOMAINS = {
    "GO": "governance-and-organization",
    "DG": "data",
    "MD": "model",
    "TP": "third-party",
    "DO": "deployment-and-operations",
    "HR": "human-oversight-and-rights",
    "EA": "evidence-and-audit",
}
DOMAIN_TITLES = {
    "GO": "Governance and organization",
    "DG": "Data",
    "MD": "Model (built or adapted in-house)",
    "TP": "Third party",
    "DO": "Deployment and operations",
    "HR": "Human oversight and rights",
    "EA": "Evidence and audit",
}
STAGES = ["DISCOVER", "ASSESS", "GOVERN", "OPERATE"]
# Earlier versions had three more stages. They are now ways of working inside OPERATE, not stages.
LEGACY_STAGES = {"ASSURE": "OPERATE", "MONITOR": "OPERATE", "REVIEW": "OPERATE"}


def norm_stage(name):
    """A stage name as typed or as stored by an earlier version, in today's names."""
    n = str(name or "").strip().upper()
    return LEGACY_STAGES.get(n, n)


def migrate_info(info):
    """Bring a project record made by an earlier version (six stages) to four stages.
    Only the project record is changed, and only in memory until the next save; the decision journal is never touched."""
    if not info or not isinstance(info.get("stages"), dict):
        return info
    st = info["stages"]
    old = [k for k in ("ASSURE", "MONITOR", "REVIEW") if k in st]
    if not old:
        st.setdefault("OPERATE", {"status": "not_started"})
        return info
    info["legacy_stages"] = {k: st[k] for k in old}
    began = [st[k] for k in old if st[k].get("status") != "not_started"]
    if "OPERATE" not in st:
        if began:
            first = began[0]
            st["OPERATE"] = {"status": "started", "started_seq": first.get("started_seq"), "started": first.get("started"),
                             "covers": ["OPERATE"], "migrated_from": old}
        else:
            st["OPERATE"] = {"status": "not_started"}
    for k in old:
        st.pop(k, None)
    if info.get("current_stage") in LEGACY_STAGES:
        info["current_stage"] = "OPERATE"
    return info
LANES = ["light", "standard", "full"]
SOURCING_MODES = [
    "built-in-house",
    "adapted-from-third-party-base",
    "third-party-service",
    "self-hosted-open-source",
    "embedded-in-vendor-product",
]
TRUST_PROPERTIES = [
    "validity-and-reliability",
    "safety",
    "security-and-resiliency",
    "accountability-and-transparency",
    "explainability-and-interpretability",
    "privacy",
    "fairness",
]
DIMENSIONS = {
    "accuracy": ("Accuracy", 20),
    "fairness": ("Fairness", 20),
    "data": ("Data quality", 15),
    "security": ("Security and misuse", 15),
    "oversight": ("Human oversight", 15),
    "regulatory": ("Regulatory and governance", 15),
}
CONTROL_STATES = [
    "drafted", "approved", "assigned", "implementing", "evidenced",
    "verified", "monitored", "rejected", "waived", "retired", "expired",
]
CREDIT_STATES = ("verified", "monitored")
SEVERITIES = ["low", "medium", "high", "critical"]
FLAGS = [
    "generative", "personal_data", "sensitive_data", "decisions_about_people",
    "safety_impact", "eu_high_risk", "regulated_sector",
    "customer_facing_automated",
]
ESCALATOR_FLAGS = [
    "decisions_about_people", "sensitive_data", "personal_data", "eu_high_risk",
    "safety_impact", "customer_facing_automated", "regulated_sector",
]
TOOL = "tool"


# ---------------------------------------------------------------- time ----
def now():
    # The clock can be overridden only in test runs (AIGRCELER_TEST=1), never in normal use.
    v = os.environ.get("AIGRCELER_NOW")
    if v and os.environ.get("AIGRCELER_TEST") == "1":
        return parse_dt(v)
    return datetime.datetime.now().astimezone()


def clip(text, n=200):
    """Shorten text for a one-line record without cutting a word in half. Adds an ellipsis only when something was cut."""
    t = " ".join(str(text or "").split())
    if len(t) <= n:
        return t
    cut = t[:n].rsplit(" ", 1)[0].rstrip(",;:.-") if " " in t[:n] else t[:n]
    return cut + "\u2026"


def iso(dt=None):
    return (dt or now()).isoformat(timespec="seconds")


def parse_dt(s):
    dt = datetime.datetime.fromisoformat(str(s))
    if dt.tzinfo is None:
        dt = dt.astimezone()
    return dt


def today():
    return now().date().isoformat()


def parse_date(value, what="date"):
    """Validate YYYY-MM-DD and return it normalised. Dates compare as strings, so they must be zero-padded."""
    if value is None or value == "":
        return None
    try:
        return datetime.date.fromisoformat(str(value).strip()).isoformat()
    except ValueError:
        raise AigError("The %s '%s' is not a valid date. Write it as YYYY-MM-DD, for example 2026-12-31." % (what, value))


DUE_DAYS = {"critical": 14, "launch_required": 21, "other": 60}


def default_due_date(defn, start=None):
    """When a control's proof is due if nobody sets a date: sooner for the controls that matter most."""
    kind = "critical" if defn.get("critical") else "launch_required" if defn.get("launch_required") else "other"
    base = datetime.date.fromisoformat(start) if start else datetime.date.today()
    return (base + datetime.timedelta(days=DUE_DAYS[kind])).isoformat()


def finite(value, what="value"):
    import math
    if value is None or isinstance(value, bool) or not math.isfinite(float(value)):
        raise AigError("The %s must be an ordinary number." % what)
    return float(value)


def evidence_usable(ev, info, on=None):
    """Is this evidence still good for credit today? (accepted, not past its date, same model version)"""
    on = on or today()
    if ev.get("status") != "accepted" or not ev.get("strength"):
        return False
    if ev["valid_until"] < on:
        return False
    if ev.get("model_version") and info.get("model_version") and ev["model_version"] != info["model_version"]:
        return False
    return True


def add_days(dt, days):
    return dt + datetime.timedelta(days=days)


def add_business_days(dt, n):
    d = dt
    while n > 0:
        d = d + datetime.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d


# ------------------------------------------------------------- helpers ----
RESERVED = {"con", "prn", "aux", "nul", "clock$"} | {"com%d" % i for i in range(1, 10)} | {"lpt%d" % i for i in range(1, 10)}


def slug(text):
    s = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")
    s = s or "item"
    if s in RESERVED:
        s += "-x"  # Windows reserves these folder names
    return s


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def canon(obj):
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with open(p, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path, obj):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
        f.write("\n")
    os.replace(tmp, p)


def write_text(path, text):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    os.replace(tmp, p)


def read_text(path, default=""):
    p = Path(path)
    if not p.exists():
        return default
    return read_any_text(p)


def read_any_text(path):
    """Read a text file the way Windows tools write it: UTF-8, UTF-8 with BOM, or UTF-16."""
    p = Path(path)
    if p.is_dir():
        raise AigError("'%s' is a folder, not a file." % p)
    raw = p.read_bytes()
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        try:
            return raw.decode("utf-16")
        except UnicodeDecodeError:
            raise AigError("'%s' is not a text file the tool can read (it is binary or in an unknown encoding)." % p.name)
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise AigError("'%s' is not a text file the tool can read (it is binary or in an unknown encoding)." % p.name)


def check_file(path, what="file"):
    p = Path(str(path))
    if not p.exists():
        raise AigError("The %s was not found: %s" % (what, path))
    if not p.is_file():
        raise AigError("'%s' is a folder. Give the %s itself." % (path, what))
    return p


def split_list(value):
    if value is None:
        return []
    if isinstance(value, list):
        return value
    sep = ";" if ";" in str(value) else ","
    return [x.strip() for x in str(value).split(sep) if x.strip()]


def domain_of(control_id):
    return str(control_id).split("-")[0]


# ----------------------------------------------------------- workspace ----
class WS:
    """A company workspace folder."""

    def __init__(self, root):
        self.root = Path(root).resolve()

    @staticmethod
    def find(explicit=None):
        cands = []
        if explicit:
            cands.append(Path(explicit))
        env = os.environ.get("AIGRCELER_WS")
        if env:
            cands.append(Path(env))
        cur = Path.cwd().resolve()
        cands.extend([cur] + list(cur.parents))
        if explicit:
            if (Path(explicit) / "data" / "workspace.json").exists():
                return WS(explicit)
            raise AigError("'%s' is not an AIGRCeler workspace (no workspace record there)." % explicit)
        for c in cands:
            if (c / "data" / "workspace.json").exists():
                return WS(c)
        raise AigError(
            "No AIGRCeler workspace found here. Run the setup first, or point to the "
            "workspace folder with --ws."
        )

    # paths
    def p(self, *parts):
        return self.root.joinpath(*parts)

    def exists(self):
        return (self.root / "data" / "workspace.json").exists()

    def load(self, name, default=None):
        return read_json(self.p("data", name + ".json"), default)

    def save(self, name, obj):
        write_json(self.p("data", name + ".json"), obj)

    def settings(self):
        s = self.load("workspace")
        if s is None:
            raise AigError("This folder is not an AIGRCeler workspace yet (no workspace record).")
        return s

    def next_id(self, kind, prefix, width=3):
        c = self.load("counters", {})
        c[kind] = c.get(kind, 0) + 1
        self.save("counters", c)
        return "%s-%0*d" % (prefix, width, c[kind])

    def journal(self):
        return Journal(self.p("decisions"), "workspace", self.p("data", "journal-head.json"))

    def project_slugs(self):
        d = self.p("projects")
        if not d.exists():
            return []
        # folders starting with "_" or "." are archives (set aside by hand) and are not live AI systems
        return sorted(x.name for x in d.iterdir() if not x.name.startswith(("_", ".")) and (x / "data" / "project.json").exists())

    def project(self, slug_):
        if not slug_:
            raise AigError("Say which AI system this is about (--project).")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", str(slug_)):
            raise AigError("'%s' is not an AI system name used in this workspace." % slug_)
        pr = Project(self, slug_)
        if not pr.exists():
            raise AigError("No AI system called '%s' in this workspace. Known: %s" % (
                slug_, ", ".join(self.project_slugs()) or "none yet"))
        return pr


class Project:
    def __init__(self, ws, slug_):
        self.ws = ws
        self.slug = slug_
        self.root = ws.p("projects", slug_)

    def p(self, *parts):
        return self.root.joinpath(*parts)

    def exists(self):
        return (self.root / "data" / "project.json").exists()

    def load(self, name, default=None):
        return read_json(self.p("data", name + ".json"), default)

    def save(self, name, obj):
        write_json(self.p("data", name + ".json"), obj)

    def info(self):
        return migrate_info(self.load("project"))

    def save_info(self, info):
        self.save("project", info)

    def next_id(self, kind, prefix, width=3):
        c = self.load("counters", {})
        c[kind] = c.get(kind, 0) + 1
        self.save("counters", c)
        return "%s-%0*d" % (prefix, width, c[kind])

    def journal(self):
        return Journal(self.p("decisions"), "project:" + self.slug, self.p("data", "journal-head.json"))

    # controls: one file each under controls/<domain>/<ID>.json
    def control_path(self, cid):
        if not re.fullmatch(r"[A-Z]{2}-[0-9]{2,3}", str(cid)):
            raise AigError("'%s' is not a control ID (they look like GO-01 or DG-12)." % cid)
        dom = DOMAINS.get(domain_of(cid), "other")
        return self.p("controls", dom, cid + ".json")

    def get_control(self, cid):
        c = read_json(self.control_path(cid))
        if c is None:
            raise AigError("This AI system has no control %s." % cid)
        return c

    def has_control(self, cid):
        return self.control_path(cid).exists()

    def save_control(self, c):
        write_json(self.control_path(c["id"]), c)

    def all_controls(self):
        out = []
        base = self.p("controls")
        if base.exists():
            for f in sorted(base.glob("*/*.json")):
                out.append(read_json(f))
        return out


# -------------------------------------------------------------- journal ----
class Journal:
    """One line per decision. Append-only. Each line carries the hash of the
    line before it, so an edited or removed line breaks the chain."""

    def __init__(self, directory, scope, head_path=None):
        self.dir = Path(directory)
        self.file = self.dir / "journal.jsonl"
        self.scope = scope
        self.head_path = Path(head_path) if head_path else None

    def lines(self):
        if not self.file.exists():
            return []
        out = []
        with open(self.file, "r", encoding="utf-8") as f:
            for raw in f:
                raw = raw.strip()
                if raw:
                    out.append(json.loads(raw))
        return out

    def last(self):
        ls = self.lines()
        return ls[-1] if ls else None

    def append(self, type_, subject, decided_by, summary, authority_basis="",
               labels=None, text=None, extra=None):
        ls = self.lines()
        seq = len(ls) + 1
        prev = ls[-1]["hash"] if ls else "0" * 64
        entry = {
            "seq": seq,
            "time": iso(),
            "type": type_,
            "scope": self.scope,
            "subject": list(subject or []),
            "decided_by": decided_by,
            "authority_basis": authority_basis or "",
            "summary": summary,
            "labels": list(labels or []),
        }
        if extra:
            entry["extra"] = extra
        if text:
            rel = "texts/%04d.md" % seq
            write_text(self.dir / rel, text if text.endswith("\n") else text + "\n")
            entry["text_ref"] = {"path": rel, "sha256": sha256_file(self.dir / rel)}
        entry["prev_hash"] = prev
        entry["hash"] = sha256_text(canon(entry))
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(self.file, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        if self.head_path:
            write_json(self.head_path, {"seq": seq, "hash": entry["hash"], "time": entry["time"]})
        return entry

    def verify(self):
        """Return a list of problems in plain words (empty list = intact)."""
        problems = []
        prev = "0" * 64
        ls = self.lines()
        for i, e in enumerate(ls, 1):
            if e.get("seq") != i:
                problems.append("Line %d is numbered %s: a line was removed, added or reordered." % (i, e.get("seq")))
            if e.get("prev_hash") != prev:
                problems.append("Line %d does not follow from line %d: the chain is broken here." % (i, i - 1))
            body = {k: v for k, v in e.items() if k != "hash"}
            if sha256_text(canon(body)) != e.get("hash"):
                problems.append("Line %d was edited after it was written (its fingerprint no longer matches)." % i)
            ref = e.get("text_ref")
            if ref:
                tp = self.dir / ref["path"]
                if not tp.exists():
                    problems.append("Line %d points to a decision text that is missing (%s)." % (i, ref["path"]))
                elif sha256_file(tp) != ref["sha256"]:
                    problems.append("The decision text for line %d was changed after it was written." % i)
            prev = e.get("hash", "")
        if self.head_path and self.head_path.exists():
            head = read_json(self.head_path)
            last = ls[-1] if ls else None
            if (last["seq"] if last else 0) < head["seq"]:
                problems.append("The journal ends at line %d but the last recorded line was %d: lines were removed from the end." % (last["seq"] if last else 0, head["seq"]))
            elif last and last["seq"] == head["seq"] and last["hash"] != head["hash"]:
                problems.append("The last line does not match the recorded head: the journal was rewritten.")
        elif ls and self.head_path:
            problems.append("The journal has lines but its head record is missing.")
        return problems

    def render_table(self):
        rows = ["| # | When | What | Decided by | Basis | Labels |", "|---|---|---|---|---|---|"]
        for e in self.lines():
            rows.append("| %d | %s | %s | %s | %s | %s |" % (
                e["seq"], e["time"][:16].replace("T", " "),
                e["summary"].replace("|", "/"), e["decided_by"],
                (e.get("authority_basis") or "").replace("|", "/"),
                ", ".join(e.get("labels", []))))
        return "\n".join(rows) + "\n"


# ------------------------------------------------------------ authority ----
GOV_CAPS = [
    "approve_controls", "approve_catalog", "start_stages", "decide_lane",
    "overrule_findings", "lift_block", "adopt_statement", "grant_exception",
    "waive_controls", "manage_roles", "close_stages", "accept_risk", "close_incidents", "verify_evidence",
]


class Actor:
    def __init__(self, person, name, roles, caps, basis, is_tool=False):
        self.person = person
        self.name = name
        self.roles = roles
        self.caps = caps
        self.basis = basis
        self.is_tool = is_tool

    @property
    def decided_by(self):
        return "tool:aigrceler" if self.is_tool else "%s:%s" % (
            self.roles[0] if self.roles else "person", self.person)

    def has_role(self, role_id):
        return role_id in self.roles


def active_assignments(ws, person=None, on=None):
    on = on or today()
    out = []
    for a in ws.load("assignments", []):
        if person and a["person"] != person:
            continue
        if a.get("revoked") and a["revoked"] <= iso():
            continue
        if a.get("from") and a["from"] > on:
            continue
        if a.get("to") and a["to"] < on:
            continue
        out.append(a)
    return out


def resolve_actor(ws, by):
    if not by or by == TOOL:
        return Actor(TOOL, "AIGRCeler", [], [], "", is_tool=True)
    people = {p["id"]: p for p in ws.load("people", [])}
    if by not in people:
        raise AigError("'%s' is not in the people directory. Add the person first." % by)
    roles_def = {r["id"]: r for r in ws.load("roles", [])}
    asg = active_assignments(ws, by)
    roles = [a["role"] for a in asg]
    caps = []
    for r in roles:
        caps.extend(roles_def.get(r, {}).get("caps", []))
    basis = "; ".join("%s (%s)" % (roles_def.get(a["role"], {}).get("name", a["role"]), a.get("basis", "no basis recorded")) for a in asg)
    return Actor(by, people[by]["name"], roles, sorted(set(caps)), basis)


def require(ws, by, cap, what):
    a = resolve_actor(ws, by)
    if a.is_tool:
        raise AigError(
            "%s needs a decision by a named person in the AI Governance role. AIGRCeler may "
            "prepare it but cannot make it. Ask AI Governance, then repeat with --by <their name>." % what)
    if cap not in a.caps:
        raise AigError("%s is not allowed for %s (roles: %s). It needs a person whose role carries '%s'." % (
            what, a.name, ", ".join(a.roles) or "none", cap))
    return a


def need_text(args, flag, what):
    v = getattr(args, flag, None)
    if not v or not str(v).strip():
        raise AigError("%s needs the decision-maker's own words (--%s). Do not write it for them." % (what, flag.replace("_", "-")))
    p = Path(str(v))
    try:
        if len(str(v)) < 240 and p.exists() and p.is_file():
            return read_any_text(p).strip()
    except (OSError, ValueError):
        pass
    return str(v)


def governance_role_ids(ws):
    return [r["id"] for r in ws.load("roles", []) if r.get("governance")]


def is_governance_person(ws, person):
    gov = set(governance_role_ids(ws))
    return any(a["role"] in gov for a in active_assignments(ws, person))
