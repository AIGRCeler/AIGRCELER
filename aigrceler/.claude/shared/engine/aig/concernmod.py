"""Concerns and proposals: what AIGRCeler noticed or recommends, kept where the next stage and the next session will see it.

A *concern* is something AIGRCeler noticed (for example a possible stand-in for a protected trait). It carries to a stage.
A *proposal* is something AIGRCeler recommends that only AI Governance can decide. It stays on the waiting page until decided.
Neither is a decision, and neither is written as anyone's words. They are labelled as AIGRCeler's own reading."""
from .core import clip
from .core import AigError, iso, today, resolve_actor, need_text, STAGES, norm_stage

KINDS = ("concern", "proposal")


def open_items(pr, kind=None):
    out = [c for c in pr.load("concerns", []) if c.get("status") == "open"]
    return [c for c in out if kind is None or c["kind"] == kind]


def cmd_add(args, ws):
    pr = ws.project(args.project)
    kind = (args.kind or "concern").lower()
    if kind not in KINDS:
        raise AigError("The kind must be one of: %s (--kind)." % ", ".join(KINDS))
    if not args.text or not args.text.strip():
        raise AigError("Say what was noticed or what is proposed (--text), in plain words, as AIGRCeler's own reading.")
    carry = norm_stage(args.carry_to or ("ASSESS" if kind == "concern" else ""))
    if carry and carry not in STAGES:
        raise AigError("--carry-to must be a stage: %s." % ", ".join(STAGES))
    items = pr.load("concerns", [])
    cid = pr.next_id("CON", "CON")
    items.append({"id": cid, "kind": kind, "text": args.text.strip(), "carry_to": carry or None,
                  "raised_by": "AIGRCeler (its own reading)", "asked_to_keep_by": args.asked_by or None,
                  "raised": iso(), "status": "open", "resolved": None, "resolution": None})
    pr.save("concerns", items)
    if kind == "proposal":
        print("Recorded %s. It shows on the waiting page as proposed by AIGRCeler until AI Governance decides." % cid)
    else:
        print("Recorded %s. It will be shown when %s starts and on the waiting page until it is dealt with." % (cid, carry or "the next stage"))


def cmd_resolve(args, ws):
    pr = ws.project(args.project)
    if not args.id or not args.note:
        raise AigError("Give the item (--id) and how it was dealt with (--note).")
    items = pr.load("concerns", [])
    c = next((x for x in items if x["id"] == args.id), None)
    if not c:
        raise AigError("No concern or proposal %s." % args.id)
    if c["status"] != "open":
        raise AigError("%s is already %s." % (args.id, c["status"]))
    a = resolve_actor(ws, args.by)
    text = None
    if c["kind"] == "proposal":
        # a proposal is a question for a decision-maker: the answer is theirs, in their words, in the journal
        if a.is_tool:
            raise AigError("A proposal is decided by a named person in AI Governance. Repeat with --by <their id> and --statement \"<their words>\".")
        text = need_text(args, "statement", "Deciding a proposal")
    c["status"] = "resolved"
    c["resolved"] = iso()
    c["resolution"] = args.note.strip()
    if text:
        c["decided_by"] = a.decided_by
        pr.journal().append("proposal_decided", ["project:" + pr.slug, c["id"]], a.decided_by,
                            "Decided on AIGRCeler's proposal %s: %s" % (c["id"], clip(args.note, 220)),
                            authority_basis=a.basis, labels=["unsigned"], text=text)
    pr.save("concerns", items)
    print("%s marked as dealt with%s." % (args.id, " and the decision is in the journal in %s's words" % a.name if text else ""))


def cmd_carry(args, ws):
    """Pass a concern on to a later stage on purpose, with the reason, instead of resolving it now."""
    pr = ws.project(args.project)
    if not args.id or not args.to or not args.reason:
        raise AigError("Give the concern (--id), the stage it moves to (--to) and the reason (--reason).")
    to = norm_stage(args.to)
    if to not in STAGES:
        raise AigError("--to must be a stage: %s." % ", ".join(STAGES))
    if len(args.reason.split()) < 5:
        raise AigError("Say in at least five words why it moves on (--reason): what is still unknown and who will deal with it there.")
    items = pr.load("concerns", [])
    c = next((x for x in items if x["id"] == args.id), None)
    if not c:
        raise AigError("No concern %s." % args.id)
    if c["status"] != "open":
        raise AigError("%s is already %s." % (args.id, c["status"]))
    if c["kind"] != "concern":
        raise AigError("%s is a proposal; it waits for a decision and is not carried." % args.id)
    if c.get("carry_to") and norm_stage(c["carry_to"]) in STAGES and STAGES.index(to) <= STAGES.index(norm_stage(c["carry_to"])):
        raise AigError("%s is for %s already; it can only move to a later stage." % (args.id, c["carry_to"]))
    c.setdefault("carried", []).append({"from": c.get("carry_to"), "to": to, "reason": args.reason.strip(), "time": iso()})
    c["carry_to"] = to
    pr.save("concerns", items)
    print("%s moves to %s. It stays open and will be shown there." % (args.id, to.capitalize()))


def cmd_list(args, ws):
    pr = ws.project(args.project)
    items = pr.load("concerns", [])
    shown = 0
    for c in items:
        if args.status and c["status"] != args.status:
            continue
        shown += 1
        print("%s  %-8s %-9s for %-8s %s%s" % (c["id"], c["kind"], c["status"], c.get("carry_to") or "-", c["text"],
                                                ("  [resolved: %s]" % c["resolution"]) if c.get("resolution") else ""))
    if not shown:
        print("Nothing recorded.")


def stage_text(pr, stage):
    """Lines to show when a stage starts: concerns raised earlier that this stage must take up."""
    out = []
    for c in open_items(pr, "concern"):
        if norm_stage(c.get("carry_to")) == stage:
            out.append("  - %s (%s)" % (c["text"], c["id"]))
    if not out:
        return ""
    return "Concerns carried in for %s (AIGRCeler's own reading; take each up and record how it was dealt with):\n%s" % (stage.capitalize(), "\n".join(out))
