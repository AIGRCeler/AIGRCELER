"""AIGRCeler v2 engine self-test.  py -3 selftest.py
Builds a throw-away demo company in a temp folder, drives the engine through a full
lifecycle (including a red-teaming case) and checks the rules that matter:
authority, hard stop, evidence strength, expiry, risk credit, journal chain.
Nothing is written outside the temp folder."""
import io, os, re, sys, tempfile, shutil, contextlib, json
os.environ["AIGRCELER_NO_DASHBOARD"] = "1"   # the dashboard has its own tests below; leave it off elsewhere for speed
os.environ["AIGRCELER_TEST"] = "1"   # lets the tests move the clock; the clock cannot be moved in normal use
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "engine"))
from aig.cli import main

TMP = tempfile.mkdtemp(prefix="aigrceler-selftest-")
WS = os.path.join(TMP, "acme")
os.makedirs(WS)
RESULTS = []

def run(*argv, ws=True, expect=0):
    argv = list(argv) + (["--ws", WS] if ws else [])
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            rc = main(argv)
        except SystemExit as e:
            rc = e.code if isinstance(e.code, int) else 2
    text = out.getvalue() + err.getvalue()
    if expect is not None and rc != expect:
        print(text)
        raise AssertionError("%s -> exit %s, expected %s" % (" ".join(argv[:4]), rc, expect))
    return text

def check(name, cond):
    RESULTS.append((name, bool(cond)))
    print(("PASS  " if cond else "FAIL  ") + name)

def P(*a, **k):
    return run(*(list(a) + ["-p", "triage-bot"]), **k)

def fill(slug, skip=()):
    """Answer every open required discovery question with a plain, consistent test answer (as a person would after being asked)."""
    from aig import profmod
    from aig.core import WS as WSC
    w = WSC(WS)
    for _ in range(5):
        pr_ = w.project(slug)
        info_ = pr_.info()
        st_ = profmod.state(w, pr_, info_)
        ans_ = {}
        for r in st_["rows"]:
            fd = r["def"]
            if not r["required"] or r["status"] not in ("open", "inferred") or fd["id"] in skip:
                continue
            k = fd["kind"]
            if fd["id"] == "model_version":
                v = info_.get("model_version") or "v1"
            elif k == "text":
                v = "Test answer: %s." % fd["label"]
            elif k == "list":
                v = "item one; item two"
            elif k == "yesno":
                flag = profmod.FLAG_ON.get(fd["id"], (None, None))[1]
                on = bool(info_["flags"].get(flag)) if flag else (bool(info_.get("consequential_actions")) if fd["id"] == "consequential_actions" else False)
                v = "yes, as recorded" if on else "no"
            else:
                sc_ = info_.get("screening") or {}
                key = profmod.SCREEN_FIELDS.get(fd["id"])
                if fd["id"] == "sourcing_mode":
                    v = info_.get("sourcing_mode") or fd["choices"][0]
                elif key and sc_.get(key):
                    v = sc_[key]
                elif fd["id"] == "eu_nexus":
                    v = "no"
                elif fd["id"] == "lifecycle_stage":
                    v = "in-use"
                else:
                    v = fd["choices"][0]
            ans_[fd["id"]] = v
        if not ans_:
            return
        path_ = os.path.join(TMP, "answers-%s.json" % slug)
        json.dump(ans_, open(path_, "w", encoding="utf-8"))
        run("profile", "set", "--file", path_, "--source", "selftest: answered by the people asked", "-p", slug)


try:
    run_args = ["ws", "init", "--company", "Acme Dental", "--governance-name", "Dana Lee", "--basis", "Charter section 3", "--ws", WS]
    main(run_args)
    for nm, role in [("Sam Ortiz", "engineering-data-science"), ("Priya Rao", "security"), ("Tom Wu", "operations"),
                     ("Lena Fox", "legal-compliance"), ("Max Ho", "executive-leadership")]:
        run("person", "add", "--name", nm)
        run("role", "assign", "--person", nm.lower().replace(" ", "-"), "--role", role, "--by", "dana-lee")
    t = run("catalog", "adopt-starter", expect=2)
    check("the tool cannot adopt the catalog; a named AI Governance person must", "named person" in t)
    run("catalog", "adopt-starter", "--by", "dana-lee", "--statement", "I adopt the starter catalog as Acme's own.")
    run("project", "create", "--name", "Triage Bot", "--purpose", "Answers patient questions", "--sourcing-mode", "third-party-service", "--model-version", "v1")
    P("project", "set", "--flags-on", "generative,personal_data,customer_facing_automated", "--downstream-dependencies", "a,b")
    P("views", "regenerate")
    w0 = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("a registered but unscreened system shows 'discovery has not been done' as waiting work", "Discovery has not been done" in w0)
    t = P("project", "screen", "--users", "many", "--autonomy", "automated", "--data", "personal", "--impact", "business")
    check("screening suggests the full lane for a customer-facing generative system", "full" in t)
    check("the screening output shows all three lanes in plain words, with light marked not available",
          all(w in t for w in ("Light:", "Standard:", "Full:")) and "NOT AVAILABLE" in t)
    check("the lane options can be shown again on request", "Lane options" in P("project", "lane-options"))
    P("views", "regenerate")
    waiting = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("what-is-waiting shows the undecided lane with its options at the top of the AI Governance list",
          "Choose the lane" in waiting and "Light:" in waiting and "Full:" in waiting)
    t = P("project", "lane-set", "--lane", "light", "--by", "dana-lee", "--statement", "x", expect=2)
    check("light lane refused when escalators exist", "not available" in t)
    check("the refusal names the nearest allowed lane", "nearest lane that is allowed" in t)
    P("project", "lane-set", "--lane", "full", "--by", "dana-lee", "--statement", "Full lane confirmed.")
    P("views", "regenerate")
    waiting = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("once the lane is decided, what-is-waiting asks AI Governance to start Discover and no longer asks for the lane",
          "Start the Discover stage" in waiting and "Choose the lane" not in waiting)
    run("project", "create", "--name", "Override Bot", "--purpose", "Override probe", "--sourcing-mode", "third-party-service")
    Z = lambda *a, **k: run(*(list(a) + ["-p", "override-bot"]), **k)
    Z("project", "screen", "--users", "few", "--autonomy", "reviewed", "--data", "none", "--impact", "minor")
    Z("project", "lane-set", "--lane", "standard", "--by", "dana-lee", "--statement", "Standard lane for the probe.")
    Z("stage", "start", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "I start DISCOVER.")
    t = Z("stage", "close", "--stage", "DISCOVER", "--by", "dana-lee", "--force-with-reason", "it is only a test", expect=2)
    check("closing over open items on a one-line reason is refused, and the items are listed",
          "These items would stay open" in t and "Still to find out" in t and "not enough" in t)
    Z("stage", "close", "--stage", "DISCOVER", "--by", "dana-lee",
      "--force-with-reason", "I accept that who uses it and what data it uses are still unknown, because this is a throwaway probe that touches no real data or people.")
    Z("views", "regenerate")
    waiting = open(os.path.join(WS, "projects", "override-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("a stage closed over open items stays visible under needs attention until the items are dealt with",
          "was closed by AI Governance with items still open" in waiting)
    run("project", "create", "--name", "Probe Bot", "--purpose", "Probe", "--sourcing-mode", "third-party-service")
    X = lambda *a, **k: run(*(list(a) + ["-p", "probe-bot"]), **k)
    X("project", "screen", "--users", "many", "--autonomy", "automated", "--data", "personal", "--impact", "business")
    X("project", "lane-set", "--lane", "full", "--by", "dana-lee", "--statement", "Full.")
    X("stage", "block", "--reason", "legal gap seed")
    X("containment", "add", "--title", "Pause the bot at night", "--ends", "2027-01-01", "--by", "dana-lee", "--statement", "I decide this pause.")
    X("request", "create", "--to", "tom-wu", "--type", "containment", "--subject", "Please pause", "--text", "Please pause it.")
    X("views", "regenerate")
    waiting = open(os.path.join(WS, "projects", "probe-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("what-is-waiting states the decided lane, the block and the temporary measure as settled",
          "Lane: **full**" in waiting and "Stage block in force" in waiting and "Temporary measure decided, until 2027-01-01" in waiting and "not yet confirmed in place" in waiting
          and "a request to act" in waiting and "0 item(s)" not in waiting and "Choose the lane" not in waiting)
    t = X("containment", "confirm", "--id", "CT-001", "--source", "guess", expect=2)
    check("a containment cannot be confirmed in place without saying who reported it", "who told you" in t)
    X("containment", "confirm", "--id", "CT-001", "--source", "Tom Wu, reply to the request")
    X("views", "regenerate")
    waiting = open(os.path.join(WS, "projects", "probe-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("once the owner reports it, the temporary measure shows as in force with who said so and that it was not checked",
          "Temporary measure in force until 2027-01-01 (reported in place by Tom Wu, reply to the request; not checked)" in waiting)
    t = P("stage", "start", "--stage", "DISCOVER", "--statement", "go", expect=2)
    check("the tool cannot start a stage", "named person" in t)
    t = P("stage", "start", "--stage", "ASSESS", "--by", "dana-lee", "--statement", "go", expect=2)
    check("hard stop: ASSESS cannot start before DISCOVER closes", "must close" in t)
    P("stage", "start", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "I start DISCOVER.")
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("DISCOVER cannot close on registration alone: it lists what is still to find out",
          "Still to find out" in t and "what data it uses" in t)
    P("project", "set", "--users", "Patients and front-desk staff", "--data-sources", "Appointment records", "--jurisdictions", "US")
    P("request", "create", "--to", "tom-wu", "--type", "discovery_question", "--subject", "How is Triage Bot checked?",
      "--text", "How does your team check that Triage Bot answers well?")
    P("project", "set", "--eval-metrics", "unknown,asked of engineering")
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("a placeholder such as 'unknown' or 'asked of ...' does not count as an answer", "how anyone checks" in t)
    P("project", "set", "--eval-metrics", "")
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("an unanswered discovery question holds DISCOVER open",
          "discovery question" in t and "Tom Wu" in t and "how anyone checks" in t)
    rid = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))[-1]["id"]
    P("request", "answer", "--id", rid, "--by", "dana-lee", "--text", "A weekly sample of 50 answers is read by the front-desk lead.")
    P("project", "set", "--eval-metrics", "weekly sample of 50 answers read by the front-desk lead")
    P("project", "set", "--human-review", "Front-desk lead reads a weekly sample; any answer can be overruled by staff, about twice a month")
    P("views", "regenerate")
    disc = open(os.path.join(WS, "projects", "triage-bot", "00-status", "discovery-record.md"), encoding="utf-8").read()
    check("'whether a person can overrule it, and how often' can be recorded from the command line",
          "overruled by staff" in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "project.json"), encoding="utf-8"))["human_review"]
          and "overruled by staff" in disc)
    check("the discovery record shows what is known and the questions sent to people",
          "Patients and front-desk staff" in disc and "Questions sent to people" in disc and "Tom Wu" in disc)
    # discovery gaps include what depends on it
    P("project", "set", "--downstream-dependencies", "weekly billing report; scheduling")
    # lists split on semicolons so a sentence with commas stays one item
    from aig.core import split_list
    check("a list item with commas inside stays one item when separated by semicolons",
          split_list("score, not the reason; second item") == ["score, not the reason", "second item"]
          and split_list("a,b") == ["a", "b"])
    # follow-ups, due dates, greetings
    P("request", "create", "--to", "tom-wu", "--type", "discovery_question", "--subject", "Who else reads Triage Bot output?",
      "--text", "Hello Tom, which reports or systems read what Triage Bot produces, and what do they do with it?")
    rq = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))[-1]
    import datetime
    check("a request with no date gets a default reply date on a weekday",
          rq["due"] and datetime.date.fromisoformat(rq["due"]).weekday() < 5)
    body = open(os.path.join(WS, "projects", "triage-bot", rq["message_file"]), encoding="utf-8").read()
    check("a greeting written into the text is not doubled", body.lower().count("hello") == 1 and "Which reports" in body)
    P("request", "set-due", "--id", rq["id"], "--due", "2031-01-15")
    check("a due date can be changed on an open request without sending a second request",
          [r for r in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8")) if r["id"] == rq["id"]][0]["due"] == "2031-01-15")
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("the new open question holds DISCOVER open", "discovery question" in t and "Tom Wu" in t)
    P("request", "answer", "--id", rq["id"], "--by", "dana-lee", "--text", "The billing report reads it.",
      "--remaining", "Does the scheduling system use it as well?")
    allr = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))
    fol = allr[-1]
    check("a partly answered request leaves a follow-up for what is missing",
          fol["status"] == "open" and fol["to"] == "tom-wu" and fol["id"] != rq["id"]
          and [r for r in allr if r["id"] == rq["id"]][0].get("follow_up") == fol["id"])
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("the follow-up keeps DISCOVER open", "discovery question" in t)
    flw = open(os.path.join(WS, "projects", "triage-bot", fol["message_file"]), encoding="utf-8").readline()
    check("a follow-up is titled from the real title of the question, once ('Still open: ...')",
          flw.startswith("# Still open: Who else reads Triage Bot output?") and flw.lower().count("still open") == 1)
    P("request", "answer", "--id", fol["id"], "--by", "dana-lee", "--text", "No, scheduling does not use it.",
      "--remaining", "Which other reports?")
    f2 = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))[-1]
    check("a second follow-up does not stack the title",
          open(os.path.join(WS, "projects", "triage-bot", f2["message_file"]), encoding="utf-8").readline().lower().count("still open") == 1)
    P("request", "answer", "--id", f2["id"], "--by", "dana-lee", "--text", "None.")
    _rq = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))
    P("request", "create", "--to", "tom-wu", "--type", "discovery_question", "--subject", "Junk reply check", "--text", "Please confirm one more thing.")
    _jid = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))[-1]["id"]
    _jt = P("request", "answer", "--id", _jid, "--by", "dana-lee", "--text", "x", expect=2)
    check("a one-letter or placeholder reply is refused and nothing is recorded", "not a real reply" in _jt and
          [r for r in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8")) if r["id"] == _jid][0]["status"] == "open")
    P("request", "withdraw", "--id", _jid, "--reason", "It was only a check of the refusal.")
    P("request", "create", "--to", "tom-wu", "--type", "discovery_question", "--subject", "Needless check", "--text", "Please confirm something that does not matter.")
    wid = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))[-1]["id"]
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("an open question holds the stage until it is answered or withdrawn", "Tom Wu" in t)
    P("request", "withdraw", "--id", wid, "--reason", "It was not needed to describe the system.")
    wr = [r for r in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8")) if r["id"] == wid][0]
    check("a withdrawn request keeps its reason and no longer holds the stage",
          wr["status"] == "withdrawn" and wr["withdrawn_reason"].startswith("It was not needed"))
    _wp = os.path.join(WS, "projects", "triage-bot", wr["message_file"])
    check("a withdrawn message that was never sent is moved out of the person's folder into 'withdrawn'",
          "withdrawn" in wr["message_file"].replace("\\", "/").split("/") and os.path.exists(_wp))
    t = P("request", "create", "--to", "tom-wu", "--type", "discovery", "--subject", "x", "--text", "y", expect=2)
    check("an unknown request type is refused with the list of types", "must be one of" in t and "discovery_question" in t)
    run("person", "add", "--name", "Vera Vendor", "--type", "external")
    P("request", "create", "--to", "tom-wu", "--type", "discovery_question", "--subject", "How was the model trained?", "--text", "How was it trained and tested?")
    rq3 = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))[-1]
    P("request", "answer", "--id", rq3["id"], "--by", "dana-lee", "--text", "I do not know; Vera Vendor does.",
      "--remaining", "How was the model trained and tested?", "--remaining-to", "vera-vendor")
    allr3 = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8"))
    check("a question can be passed on to the person who knows, and not back to the one who said they do not",
          allr3[-1]["to"] == "vera-vendor" and allr3[-1]["type"] == "discovery_question" and allr3[-1]["status"] == "open"
          and not [r for r in allr3 if r["to"] == "tom-wu" and r["status"] == "open"])
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("the passed-on question keeps DISCOVER open", "Vera Vendor" in t)
    P("request", "answer", "--id", allr3[-1]["id"], "--by", "dana-lee", "--text", "Trained on public data and tested yearly.")
    P("views", "regenerate")
    disc3 = open(os.path.join(WS, "projects", "triage-bot", "00-status", "discovery-record.md"), encoding="utf-8").read()
    check("the discovery record names what each question was about", "How was the model trained?" in disc3 or "how-was-the-model-trained" in disc3.lower())
    # concerns and proposals
    P("concern", "add", "--kind", "concern", "--text", "Postal code may stand in for ethnicity.", "--asked-by", "dana-lee")
    P("concern", "add", "--kind", "proposal", "--text", "Ask Tom Wu to switch the bot off at night.")
    P("views", "regenerate")
    w = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("a proposal waits on the page as proposed by AIGRCeler, and a concern is carried to the next stage on the page",
          "Proposed by AIGRCeler, waiting for your decision" in w and "switch the bot off at night" in w and "Postal code may stand in" in w)
    disc2 = open(os.path.join(WS, "projects", "triage-bot", "00-status", "discovery-record.md"), encoding="utf-8").read()
    check("the discovery record shows what AIGRCeler noticed, labelled as its own reading",
          "its own reading" in disc2 and "Postal code" in disc2)
    t = P("concern", "resolve", "--id", "CON-002", "--note", "Dana declined.", expect=2)
    check("a proposal cannot be closed by the tool: the person decides, in their own words", "named person" in t)
    P("concern", "resolve", "--id", "CON-002", "--note", "Dana declined.", "--by", "dana-lee", "--statement", "No, leave the bot on at night.")
    jl = open(os.path.join(WS, "projects", "triage-bot", "decisions", "journal.jsonl"), encoding="utf-8").read()
    check("the decision on a proposal is in the journal with the person's words", "proposal_decided" in jl)
    P("views", "regenerate")
    w = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("a proposal leaves the page once it is dealt with", "switch the bot off at night" not in w)
    t = P("stage", "close", "--stage", "DISCOVER", expect=2)
    check("a full-lane system cannot leave DISCOVER on the six old facts: the rest of the profile is asked for",
          "Still to find out" in t and "discovery questions" in t)
    fill("triage-bot")
    P("stage", "close", "--stage", "DISCOVER")
    t = P("stage", "start", "--stage", "ASSESS", "--by", "dana-lee", "--statement", "I start ASSESS.")
    check("concerns raised earlier are shown when the stage that must take them up starts",
          "Concerns carried in" in t and "Postal code" in t)
    P("risk", "init"); P("risk", "set", "--all-defaults", "--reason", "standard scenarios fit")
    # Assess does not close over an unresolved concern or over unanswered assessments
    t = P("stage", "close", "--stage", "ASSESS", expect=2)
    check("Assess cannot close while a concern carried into it is not dealt with", "concern(s) carried into Assess are not dealt with" in t and "CON-001" in t)
    check("Assess cannot close while the assessments the system may need are unanswered", "assessments this system may need are not all answered" in t)
    P("views", "regenerate")
    w = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("the waiting page shows what keeps Assess from closing, as AIGRCeler's own work", "AIGRCeler to do before Assess can close" in w and "carried into Assess" in w)
    t = P("concern", "carry", "--id", "CON-001", "--to", "ASSESS", "--reason", "Same stage as it is now so this is refused anyway", expect=2)
    check("a concern can only be carried to a later stage", "later stage" in t)
    t = P("concern", "carry", "--id", "CON-001", "--to", "GOVERN", "--reason", "short", expect=2)
    check("carrying a concern on needs a real reason", "at least five words" in t)
    t = P("concern", "carry", "--id", "CON-001", "--to", "GOVERN", "--reason", "The postal-code proxy needs a control decision, which Govern makes with the owner.")
    check("a concern can be passed on to a later stage with a reason", "moves to Govern" in t)
    t = P("assess", "show")
    check("the assessment list says what fits and what is not answered", "NOT ANSWERED" in t and "data-protection impact" in t.lower())
    t = P("assess", "item", "--item", "dpia", "--status", "not-needed", "--note", "No personal data is processed by this bot at all", expect=2)
    check("saying a rights or data-protection assessment is not needed takes a named person", "named person in AI Governance" in t)
    t = P("assess", "item", "--item", "dpia", "--status", "not-needed", "--note", "No personal data is processed by this bot at all",
          "--by", "dana-lee", "--statement", "I judge a DPIA is not needed; counsel agreed on the call.")
    check("a named person can record that an assessment is not needed, in their own words", "not needed" in t)
    t = P("assess", "item", "--item", "docs", "--status", "planned", "--note", "Vendor documents are collected under the vendor controls in Govern")
    check("a planned assessment names the controls that will carry it", "planned" in t)
    t = P("assess", "item", "--item", "affected", "--status", "done", "--note", "Auditor wrote the affected-people note in working papers")
    check("an assessment can be recorded as done", "done" in t)
    t = P("assess", "item", "--item", "docs", "--status", "planned", "--note", "short", expect=2)
    check("an assessment position needs a real note", "at least five words" in t)
    # a risk the standard list misses can be added, rated, and linked to standard controls
    t = P("risk", "add", "--title", "Night staff cannot reach the bot to switch it off", "--dimension", "oversight", "--likelihood", "3", "--impact", "4",
          "--reason", "Interview facts say only one engineer holds the switch and is off at night.", "--like", "S-HUM-03")
    check("a system-specific risk can be added and rated", "added and rated" in t)
    t = P("risk", "add", "--title", "Night staff cannot reach the bot to switch it off", "--dimension", "oversight", "--likelihood", "3", "--impact", "4",
          "--reason", "Interview facts say only one engineer holds the switch and is off at night.", expect=2)
    check("the same added risk is not added twice", "already on the list" in t)
    t = P("risk", "add", "--title", "Another", "--dimension", "nonsense", "--likelihood", "3", "--impact", "4", "--reason", "A reason of more than five words here", expect=2)
    check("an added risk needs a known dimension", "Say which dimension" in t)
    rid_new = [x for x in __import__("json").load(open(os.path.join(WS, "projects", "triage-bot", "data", "risks.json"), encoding="utf-8")) if x.get("custom")][0]["id"]
    t = P("risk", "set", "--id", rid_new, "--likelihood", "3", "--impact", "4", "--reason", "Same facts as when it was added, now linked to a control.", "--like", "S-HUM-04")
    check("a risk added for this system can be linked to standard controls afterwards", "rated" in t)
    t = P("risk", "set", "--id", "R-001", "--likelihood", "3", "--impact", "3", "--reason", "Trying to link a standard scenario to others.", "--like", "S-HUM-04", expect=2)
    check("linking is refused on a standard scenario", "already has its own" in t)
    t = P("risk", "gaps")
    check("the list of High and Critical risks shows which controls address each", "High" in t or "Critical" in t or "No High or Critical" in t)
    P("views", "regenerate")
    rv = open(os.path.join(WS, "projects", "triage-bot", "00-status", "5-risk.md"), encoding="utf-8").read()
    check("the risk view shows where each assessment stands", "Assessments this system may need" in rv and "Night staff cannot reach" in rv)
    P("stage", "close", "--stage", "ASSESS")
    P("stage", "start", "--stage", "GOVERN", "--by", "dana-lee", "--statement", "I start GOVERN.")
    P("assess", "item", "--item", "fairness", "--status", "planned", "--note", "Fairness testing is planned by the vendor and checked by us", "--control", "MD-04")
    # the company's catalog may be behind what the product ships with: say so, and keep saying so until AI Governance decides
    from aig.catalogmod import defpath as _dp
    from aig.core import WS as _WS
    _w = _WS(WS)
    _gone = _dp(_w, "GO-19")
    _saved = open(_gone, encoding="utf-8").read()
    os.remove(_gone)
    t = P("control", "draft")
    check("drafting says when the company's catalog is missing controls the product now ships with", "does not have 1 control(s)" in t and "GO-19" in t)
    P("views", "regenerate")
    w = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("the waiting page says the catalog is behind", "missing 1 control(s) this product now ships with" in w)
    t = run("catalog", "sync-starter", "--by", "dana-lee", "--statement", "Add the new starter controls to our catalog.")
    check("AI Governance can bring the catalog up to date", "GO-19" in t)
    t = P("control", "draft")
    check("after the update the new control is drafted for the system", "Drafted 1 controls" in t)
    t = P("control", "list", "--domain", "MD")
    check("a red-teaming control is drafted for a customer-facing generative system", "Red-team" in t)
    t = P("control", "owners")
    check("the owners list counts from the records and flags AI Governance members", "control(s) on Triage Bot" in t and "(proposed)" in t)
    t = P("control", "applies", "--ids", "MD-04,TP-05")
    check("the engine says a control is left out on purpose and why, and which control is on the system", "MD-04" in t and "not on this system on purpose" in t and "third-party-service" in t and "TP-05" in t and "on this system, drafted" in t)
    t = P("stage", "gate", "--stage", "GOVERN", expect=None)
    check("a planned assessment whose named control is not on the system holds Govern", "'fairness analysis across groups' is planned" in t and "MD-04" in t and "Controls that would carry it here: TP-05" in t)
    t = P("assess", "item", "--item", "fairness", "--status", "planned", "--note", "Fairness is tested on our own cases under the vendor test control")
    check("planning an assessment names the controls that apply to this system, not a fixed list", "Carried by" in t and "MD-04" not in t)
    t = P("control", "approve", "--all-drafted", "--by", "tom-wu", "--statement", "x", expect=2)
    check("someone without the AI Governance role cannot approve controls", "not allowed" in t)
    P("control", "approve", "--all-drafted", "--by", "dana-lee", "--statement", "Approved after reading the list.")
    t = P("control", "assign", "--role", "security", "--owner", "dana-lee", "--due", "2026-12-01", expect=2)
    check("AI Governance cannot be made owner of a control", "never implements" in t)
    for role, who in [("security", "priya-rao"), ("engineering-data-science", "sam-ortiz"), ("operations", "tom-wu"),
                      ("legal-compliance", "lena-fox"), ("executive-leadership", "max-ho")]:
        P("control", "assign", "--role", role, "--owner", who, "--due", "2026-12-01")
    # move one control to someone else after assignment: the old message is withdrawn and one new message covers what stays
    from aig.core import WS as _W2
    _w2 = _W2(WS)
    _pr2 = _w2.project("triage-bot")
    _mv = [c for c in _pr2.all_controls() if c.get("owner") == "tom-wu"][0]["id"]
    _n_before = len([c for c in _pr2.all_controls() if c.get("owner") == "tom-wu"])
    t = P("control", "assign", "--ids", _mv, "--role", "operations", "--owner", "priya-rao", "--due", "2026-12-01")
    check("moving one assigned control gives its new owner one message and withdraws the old one", "earlier message" in t and "withdrawn" in t and "one new message" in t)
    _pr2 = _w2.project("triage-bot")
    check("only the chosen control moved", [c["owner"] for c in _pr2.all_controls() if c["id"] == _mv] == ["priya-rao"]
          and len([c for c in _pr2.all_controls() if c.get("owner") == "tom-wu"]) == _n_before - 1)
    _reqs = _pr2.load("requests", [])
    check("the old message was moved out of the person's folder and the request is withdrawn",
          any(r["status"] == "withdrawn" and "withdrawn" in r["message_file"] for r in _reqs))
    _open = next(r for r in _reqs if r["status"] == "open" and r["controls"] and not r.get("delivered"))
    P("request", "set-due", "--id", _open["id"], "--due", "2031-02-02")
    check("a due date changed before the message is sent is written into the message too",
          "2031-02-02" in open(os.path.join(WS, "projects", "triage-bot", _open["message_file"]), encoding="utf-8").read())
    t = P("control", "mark-sent", "--id", _open["id"], "--note", "sent", expect=2)
    check("AIGRCeler cannot mark a message as sent on its own", "only when a person says" in t)
    P("control", "mark-sent", "--id", _open["id"], "--by", "dana-lee", "--note", "Dana told me she emailed it.")
    check("a person can say a message was sent, and who said so is recorded",
          [r for r in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8")) if r["id"] == _open["id"]][0]["delivered"]["by"] == "dana-lee")
    t = P("control", "unmark-sent", "--id", _open["id"], "--note", "Dana had not sent it after all.")
    check("a wrong 'sent' mark can be taken back and the old mark is kept",
          "no longer marked" in t and [r for r in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "requests.json"), encoding="utf-8")) if r["id"] == _open["id"]][0]["delivered_history"])
    t = P("control", "assign", "--ids", _mv, "--role", "security", "--owner", "tom-wu", "--due", "2026-12-01", expect=2)
    check("--ids with --role refuses a control that belongs to another role", "belongs to role" in t)
    P("control", "assign", "--ids", _mv, "--owner", "tom-wu", "--due", "2026-12-01")
    t = P("stage", "close", "--stage", "GOVERN", expect=2)
    check("a concern carried into Govern holds Govern from closing until it is settled", "carried into Govern are not dealt with yet: CON-001" in t)
    P("concern", "carry", "--id", "CON-001", "--to", "OPERATE", "--reason", "The evidence is gathered during Operate, not now.")
    P("stage", "close", "--stage", "GOVERN")
    P("views", "regenerate")
    w = open(os.path.join(WS, "projects", "triage-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("the waiting page says whether each message is marked as sent", "not marked as sent yet" in w)
    t = P("request", "list")
    check("the request list says what each request is about and whether it is marked sent", "not marked sent" in t and " | " in t)
    P("stage", "start", "--stage", "OPERATE", "--by", "dana-lee", "--statement", "I start OPERATE.")
    before = P("risk", "show")
    open(os.path.join(TMP, "garak.json"), "w").write(json.dumps({"tool": "garak", "failures": 2}))
    P("evidence", "intake", "--control", "MD-07", "--file", os.path.join(TMP, "garak.json"), "--kind", "report", "--tool", "garak", "--model-version", "v1", "--submitted-by", "priya-rao")
    t = P("finding", "record", "--evidence", "EV-001", "--verdict", "satisfied", "--reasons", "ok", "--by", "priya-rao", expect=2)
    check("a person without the authority to verify cannot record a finding", "authority to verify" in t)
    P("finding", "record", "--evidence", "EV-001", "--verdict", "satisfied", "--reasons", "Scope, attacks and fixes documented.")
    after = P("risk", "show")
    check("verified red-team control with strong evidence lowers residual risk", before.splitlines()[-1] != after.splitlines()[-1])
    P("evidence", "intake", "--control", "DO-04", "--text", "We reviewed access.", "--kind", "statement", "--submitted-by", "priya-rao")
    t = P("finding", "record", "--evidence", "EV-002", "--verdict", "satisfied", "--reasons", "statement only", expect=2)
    check("the tool alone cannot verify a statement", "named reviewer" in t)
    t = P("finding", "record", "--evidence", "EV-002", "--verdict", "satisfied", "--reasons", "statement only", "--by", "dana-lee", "--statement", "I read it and I accept it.")
    check("a statement alone cannot verify a control", "stays at 'evidenced'" in t and "DO-04 is now evidenced" in t)
    t = P("project", "set", "--model-version", "Reported today: the vendor moved us to a new version, nothing else is known.", expect=2)
    check("a sentence is refused as the model version (reports are matched against it word for word)", "version name only" in t)
    t = P("profile", "set", "--field", "model_version", "--value", "Reported today: the vendor moved us to v3, nothing else is known.", "--source", "Dana Lee", expect=2)
    check("the same refusal applies when the version is given as a discovery answer", "version name only" in t)
    P("project", "set", "--model-version", "v2")
    t = P("control", "list", "--state", "expired")
    check("a model version change expires evidence tied to the old version", "MD-07" in t)
    P("evidence", "intake", "--control", "MD-07", "--file", os.path.join(TMP, "garak.json"), "--kind", "report", "--tool", "garak", "--model-version", "v2", "--submitted-by", "priya-rao")
    P("finding", "record", "--evidence", "EV-003", "--verdict", "satisfied", "--reasons", "Re-tested on v2.")
    P("indicator", "set", "--control", "MD-07", "--metric", "jailbreak rate", "--baseline", "0.02", "--min", "0", "--max", "0.05")
    t = P("indicator", "update", "--id", "IND-001", "--value", "0.2")
    check("an out-of-tolerance indicator suspends credit", "suspended" in t)
    t = P("risk", "accept", "--id", "R-011", "--by", "dana-lee", "--statement", "ok", expect=2)
    check("a Critical residual risk cannot be accepted by AI Governance alone", "executive-leadership" in t)
    P("risk", "accept", "--id", "R-011", "--by", "max-ho", "--statement", "I accept this until the next test cycle.", "--basis", "Board resolution")
    P("indicator", "update", "--id", "IND-001", "--value", "0.01")
    t = P("incident", "open", "--title", "Named opener", "--severity", "low", "--description", "d", "--by", "dana-lee", expect=2)
    check("an incident declared in a person's name needs that person's words", "own words" in t)
    P("incident", "open", "--title", "Wrong advice", "--severity", "high", "--description", "d")
    _iid = [i["id"] for i in json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "incidents.json"), encoding="utf-8"))][-1]
    t = P("incident", "escalate", "--id", _iid, expect=2)
    check("an incident notice with nobody to tell is refused instead of being logged as sent", "Say who must be told" in t)
    t = P("incident", "escalate", "--id", _iid, "--to", "dana-lee")
    check("an incident notice is written, not claimed as sent", "NOT been sent" in t)
    _tl = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "incidents.json"), encoding="utf-8"))[-1]["timeline"][-1]["note"]
    check("the incident timeline says the notice was written, not sent", _tl.startswith("Notice written") and "Notice sent" not in _tl)
    t = P("incident", "close", "--id", "INC-001", "--by", "dana-lee", "--statement", "closed", "--retrospective", "r", "--lesson", "Add a medical-advice guardrail control")
    check("closing an incident feeds a catalog proposal", "catalog proposal" in t)
    P("views", "regenerate", ws=True)
    t = run("check", "run", expect=0)
    check("integrity checks pass on an untouched workspace", "No problems" in t)
    jf = os.path.join(WS, "projects", "triage-bot", "decisions", "journal.jsonl")
    raw = open(jf, encoding="utf-8").read()
    open(jf, "w", encoding="utf-8").write(raw.replace("Started ASSESS", "Started ASSESSMENT", 1))
    t = P("journal", "verify", expect=1)
    check("editing a journal line is detected", "edited" in t)
    open(jf, "w", encoding="utf-8").write(raw)
    t = P("journal", "verify")
    check("restored journal verifies again", "intact" in t)

    # ------------------------------------------------------------------ regression tests for the independent review
    import subprocess
    def ctrl_rows(state=None, proj="triage-bot"):
        args = ["control", "list", "-p", proj] + (["--state", state] if state else [])
        rows = []
        for ln in run(*args).splitlines():
            parts = ln.split()
            if parts and len(parts[0]) in (5, 6) and parts[0][2] == "-":
                rows.append({"id": parts[0], "state": parts[1], "owner": parts[parts.index("owner:") + 1] if "owner:" in parts else None})
        return rows
    def ev_id(text):
        return re.search(r"Evidence (EV-\d+) received", text).group(1)
    def assigned_ids(n):
        return [r["id"] for r in ctrl_rows("assigned")][:n]
    open(os.path.join(TMP, "doc.txt"), "w").write("A document the owner prepared.")
    open(os.path.join(TMP, "fake.sarif"), "w").write("not a report")

    # 3. typed text can never earn strong evidence
    c1, c2, c3, c4 = assigned_ids(4)
    t = P("evidence", "intake", "--control", c1, "--text", "trust me", "--kind", "report", "--tool", "fake", "--model-version", "v2", expect=2)
    check("typed-in text cannot be passed off as a tool report", "only be recorded as a statement" in t)
    t = P("evidence", "intake", "--control", c1, "--file", os.path.join(TMP, "fake.sarif"), "--kind", "report", "--tool", "garak", "--model-version", "v2")
    e_a = ev_id(t)
    check("a report that does not name its tool in the file counts only as moderate", "strength on arrival moderate" in t)
    # 4. who may verify
    t = P("finding", "record", "--evidence", e_a, "--verdict", "satisfied", "--reasons", "ok", expect=2)
    check("the tool alone cannot verify a moderate report", "named reviewer" in t)
    t = P("finding", "record", "--evidence", e_a, "--verdict", "satisfied", "--reasons", "ok", "--by", "tom-wu", expect=2)
    check("a person with no authority cannot verify", "authority to verify" in t)
    e_b = ev_id(P("evidence", "intake", "--control", c2, "--file", os.path.join(TMP, "doc.txt"), "--kind", "document", "--submitted-by", "dana-lee"))
    t = P("finding", "record", "--evidence", e_b, "--verdict", "satisfied", "--reasons", "ok", "--by", "dana-lee", expect=2)
    check("the person who sent the evidence cannot judge it", "sent this evidence" in t)
    t = P("finding", "record", "--evidence", e_a, "--verdict", "satisfied", "--reasons", "Reviewed the report; scope and fixes are documented.", "--by", "dana-lee", expect=2)
    check("a person verifying evidence must give their own words, not just AIGRCeler's reasons", "own words" in t.lower() or "statement" in t.lower())
    t = P("finding", "record", "--evidence", e_a, "--verdict", "satisfied", "--reasons", "Reviewed the report; scope and fixes are documented.", "--by", "dana-lee", "--statement", "I reviewed it and I am satisfied.")
    check("a half step of credit that does not move the score is said out loud", "half step is kept" in t and "banked" in t)
    check("a named reviewer with authority can verify", ctrl_rows("verified") and any(r["id"] == c1 for r in ctrl_rows("verified")))
    # evidence edited after it arrived stops earning credit at once
    import json as _j
    _pd = os.path.join(WS, "projects", "triage-bot")
    import glob as _g
    _ctl = next(c_ for c_ in (_j.load(open(f, encoding="utf-8")) for f in _g.glob(os.path.join(_pd, "controls", "*", "*.json")))
                if c_["state"] == "verified" and c_.get("current_evidence"))
    _ev = next(e for e in _j.load(open(os.path.join(_pd, "data", "evidence.json"), encoding="utf-8")) if e["id"] == _ctl["current_evidence"])
    _fp = os.path.join(_pd, _ev["file"].replace("/", os.sep))
    _orig = open(_fp, "rb").read()
    open(_fp, "ab").write(b"\nedited later")
    t = P("risk", "recompute")
    check("evidence edited after it arrived is expired and says why", "was changed after it arrived" in t)
    t = P("control", "list", "--state", "expired")
    check("the control whose evidence was edited stops being verified", _ev["control"] in t)
    t = run("check", "run", expect=None)
    check("the integrity check still reports the edited file", "fingerprint mismatch" in t)
    check("the edit is written to the decision journal, not only to the control", "evidence_tampered" in open(os.path.join(_pd, "decisions", "journal.jsonl"), encoding="utf-8").read())
    open(_fp, "wb").write(_orig)
    # 2. retired / waived controls cannot be revived by a later finding
    e_c = ev_id(P("evidence", "intake", "--control", c3, "--file", os.path.join(TMP, "doc.txt"), "--kind", "document", "--submitted-by", "tom-wu"))
    P("control", "retire", "--id", c3, "--by", "dana-lee", "--statement", "No longer needed for this system.")
    t = P("finding", "record", "--evidence", e_c, "--verdict", "satisfied", "--reasons", "ok", "--by", "dana-lee", expect=2)
    check("a retired control is not revived by a later finding", "not in force" in t)
    e_d = ev_id(P("evidence", "intake", "--control", c4, "--file", os.path.join(TMP, "doc.txt"), "--kind", "document", "--submitted-by", "tom-wu"))
    P("control", "waive", "--id", c4, "--by", "dana-lee", "--statement", "Waived for now.", "--until", "2027-06-30")
    t = P("finding", "record", "--evidence", e_d, "--verdict", "satisfied", "--reasons", "ok", "--by", "dana-lee", expect=2)
    check("a waived control is not revived by a later finding", "not in force" in t)
    # 1. a 'not' finding after an upgrade cannot re-verify
    P("catalog", "propose", "--kind", "edit", "--id", c1, "--change", '{"title": "Updated title for the test"}', "--reason", "Wording change for the regression test.")
    pid = [ln.split()[0] for ln in run("catalog", "proposals", "--status", "open").splitlines() if ln.startswith("P-")][-1]
    run("catalog", "approve", "--id", pid, "--by", "dana-lee", "--statement", "Approved the wording change.")
    P("control", "upgrade", "--id", c1, "--by", "dana-lee", "--statement", "Move to the new version.")
    e_e = ev_id(P("evidence", "intake", "--control", c1, "--file", os.path.join(TMP, "doc.txt"), "--kind", "document", "--submitted-by", "tom-wu"))
    t = P("finding", "record", "--evidence", e_e, "--verdict", "not", "--reasons", "does not meet the criteria")
    check("a 'not' finding after an upgrade does not leave the control verified", "now verified" not in t and "now rejected" in t)
    # evidence answers only the request it is said to answer, never a second request about the same control
    _rf = os.path.join(_pd, "data", "requests.json")
    _rq = json.load(open(_rf, encoding="utf-8"))
    for _i in ("REQ-901", "REQ-902"):
        _rq.append({"id": _i, "type": "evidence_request", "to": "tom-wu", "controls": [c1], "status": "open", "due": "2031-01-01",
                    "sent": "2026-01-01T00:00:00+00:00", "answered": None, "answer_file": None, "message_file": "x.md"})
    json.dump(_rq, open(_rf, "w", encoding="utf-8"), indent=1)
    P("evidence", "intake", "--control", c1, "--file", os.path.join(TMP, "doc.txt"), "--kind", "document", "--submitted-by", "tom-wu", "--request", "REQ-901")
    _st = {r["id"]: r["status"] for r in json.load(open(_rf, encoding="utf-8"))}
    check("evidence closes only the request it was said to answer", _st["REQ-901"] == "answered" and _st["REQ-902"] == "open")
    _rq = json.load(open(_rf, encoding="utf-8"))
    for _r in _rq:
        if _r["id"] == "REQ-901":
            _r["status"] = "open"; _r["answered"] = None
    json.dump(_rq, open(_rf, "w", encoding="utf-8"), indent=1)
    t = P("evidence", "intake", "--control", c1, "--file", os.path.join(TMP, "doc.txt"), "--kind", "document", "--submitted-by", "tom-wu")
    _st = {r["id"]: r["status"] for r in json.load(open(_rf, encoding="utf-8"))}
    check("with two open requests and none named, none is closed and the person is told", "none was closed" in t and _st["REQ-901"] == "open" and _st["REQ-902"] == "open")
    # 5. credit trusts only valid inputs
    t = P("indicator", "update", "--id", "IND-001", "--value", "nan", expect=2)
    check("a reading that is not a number is refused", "ordinary number" in t)
    t = P("indicator", "set", "--control", "MD-07", "--metric", "other", "--min", "5", "--max", "1", expect=2)
    check("an indicator range with min above max is refused", "minimum is higher" in t)
    base = P("risk", "show").splitlines()[-1]
    os.environ["AIGRCELER_NOW"] = "2035-01-01T09:00:00+00:00"
    t = P("risk", "recompute")
    after_time = P("risk", "show").splitlines()[-1]
    check("evidence past its date earns no credit when risk is recomputed", base != after_time)
    t = P("control", "list", "--state", "expired")
    check("the expiry is applied, not just noticed", "MD-07" in t)
    del os.environ["AIGRCELER_NOW"]
    # 14. the clock cannot be moved outside tests
    saved = os.environ.pop("AIGRCELER_TEST")
    os.environ["AIGRCELER_NOW"] = "2035-01-01T09:00:00+00:00"
    from aig.core import now as _now
    check("the clock override is ignored outside test runs", _now().year != 2035)
    os.environ["AIGRCELER_TEST"] = saved
    del os.environ["AIGRCELER_NOW"]
    # 6. authority ends at once; dates are validated
    run("person", "add", "--name", "Gov Two")
    t = run("role", "assign", "--person", "gov-two", "--role", "ai-governance", "--start", "2026-1-1", "--by", "dana-lee", expect=2)
    check("a date not written YYYY-MM-DD is refused", "YYYY-MM-DD" in t)
    run("role", "assign", "--person", "gov-two", "--role", "ai-governance", "--by", "dana-lee")
    run("role", "unassign", "--person", "gov-two", "--role", "ai-governance", "--by", "dana-lee")
    t = P("project", "lane-set", "--lane", "full", "--by", "gov-two", "--statement", "x", expect=2)
    check("AI Governance authority ends the moment the assignment is ended", "not allowed" in t)
    # 13. decisions are recorded under the person who made them
    t = P("risk", "accept", "--id", "R-001", "--by", "dana-lee", "--with", "max-ho", "--statement", "x", expect=2)
    check("one person cannot accept a risk on another's behalf", "their own acceptance" in t)
    t = P("risk", "accept", "--id", "R-001", "--by", "dana-lee", "--until", "2020-01-01", "--statement", "x", expect=2)
    check("an acceptance with an end date in the past is refused", "already passed" in t)
    t = P("control", "approve", "--ids", "GO-01", "--by", "dana-lee", expect=2)
    check("approving controls needs the approver's own words", "own words" in t)
    # 10. exceptions are time-limited and scoped
    t = run("exception", "add", "--what", "Dana owns one control", "--why", "No one else can", "--expires", "2020-01-01", "--person", "dana-lee",
            "--by", "dana-lee", "--statement", "Recorded.", expect=2)
    check("an exception that has already expired is refused", "already passed" in t)
    run("exception", "add", "--what", "Dana owns one control", "--why", "No one else can", "--expires", "2027-12-31", "--person", "dana-lee",
        "--controls", c2, "--by", "dana-lee", "--statement", "Recorded.")
    # 12. facts that drive the lane cannot be lowered quietly
    t = P("project", "set", "--flags-off", "personal_data", expect=2)
    check("lowering a lane-driving fact needs AI Governance", "needs a decision" in t)
    t = P("project", "set", "--flags-off", "personal_data", "--by", "dana-lee", expect=2)
    check("lowering a lane-driving fact needs the decider's words", "own words" in t)
    P("project", "set", "--flags-off", "personal_data", "--by", "dana-lee", "--statement", "Verified that no personal data enters the system.")
    check("a lowered fact is written in the journal", "project_facts_changed" in open(jf, encoding="utf-8").read())
    P("project", "set", "--flags-on", "personal_data")
    # 15. ordinary mistakes give plain refusals, never a stack trace
    t = P("obligation", "add", "--title", "Notify regulator", "--authority", "DPA", expect=2)
    check("an obligation without a date is refused", "due date" in t)
    t = P("stage", "close", "--stage", "NOPE", expect=2)
    check("an unknown stage is refused plainly", "Stage must be one of" in t)
    t = P("stage", "start", "--by", "dana-lee", "--statement", "x", expect=2)
    check("a missing stage name is refused plainly", "Say which stage" in t)
    t = P("incident", "open", "--title", "x", expect=2)
    check("an incident without a severity is refused plainly", "Severity must be" in t)
    t = P("evidence", "intake", "--control", c1, "--file", TMP, "--kind", "document", expect=2)
    check("a folder given as evidence is refused plainly", "is a folder" in t)
    open(os.path.join(TMP, "bin.dat"), "wb").write(b"\xff\xfe\x00\x81\x82\x83\x84")
    t = P("stage", "adopt", "--stage", "OPERATE", "--source", os.path.join(TMP, "bin.dat"), "--by", "dana-lee", expect=2)
    check("a binary file as a statement is refused plainly", "not a text file" in t or "must close" in t)
    t = run("ws", "status", "--ws", os.path.join(TMP, "nowhere"), ws=False, expect=2)
    check("an unknown --ws is an error, not a silent fallback", "not an AIGRCeler workspace" in t)
    t = run("ws", "release", ws=False)
    check("ws release says which framework release this is, with no workspace needed", "AIGRCeler framework version:" in t)
    t = run("catalog", "propose", "--kind", "add", "--reason", "Trying a bad control ID here.",
            "--change", json.dumps({"id": "GO-x/../../../../data/roles", "title": "t"}), expect=2)
    check("a control ID that is not a control ID is refused", "control ID" in t or "missing" in t)
    open(os.path.join(TMP, "stmt16.txt"), "wb").write("Adopted in my own words é".encode("utf-16"))
    from aig.core import need_text as _nt
    class _A: statement = os.path.join(TMP, "stmt16.txt")
    check("a statement file saved by Windows PowerShell (UTF-16) is read", "Adopted" in _nt(_A, "statement", "x"))
    # 9. truncating or deleting the journal is detected, and evidence is cross-checked against it
    raw2 = open(jf, encoding="utf-8").read()
    lines2 = raw2.splitlines(True)
    open(jf, "w", encoding="utf-8").write("".join(lines2[:-1]))
    t = P("journal", "verify", expect=1)
    check("removing the last journal line is detected", "removed from the end" in t)
    open(jf, "w", encoding="utf-8").write(raw2)
    ej = os.path.join(WS, "projects", "triage-bot", "data", "evidence.json")
    ev_raw = open(ej, encoding="utf-8").read()
    ev_list = json.loads(ev_raw)
    ev_list[0]["sha256"] = "0" * 64
    open(ej, "w", encoding="utf-8").write(json.dumps(ev_list))
    t = run("check", "run", expect=1)
    check("a rewritten evidence record is caught against the journal", "differs" in t or "fingerprint" in t)
    open(ej, "w", encoding="utf-8").write(ev_raw)
    t = run("check", "run", expect=0)
    check("checks pass again once the record is restored", "No problems" in t)
    # 14. two commands at once cannot lose each other's records
    P("stage", "block", "--reason", "seed block")
    engine = os.path.join(HERE, "..", "engine", "aigrceler.py")
    procs = [subprocess.Popen([sys.executable, engine, "stage", "block", "--reason", "parallel %d" % i, "--ws", WS, "-p", "triage-bot"],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) for i in range(6)]
    for pr_ in procs: pr_.wait()
    blocks = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "project.json")))["blocks"]
    jb = [json.loads(l) for l in open(jf, encoding="utf-8") if '"block_placed"' in l]
    check("six commands run at once all land (no lost records)", len(blocks) == len(jb) == 7)



    # ---- Operate: no closing, live readiness, the go decision, chase list, review schedule, due dates ----
    t = P("stage", "close", "--stage", "OPERATE", expect=2)
    check("Operate does not close", "Operate does not close" in t and "operate signoff" in t)
    t = P("operate", "readiness")
    check("readiness is worked out live and says what stands in the way", "Required controls verified:" in t and "Nothing stands in the way" in t or "Standing in the way" in t)
    t = P("stage", "gate", "--stage", "OPERATE")
    check("the Operate gate shows the same readiness", "Readiness for the go decision" in t)
    t = P("operate", "signoff", "--statement", "Go.", expect=2)
    check("the tool alone cannot record the go decision", "decision by a named person" in t)
    t = P("operate", "signoff", "--by", "priya-rao", "--statement", "Go ahead.", expect=2)
    check("a person outside AI Governance cannot record the go decision", "not allowed" in t)
    jfile = os.path.join(WS, "projects", "triage-bot", "decisions", "journal.jsonl")
    t = P("operate", "signoff", "--by", "dana-lee", "--statement", "Go ahead while the block is in force.", expect=2)
    check("the go decision cannot be recorded while a stage block is in force", "stage block is in force" in t)
    from aig.core import WS as _W0
    for b_ in [x for x in _W0(WS).project("triage-bot").info()["blocks"] if not x["lifted"]]:
        P("stage", "lift-block", "--id", b_["id"], "--by", "dana-lee", "--statement", "I lift the block knowing what is open; this is a test with no real candidates.")
    n_before = len(open(jfile).read().splitlines())
    t = P("operate", "signoff", "--by", "dana-lee", "--statement", "Go ahead anyway.", expect=None)
    open_items_now = "Nothing stands in the way" in P("operate", "readiness")
    if not open_items_now:
        check("going ahead over open items needs a full sentence of reasons", "own words" in t and "at least a full sentence" in t)
        t = P("operate", "signoff", "--by", "dana-lee", "--statement",
              "I accept going ahead while the rest of the proof is gathered, because the pilot is small and a person checks every result.")
        check("the go decision is recorded over open items and kept as a concern", "left open" in t and "CON-" in t)
    else:
        check("the go decision is recorded when nothing stands in the way", "Go decision recorded" in t)
    jl = open(jfile).read().splitlines()
    last = json.loads(jl[-1])
    check("the go decision is a journal line of its own kind", last["type"] == "signoff")
    check("the go decision keeps the open items it was recorded over", ("open_items" in last["extra"]) and (bool(last["extra"]["open_items"]) != open_items_now))
    t = P("project", "show")
    check("the project shows its last go decision", "Last go decision" in t)
    P("views", "regenerate")
    ls = json.load(open(os.path.join(WS, "projects", "triage-bot", "00-status", "launch-status.json")))
    check("the launch status file carries the last go decision and open high incidents", ls.get("last_go_decision") and "high_or_critical_incidents_open" in ls)

    t = P("operate", "chase")
    check("the chase list says nothing was sent and groups by who must act", "Nothing here has been sent" in t and "Waiting on us" in t)
    check("the chase list is also written as a view file", os.path.exists(os.path.join(WS, "projects", "triage-bot", "00-status", "7-chase-list.md")))
    from aig.core import WS as _WS1
    _unsent = [r_ for r_ in _WS1(WS).project("triage-bot").load("requests", []) if r_["status"] == "open" and not r_.get("delivered")]
    t = P("operate", "chase")
    check("every written-but-unsent message shows on the chase list under what waits on us", bool(_unsent) and all(r_["id"] in t for r_ in _unsent))
    # what a person says about sending, taking back and withdrawing leaves a journal line; so does confirming an incident
    def _last_type():
        return json.loads(open(jfile).read().splitlines()[-1])["type"]
    _u = [r_ for r_ in _WS1(WS).project("triage-bot").load("requests", []) if r_["status"] == "open" and not r_.get("delivered")]
    P("control", "mark-sent", "--id", _u[0]["id"], "--by", "dana-lee", "--note", "Sent by email this morning.")
    check("marking a message as sent is a journal line in the sender's name", _last_type() == "request_sent")
    P("control", "unmark-sent", "--id", _u[0]["id"], "--by", "dana-lee", "--note", "I marked the wrong message as sent by mistake.")
    check("taking back a sent mark is a journal line", _last_type() == "request_unsent")
    P("request", "withdraw", "--id", _u[0]["id"], "--by", "dana-lee", "--reason", "No longer needed after the call.")
    check("withdrawing a request is a journal line", _last_type() == "request_withdrawn")
    P("incident", "open", "--title", "Ack test", "--severity", "low", "--description", "d")
    _iid2 = [l_.split()[0] for l_ in P("incident", "list").splitlines() if "Ack test" in l_][0]
    P("incident", "ack", "--id", _iid2, "--by", "dana-lee")
    check("confirming an incident was seen is a journal line", _last_type() == "incident_acknowledged")
    P("incident", "close", "--id", _iid2, "--by", "dana-lee", "--statement", "Closed after checking it was a false alarm.", "--retrospective", "A false alarm; nothing changes.", "--lesson", "Check the alert source first.")
    _inc = [i_ for i_ in _WS1(WS).project("triage-bot").load("incidents", []) if i_["id"] == _iid2][0]
    check("a closed incident records who closed it and the lesson", _inc.get("closed_by", "").endswith("dana-lee") and _inc.get("lesson") == "Check the alert source first.")
    t = P("operate", "chase", "--person", "nobody", expect=2)
    check("the chase list refuses an unknown person", "not in the people directory" in t)
    t = P("operate", "chase", "--person", "tom-wu")
    check("the chase list can be shown for one person", "Chase list" in t)

    cid_ = [r["id"] for r in ctrl_rows("assigned")][0]
    t = P("control", "set-due", "--id", cid_, "--due", "2030-01-02", expect=2)
    check("moving a due date needs a reason", "reason" in t)
    t = P("control", "set-due", "--id", cid_, "--due", "2030-01-02", "--why", "The owner is away until January.")
    check("a control's due date can be moved with a reason", "2030-01-02" in t)
    from aig.core import WS as _WSC, default_due_date as _ddd
    _c = _WSC(WS).project("triage-bot").get_control(cid_)
    _owner = "tom-wu" if _c.get("owner") != "tom-wu" else "priya-rao"
    t = P("control", "assign", "--ids", cid_, "--owner", _owner)
    check("assigning without a date gives a default from how much the control matters", "No due date was given" in t)
    check("the default date follows the control's weight", _WSC(WS).project("triage-bot").get_control(cid_)["due"] == _ddd(_c["definition"]))

    t = P("review", "due")
    check("the review due date is shown once Operate has started", "Next review due" in t or "Review overdue" in t)
    check("the default review rhythm follows the lane", "default for the lane" in t)
    t = P("review", "schedule", "--days", "90", "--statement", "Review every quarter.", expect=2)
    check("setting the review rhythm needs a named person", "decision by a named person" in t)
    t = P("review", "schedule", "--days", "3", "--by", "dana-lee", "--statement", "Very often.", expect=2)
    check("an absurd review rhythm is refused", "outside what makes sense" in t)
    t = P("review", "schedule", "--days", "90", "--by", "dana-lee", "--statement", "We review every quarter because the system changes often.")
    check("AI Governance can set the review rhythm in its own words", "every 90 days" in t and "set by AI Governance" in t)
    t = P("review", "add", "--kind", "periodic", "--summary", "First quarterly review.")
    check("recording a review shows when the next is due", "Review REV-" in t and "last recorded" in t)

    # a project record from the six-stage version moves to four stages without touching the journal
    pj = os.path.join(WS, "projects", "triage-bot", "data", "project.json")
    jbefore = open(jfile).read()
    saved = open(pj).read()
    d = json.loads(saved)
    op = d["stages"].pop("OPERATE")
    d["stages"]["ASSURE"] = dict(op, covers=["ASSURE"])
    d["stages"]["MONITOR"] = {"status": "not_started"}
    d["stages"]["REVIEW"] = {"status": "not_started"}
    d["current_stage"] = "ASSURE"
    open(pj, "w").write(json.dumps(d))
    t = P("project", "show")
    check("an older project record reads as four stages with Operate started", "OPERATE" in t and "ASSURE" not in t and "OPERATE   started" in t)
    check("reading an older project record does not touch the journal", open(jfile).read() == jbefore)
    t = P("stage", "start", "--stage", "ASSURE", "--by", "dana-lee", "--statement", "again", expect=2)
    check("the old stage names still work and mean Operate", "OPERATE is already started" in t)
    open(pj, "w").write(saved)

    # 7. the light lane runs as one pass, whatever order the decisions came in
    run("project", "create", "--name", "FAQ Bot", "--purpose", "Answers staff questions from the handbook", "--sourcing-mode", "third-party-service", "--model-version", "m1")
    Q = lambda *a, **k: run(*(list(a) + ["-p", "faq-bot"]), **k)
    Q("project", "screen", "--users", "few", "--autonomy", "reviewed", "--data", "none", "--impact", "minor")
    Q("stage", "start", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "I start DISCOVER.")
    t = Q("project", "lane-set", "--lane", "light", "--by", "dana-lee", "--statement", "Light lane confirmed.")
    check("a light lane decided after DISCOVER started widens the one pass", "now covers Assess and Govern" in t)
    t = Q("stage", "close", "--stage", "ASSESS", expect=2)
    check("in the light lane Assess cannot close on its own", "one combined pass" in t)
    Q("project", "set", "--users", "Staff", "--data-sources", "Public handbook", "--jurisdictions", "US", "--eval-metrics", "monthly spot check")
    t = Q("stage", "close", "--stage", "DISCOVER", expect=2)
    t2 = Q("profile", "show", "--open")
    check("DISCOVER lists what depends on the system as still to find out until it is answered",
          "Still to find out" in t and "what depends on what it produces" in t2)
    Q("project", "set", "--downstream-dependencies", "none: nothing else uses the bot")
    fill("faq-bot")
    Q("risk", "init"); Q("risk", "set", "--all-defaults", "--reason", "standard scenarios fit")
    Q("control", "draft")
    Q("control", "approve", "--all-drafted", "--by", "dana-lee", "--statement", "Approved the light-lane core set.")
    for role, who in [("security", "priya-rao"), ("engineering-data-science", "sam-ortiz"), ("operations", "tom-wu"),
                      ("legal-compliance", "lena-fox"), ("executive-leadership", "max-ho")]:
        r_ = Q("control", "assign", "--role", role, "--owner", who, "--due", "2026-12-01", expect=None)
    t = Q("stage", "close", "--stage", "DISCOVER")
    check("the light pass closes as one", "DISCOVER closed" in t)
    t = Q("stage", "start", "--stage", "OPERATE", "--by", "dana-lee", "--statement", "I start OPERATE.")
    check("OPERATE can start after the combined pass", "OPERATE started" in t)
    t = run("check", "run", expect=0)
    check("the light-lane flow raises no integrity problems", "PROBLEM" not in t)
    # 12. a re-screen that raises the tier raises the lane
    t = Q("project", "screen", "--users", "very-many", "--autonomy", "automated", "--data", "sensitive", "--impact", "rights-or-safety")
    check("a re-screen that raises the tier raises the lane automatically", "raised" in t or "full" in t)
    check("the lane really changed", '"lane": "full"' in open(os.path.join(WS, "projects", "faq-bot", "data", "project.json")).read())
    # 8. adopting a statement cannot skip the rules
    run("project", "create", "--name", "Pilot Bot", "--purpose", "Pilot", "--sourcing-mode", "third-party-service")
    R = lambda *a, **k: run(*(list(a) + ["-p", "pilot-bot"]), **k)
    open(os.path.join(TMP, "old.md"), "w").write("An earlier approval of this project, dated last year.")
    t = R("stage", "adopt", "--stage", "OPERATE", "--source", os.path.join(TMP, "old.md"), "--by", "dana-lee", expect=2)
    check("adopting a statement cannot skip the stages before it", "must close" in t or "lane must be decided" in t)
    R("stage", "block", "--reason", "open question from legal")
    t = R("stage", "adopt", "--stage", "GOVERN", "--source", os.path.join(TMP, "old.md"), "--by", "dana-lee", expect=2)
    check("adopting a statement for a stage after Assess respects an open block", "cannot start while a block" in t)
    t = R("stage", "start", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "I start DISCOVER under the block.")
    check("an open block does not stop Discovery itself from starting", "DISCOVER started" in t)
    t = R("stage", "close", "--stage", "GOVERN", "--without-start", "--by", "dana-lee", "--statement", "x", expect=2)
    check("closing a stage without a start decision respects the order", "must close" in t or "cannot start while a block" in t or "lane must be decided" in t)
    # 10. an exception covers only what it names
    run("exception", "add", "--what", "Dana owns one control", "--why", "No one else can", "--expires", "2027-12-31", "--person", "dana-lee",
        "--controls", "GO-01", "--by", "dana-lee", "--statement", "Recorded.")
    exn = re.findall(r"EX-\d+", open(os.path.join(WS, "data", "exceptions.json")).read())[-1]
    q_ids = [r["id"] for r in ctrl_rows("approved", "faq-bot")] or [r["id"] for r in ctrl_rows("assigned", "faq-bot")]
    t = Q("control", "assign", "--ids", "GO-02", "--owner", "dana-lee", "--exception", exn, expect=2)
    check("an exception only covers the controls it names", "only covers" in t)
    t = Q("exception", "add", "--what", "Dana owns one control on this system", "--why", "No one else can", "--expires", "2027-12-31", "--person", "dana-lee",
          "--controls", "GO-01", "--by", "dana-lee", "--statement", "Recorded.", expect=None)
    check("a system's exception has its own ID prefix, so it never shares an ID with a company-wide one", "EXP-001" in t)
    t = Q("exception", "list", expect=None)
    check("the exception list shows company-wide and system exceptions, what each covers and when it ends",
          "company-wide" in t and "system: faq-bot" in t and "EXP-001" in t and "Covers: GO-01" in t and "ends 2027-12-31" in t)
    t = Q("control", "assign", "--ids", "GO-01", "--owner", "dana-lee", "--exception", exn, "--due", "2026-12-01", expect=None)
    t = Q("control", "owners", expect=None)
    check("the owners list shows the exception that covers an AI Governance member's controls",
          ("exception %s covers all of these" % exn) in t or ("exception %s covers some" % exn) in t)

    # working inside a system's folder means that system is meant (the menu launches Claude there)
    here = os.getcwd()
    os.chdir(os.path.join(WS, "projects", "faq-bot"))
    try:
        t = run("project", "show", ws=False)
    finally:
        os.chdir(here)
    check("run from inside a system's folder, the system is found without -p", "FAQ Bot" in t)

    # 9. the discovery profile: answers with their sources, factors raised, unknowns capped, batched questions
    run("project", "create", "--name", "Profile Bot", "--purpose", "Summarises support tickets", "--sourcing-mode", "third-party-service")
    D = lambda *a, **k: run(*(list(a) + ["-p", "profile-bot"]), **k)
    t = D("profile", "set", "--field", "users", "--value", "unknown", "--source", "Dana", expect=2)
    check("a placeholder is refused as an answer", "not an answer" in t)
    t = D("profile", "set", "--field", "users", "--value", "Support staff", "--source", "probably", expect=2)
    check("a guess is refused as a source", "not a source" in t)
    t = D("profile", "set", "--field", "users", "--value", "Support staff", expect=2)
    check("an answer without a source is refused", "--source" in t)
    t = D("profile", "set", "--field", "user_scale", "--value", "hundreds", "--source", "Dana", expect=2)
    check("a choice question accepts only its choices", "must be one of" in t)
    t = D("profile", "set", "--field", "generative", "--value", "maybe", "--source", "Dana", expect=2)
    check("a yes/no question needs yes or no", "yes or no" in t)
    t = D("profile", "set", "--field", "generative", "--value", "yes: writes the summaries", "--source", "Sam Ortiz, 2026-10-12")
    pj = json.load(open(os.path.join(WS, "projects", "profile-bot", "data", "project.json"), encoding="utf-8"))
    check("an answer that raises a factor raises it on the system record", pj["flags"]["generative"] is True)
    json.dump({"user_scale": "few", "autonomy": "reviewed", "data_kind": "none", "impact_level": "minor"}, open(os.path.join(TMP, "screen.json"), "w"))
    t = D("profile", "set", "--file", os.path.join(TMP, "screen.json"), "--source", "Tom Wu, by email")
    pj = json.load(open(os.path.join(WS, "projects", "profile-bot", "data", "project.json"), encoding="utf-8"))
    check("once the four screening questions are answered the screening runs by itself", "running the screening" in t and pj.get("tier"))
    D("profile", "set", "--field", "business_owner", "--value", "Tom Wu", "--source", "guessed from the org chart", "--inferred")
    t = D("profile", "show", "--open")
    check("an inferred answer stays open until a person confirms it", "inferred" in t and "who answers for it" in t)
    jl = open(os.path.join(WS, "projects", "profile-bot", "decisions", "journal.jsonl"), encoding="utf-8").read()
    check("recording answers leaves a line in the journal with the sources", "profile_recorded" in jl and "Sam Ortiz" in jl)
    t = P("profile", "set", "--field", "generative", "--value", "no", "--source", "Sam Ortiz")
    pj = json.load(open(os.path.join(WS, "projects", "triage-bot", "data", "project.json"), encoding="utf-8"))
    check("an answer that would lower a factor is not applied: that is AI Governance's decision",
          "AI Governance has to decide" in t and pj["flags"]["generative"] is True)
    # unknown after asking
    t = D("profile", "unknown", "--field", "users", "--asked", "tom-wu", "--reason", "Tom says nobody has counted them", expect=2)
    check("a question that decides the lane cannot be left unknown", "cannot be left unknown" in t)
    t = D("profile", "unknown", "--field", "related_ai_use", "--asked", "tom-wu", "--reason", "Tom says nobody has looked at it", expect=2)
    check("unknown is allowed only after the person was really sent the question", "has not been sent a question" in t)
    t = D("profile", "plan")
    check("the plan drafts one message per person and does not send without a go-ahead", "This is a draft" in t and "Tom Wu" in t)
    t = D("profile", "plan", "--send")
    check("the plan sends one batched message per person", "written to Tom Wu" in t)
    t = D("profile", "plan", "--send")
    check("asking again does not send the same questions twice", "already sent" in t)
    t = D("profile", "unknown", "--field", "related_ai_use", "--asked", "tom-wu", "--reason", "no idea", expect=2)
    check("a one-line reason for 'not known' is refused", "at least five words" in t)
    t = D("profile", "unknown", "--field", "related_ai_use", "--asked", "tom-wu", "--reason", "Tom says nobody has looked at what the team uses")
    check("unknown after asking is recorded and carried to Assess", "Recorded as not known" in t and "carried to Assess" in t)
    t = D("concern", "list")
    check("each unknown becomes a concern for Assess, in AIGRCeler's own words", "Not known after asking Tom Wu" in t)
    # the cap, and the risk starting point
    run("project", "create", "--name", "Cap Bot", "--purpose", "Sorts internal mail", "--sourcing-mode", "third-party-service")
    K = lambda *a, **k: run(*(list(a) + ["-p", "cap-bot"]), **k)
    K("project", "screen", "--users", "few", "--autonomy", "reviewed", "--data", "none", "--impact", "minor")
    K("project", "lane-set", "--lane", "light", "--by", "dana-lee", "--statement", "Light lane for the mail sorter.")
    K("stage", "start", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "I start DISCOVER.")
    skip = ("business_owner", "related_ai_use", "vendor_model", "generative", "downstream_dependencies")
    fill("cap-bot", skip=skip)
    for f_ in skip[:4]:
        K("profile", "unknown", "--field", f_, "--asked", "dana-lee", "--reason", "Dana asked around and nobody could say")
    t = K("stage", "gate", "--stage", "DISCOVER")
    check("a few unknowns within the limit do not hold Discover (the gate still asks for the last open question)", "Too many" not in t and "what depends on what it produces" in t)
    K("project", "set", "--downstream-dependencies", "none: nothing uses it")
    t = K("stage", "gate", "--stage", "DISCOVER")
    check("four unknowns of twenty-two required questions are within the 20% limit",
          "Too many" not in t and "Still to find out" not in t and "4 not known after asking" in t)
    t = K("risk", "init")
    check("risk scenarios start one step worse where the facts are not known, and say so", "one step worse" in t)
    rk = json.load(open(os.path.join(WS, "projects", "cap-bot", "data", "risks.json"), encoding="utf-8"))
    check("the starting rating names what is not known", any("raised one step in likelihood" in r["inherent_reason"] and "who answers for it" in r["inherent_reason"] for r in rk))
    K("profile", "unknown", "--field", "downstream_dependencies", "--asked", "dana-lee", "--reason", "Dana asked around and nobody could say")
    t = K("stage", "close", "--stage", "DISCOVER", expect=2)
    check("a fifth unknown goes over the 20% limit and holds Discover", "Too many answers" in t)
    K("profile", "set", "--field", "business_owner", "--value", "Tom Wu", "--source", "Tom Wu, confirmed in person")
    t = K("concern", "list")
    check("answering a question that was unknown closes its concern", "resolved" in t and "answered later" in t)
    t = K("stage", "gate", "--stage", "DISCOVER")
    check("with the unknown answered, the profile no longer holds Discover", "Too many" not in t and "Still to find out" not in t)
    t = K("profile", "unknown", "--field", "in_use_since", "--asked", "dana-lee", "--reason", "Dana asked around and nobody could say", expect=2)
    check("a question outside the lane's depth is not recorded as unknown", "not required" in t)
    # the EU questions are asked only when the system touches the EU
    D("profile", "set", "--field", "eu_nexus", "--value", "yes", "--source", "Dana")
    t = D("profile", "set", "--field", "eu_class_view", "--value", "prohibited-concern", "--source", "Dana, unsure about the screening step")
    cl = D("concern", "list")
    check("a possible prohibited use is raised as a proposal for AI Governance, never decided by the tool", "prohibited" in cl and "proposal" in cl)
    # the regulatory map
    rm = json.load(open(os.path.join(HERE, "..", "catalog", "regulatory-map.json"), encoding="utf-8"))
    refs = json.load(open(os.path.join(HERE, "regulatory-refs.json"), encoding="utf-8"))
    cat = {c["id"]: c for c in json.load(open(os.path.join(HERE, "..", "catalog", "starter-catalog.json"), encoding="utf-8"))["controls"]}
    prof_ids = {f["id"] for f in json.load(open(os.path.join(HERE, "..", "catalog", "discovery-profile.json"), encoding="utf-8"))["fields"]}
    for fw in rm["frameworks"]:
        have = [i["ref"] for i in fw["items"]]
        check("the map has an entry for every item of %s and nothing else (%d items)" % (fw["name"], len(refs[fw["id"]])),
              sorted(have) == sorted(refs[fw["id"]]))
        check("every entry of %s names a control or a mechanism, and every control exists" % fw["name"],
              all((i["controls"] or i["mechanisms"]) and all(c in cat for c in i["controls"]) for i in fw["items"]))
        check("%s: nothing is silently half-covered (partial and gap entries say what is left)" % fw["name"],
              all(i["note"] for i in fw["items"] if i["status"] != "covered"))
        check("%s: every discovery question named in the map exists" % fw["name"], all(p in prof_ids for i in fw["items"] for p in i["profile"]))
    sc_ids = {x["id"] for x in json.load(open(os.path.join(HERE, "..", "catalog", "scenarios.json"), encoding="utf-8"))["scenarios"]}
    prof = json.load(open(os.path.join(HERE, "..", "catalog", "discovery-profile.json"), encoding="utf-8"))["fields"]
    check("every risk scenario is fed by at least one discovery question", sc_ids <= {s_ for f_ in prof for s_ in f_["scen"]})
    check("every control a discovery question names exists", all(c in cat for f_ in prof for c in f_["ctl"]))
    check("every critical control is reachable from the legal map or the catalog tags (legal tags come from the map)",
          all(any(t.startswith(("ISO 42001", "EU AI Act", "NIST AI RMF")) for t in c["legal"]) for c in cat.values()
              if c["id"] in {x for fw in rm["frameworks"] for i in fw["items"] for x in i["controls"]}))
    check("the new impact-assessment control carries its ISO and NIST tags from the map",
          "ISO 42001 A.5.2" in cat["GO-17"]["legal"] and "NIST AI RMF MAP 5.1" in cat["GO-17"]["legal"])
    # a company on an older catalog is told what it lacks and can add it without touching its own controls
    go17 = os.path.join(WS, "catalog", "current", "governance-and-organization", "GO-17.json")
    os.remove(go17)
    t = run("reg", "coverage")
    check("a catalog missing starter controls is told so", "does not have" in t and "GO-17" in t and "sync-starter" in t)
    t = run("catalog", "sync-starter", "--statement", "x", expect=2)
    check("the tool cannot add controls to the catalog", "named person" in t)
    t = run("catalog", "sync-starter", "--by", "dana-lee", "--statement", "Add the new starter controls.")
    check("a named person adds the missing starter controls in one step", "Added 1 new control(s): GO-17" in t and os.path.exists(go17))
    t = run("reg", "coverage")
    check("the coverage report names each framework and what is only partly covered", "ISO/IEC 42001" in t and "partly covered" in t and "NIST AI Risk Management" in t and "not legal advice" in t)
    t = run("reg", "item", "--ref", "A.5.2")
    check("a single item shows its controls, mechanisms and the Discover questions behind it", "GO-17" in t and "affected_people" in t)
    t = run("reg", "item", "--ref", "Art. 27")
    check("an EU article shows who it applies to as a question for counsel", "question for counsel" in t)
    t = P("reg", "project")
    check("the per-system regulatory view lists items with the state of their controls and carries the disclaimer", "Regulatory view" in t and "not legal advice" in t and "| " in t)
    P("views", "regenerate")
    check("the regulatory view is written with the other views", os.path.exists(os.path.join(WS, "projects", "triage-bot", "00-status", "6-regulatory-view.md")))
    t = D("reg", "project", "--framework", "eu")
    check("an EU view reflects the company's own EU answers and leaves applicability to counsel", "EU link: yes" in t and "question for counsel" in t)
    # a possible legal hard stop must be looked at before Discover closes
    for slug_, nm_ in (("hire-bot", "Hire Bot"), ("hire-bot-two", "Hire Bot Two")):
        run("project", "create", "--name", nm_, "--purpose", "Screens job applicants", "--sourcing-mode", "third-party-service")
        H = (lambda sl: (lambda *a, **k: run(*(list(a) + ["-p", sl]), **k)))(slug_)
        H("project", "set", "--flags-on", "decisions_about_people,regulated_sector,personal_data", "--downstream-dependencies", "a")
        H("project", "screen", "--users", "many", "--autonomy", "automated", "--data", "personal", "--impact", "rights-or-safety")
        H("project", "lane-set", "--lane", "full", "--by", "dana-lee", "--statement", "Full lane.")
        H("stage", "start", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "Start.")
        fill(slug_)
    H1 = lambda *a, **k: run(*(list(a) + ["-p", "hire-bot"]), **k)
    H2 = lambda *a, **k: run(*(list(a) + ["-p", "hire-bot-two"]), **k)
    t = H1("stage", "close", "--stage", "DISCOVER", expect=2)
    check("a system that decides about people in a regulated field cannot close Discover until a possible legal hard stop is looked at",
          "possible legal hard stop has not been looked at" in t)
    H1("views", "regenerate")
    waiting = open(os.path.join(WS, "projects", "hire-bot", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("the waiting page, which the session start reports, shows the unresolved possible legal hard stop", "possible legal hard stop" in waiting)
    t = H1("stage", "block-review", "--reason", "not needed", expect=2)
    check("a recorded reason for no block must be a real sentence", "at least ten words" in t)
    H1("stage", "block-review", "--reason", "No bias audit is needed here because counsel was asked and confirmed no rules apply to this use.")
    t = H1("stage", "gate", "--stage", "DISCOVER")
    check("a recorded reason for no block clears the check", "possible legal hard stop" not in t)
    H2("stage", "block", "--reason", "No bias audit is known; whether rules apply is a question for counsel")
    t = H2("stage", "gate", "--stage", "DISCOVER")
    check("placing a block also clears the check", "possible legal hard stop" not in t)
    # a block lets Assess start and run, but not close, and holds the stages after it
    H2("stage", "close", "--stage", "DISCOVER", "--by", "dana-lee", "--statement", "Close Discover; the block stays.")
    t = H2("stage", "start", "--stage", "ASSESS", "--by", "dana-lee", "--statement", "Start Assess under the block.")
    check("an open block does not stop Assess from starting", "ASSESS started" in t)
    t = H2("stage", "close", "--stage", "ASSESS", "--by", "dana-lee", "--statement", "x", expect=2)
    check("an open block stops Assess from closing", "cannot close while a stage block is in force" in t)
    t = H2("stage", "close", "--stage", "ASSESS", "--by", "dana-lee", "--force-with-reason", "I accept leaving this open because the test is only a test and nothing real depends on it today.", expect=2)
    check("closing over a block is not possible, even with a reason", "closing over it is not an option" in t)
    t = H2("stage", "start", "--stage", "GOVERN", "--by", "dana-lee", "--statement", "x", expect=2)
    check("the stage after Assess cannot start under a block", "cannot start while a block" in t)
    t = H2("assess", "show")
    check("a system that decides about people is shown the fairness and rights assessments as not answered",
          "Fairness analysis" in t and "Impact on people's rights" in t and "NOT ANSWERED" in t)
    check("the list does not say what the law requires", "required" not in t.split("Assessments that may fit")[1].split("\n")[0].replace("whether one is required is for counsel", ""))
    H2("views", "regenerate")
    w2 = open(os.path.join(WS, "projects", "hire-bot-two", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("the waiting page says what keeps Assess from closing, and keeps the block line", "AIGRCeler to do before Assess can close" in w2 and "Stage block in force" in w2)
    t = H2("stage", "lift-block", "--id", "BLK-001", "--by", "dana-lee", "--statement", "I lift the block knowing what is open; this is a test with no real candidates.")
    check("lifting a block says where what it was lifted over is recorded", "carried to Govern" in t)
    t = H2("concern", "list", "--status", "open")
    check("what a lifted block rested on is carried into Govern as a concern", "for GOVERN" in t and "No bias audit is known" in t and "was lifted by" in t)
    H2("views", "regenerate")
    w3 = open(os.path.join(WS, "projects", "hire-bot-two", "00-status", "0-what-is-waiting.md"), encoding="utf-8").read()
    check("the waiting page keeps saying a block was lifted over open items", "A stage block was lifted by" in w3)
    # ------------------------------------------------------------------ dashboard
    import hashlib
    from aig import dashmod, stagemod, chasemod
    from aig.core import WS as WSD

    def tree_hash():
        out = {}
        for root_, dirs_, files_ in os.walk(WS):
            if os.path.abspath(root_) == os.path.join(WS, "dashboard") or os.path.join(WS, "dashboard") in os.path.abspath(root_):
                continue
            for f_ in files_:
                fp_ = os.path.join(root_, f_)
                out[fp_] = hashlib.sha256(open(fp_, "rb").read()).hexdigest()
        return out
    before = tree_hash()
    t = run("dashboard", "build")
    after = tree_hash()
    dash_dir = os.path.join(WS, "dashboard")
    idx = os.path.join(dash_dir, "index.html")
    check("the dashboard builds a page and a data file", os.path.exists(idx) and os.path.exists(os.path.join(dash_dir, "dashboard.json")))
    check("building the dashboard changes no record (it only reads)", before == after)
    html = open(idx, encoding="utf-8").read()
    dj = json.load(open(os.path.join(dash_dir, "dashboard.json"), encoding="utf-8"))
    check("the page is the fixed template, with its version, and no placeholder left", 'name="aig-template-version"' in html and "{{AIG_DATA}}" not in html and dj["template_version"])
    check("the page works offline: nothing is loaded from outside, and the page forbids it", not re.search(r'(src|href)=["\']https?://', html)
          and "default-src 'none'" in html and "connect-src" not in html and "<link " not in html)
    check("the page carries the AIGRCeler logo inside itself (light and dark), in the footer always and in the header only when the company set no logo of its own",
          html.count("data:image/png;base64,") >= 2 and "AIG-LOGO-BEGIN" in html and "class: 'foot-logo'" in html
          and "CFG.logo ? h('img', { src: CFG.logo, alt: '' }) : aigLogo()" in html)
    wd = WSD(WS)
    sy = [x for x in dj["systems"] if x["slug"] == "triage-bot"][0]
    blk, nums = stagemod.readiness(wd, wd.project("triage-bot"))
    check("the dashboard's required-controls figures equal the engine's own readiness", sy["go"]["done"] == nums["done"] and sy["go"]["required"] == nums["required"])
    check("the dashboard's follow-up list equals the chase list", len(sy["chase"]) == len(chasemod.build(wd, wd.project("triage-bot"))))
    check("every system in the workspace is on the dashboard", sorted(x["slug"] for x in dj["systems"]) == wd.project_slugs())
    check("every attention item names a severity and a place to go", all(a["severity"] in ("critical", "serious", "warning", "info") and a["text"] for a in dj["attention"]))
    check("the most serious items come first", [a["severity"] for a in dj["attention"]] == sorted([a["severity"] for a in dj["attention"]], key=lambda v: ["critical", "serious", "warning", "info"].index(v)))
    evil = '</script><img src=x onerror=alert(1)>'
    page, _d = dashmod.render({"x": evil, "config": {}})
    check("text from the records cannot close the data block or become markup", evil not in page and "\\u003c/script" in page)
    check("one history snapshot is kept for the day, and a second build the same day replaces it",
          len(os.listdir(os.path.join(dash_dir, "history"))) == 1 and (run("dashboard", "build") and len(os.listdir(os.path.join(dash_dir, "history"))) == 1))
    # company settings: look only, never structure
    json.dump({"title": "Acme view", "accent": "#aa0000", "hide": ["people", "not-a-section"], "logo": "../outside.png"}, open(os.path.join(dash_dir, "config.json"), "w"))
    run("dashboard", "build")
    cfg = json.load(open(os.path.join(dash_dir, "dashboard.json"), encoding="utf-8"))["config"]
    check("company settings change the title, accent and hidden sections, and unknown ones are ignored", cfg["title"] == "Acme view" and cfg["accent"] == "#aa0000" and cfg["hide"] == ["people"] and cfg["logo"] is None)
    json.dump({"accent": "red; background:url(x)"}, open(os.path.join(dash_dir, "config.json"), "w"))
    run("dashboard", "build")
    check("a company setting that is not a plain colour is ignored", json.load(open(os.path.join(dash_dir, "dashboard.json"), encoding="utf-8"))["config"]["accent"] is None)
    os.remove(os.path.join(dash_dir, "config.json"))
    # automatic rebuild after a change
    os.environ["AIGRCELER_NO_DASHBOARD"] = "0"
    os.remove(idx)
    run("person", "list")
    check("looking at records does not rebuild the dashboard", not os.path.exists(idx))
    run("person", "add", "--name", "Dash Test", "--contact", "dash@example.test", "--type", "internal")
    check("a change rebuilds the dashboard by itself", os.path.exists(idx))
    saved_t = dashmod.TEMPLATE
    dashmod.TEMPLATE = type(saved_t)(os.path.join(TMP, "no-such-template.html"))
    t = run("person", "add", "--name", "Dash Test Two", "--contact", "dash2@example.test", "--type", "internal")
    check("a dashboard that cannot be built never stops a record from being written",
          os.path.exists(os.path.join(dash_dir, "build-error.txt")) and any(p_["name"] == "Dash Test Two" for p_ in wd.load("people", [])))
    dashmod.TEMPLATE = saved_t
    run("dashboard", "build")
    check("a good build clears the error note", not os.path.exists(os.path.join(dash_dir, "build-error.txt")))
    from aig.core import clip as _clip
    _t = "Planned: the question of whether a rights assessment is required is with outside counsel; Auditor to prepare it once counsel replies. Not decided as unnecessary."
    _c = _clip(_t, 100)
    check("long record text is shortened at a word boundary with an ellipsis", _c.endswith("\u2026") and _t.startswith(_c[:-1]) and _t[len(_c) - 1] == " ")
    check("short record text is left alone", _clip("short note", 100) == "short note")
    os.environ["AIGRCELER_NO_DASHBOARD"] = "1"
    # the shipped sample has the same shape as a real build
    sample = json.load(open(os.path.join(HERE, "dashboard-sample.json"), encoding="utf-8"))
    def shape(o, depth=0):
        if isinstance(o, dict):
            return {k: shape(v, depth + 1) for k, v in o.items()} if depth < 2 else sorted(o.keys())
        return None
    real_sys = sy
    smp_sys = sample["systems"][0]
    check("the shipped sample dashboard data has the same fields as a real build",
          set(sample.keys()) == set(dj.keys()) | {"history"} and sorted(smp_sys.keys()) == sorted(real_sys.keys())
          and sorted(smp_sys["go"].keys()) == sorted(real_sys["go"].keys()) and sorted(smp_sys["profile"].keys()) == sorted(real_sys["profile"].keys())
          and sorted(smp_sys["counts"].keys()) == sorted(real_sys["counts"].keys()) and sorted(smp_sys["controls"].keys()) == sorted(real_sys["controls"].keys())
          and sorted(smp_sys["control_rows"][0].keys()) == sorted(real_sys["control_rows"][0].keys()) and (not real_sys["chase"] or sorted(smp_sys["chase"][0].keys()) == sorted(real_sys["chase"][0].keys())))
    if os.environ.get("AIG_DASH_OUT"):
        shutil.copy(idx, os.environ["AIG_DASH_OUT"])

finally:
    shutil.rmtree(TMP, ignore_errors=True)

bad = [n for n, ok in RESULTS if not ok]
print("\n%d checks, %d failed." % (len(RESULTS), len(bad)))
sys.exit(1 if bad else 0)
