# TriagePilot

A support ticket triage system that works for any business. One config block (business
name, type, category list) is the whole per business setup. Built as a hybrid, the same
pattern as its two sibling portfolio projects, **claim-triage-agent** and
**analytics-agent**: **n8n orchestrates** the workflow and the human review step,
while a **FastAPI service holds the deterministic engine** and the audit trail, because
n8n Cloud's Code node can't import a library or make a network call, so real logic has
to live somewhere that can.

## What changed from the first version

The first version was n8n plus Gemini plus a Google Sheet, with no backend, deliberately
the smallest stack for the job. It was rebuilt into this hybrid so it would carry the
same real weight as its two siblings: **the model never decides**, a rule engine does,
with a readable catalog, a full audit trail, and a golden regression suite, not a
single LLM call that hopes for the best. That is a genuine architecture change, not
extra nodes added for appearance; every node in the resulting n8n workflow does real
work.

## What makes it different

- **The model never decides.** Gemini only extracts signals from the ticket (sentiment,
  whether it mentions an emergency, money, legal risk or a cancellation, and a topic
  guess), validated against a strict schema. A 14 rule catalog (`app/rules/catalog.py`)
  decides urgency and routes the ticket, deterministically. `GET /rules` returns the
  whole catalog for a client to review.
- **Four human review lanes, not one**, chosen by the rules that fired: `auto_draft`
  (nothing flagged, a quick approval), `escalate` (emergency or safety language),
  `billing_review` (money at stake), `manager_review` (legal risk, a repeat unresolved
  contact, or an extraction too unsure to trust). Escalation always outranks a billing
  question in the same ticket.
- **A narration guardrail.** After Gemini drafts a reply, the draft is checked against
  what the engine actually decided; language implying an emergency or legal risk the
  engine never flagged gets replaced with a neutral draft instead of shipping an
  inconsistent reply.
- **A real repeat contact check** (`app/store.py`), not a guess: the same email writing
  in again within 48 hours is a genuine database lookup against past tickets, and it
  routes to a manager.
- **A golden regression suite** (`data/golden/cases.json`, `app/golden.py`), 8 hand
  verified cases run against the rule engine directly, the true oracle for this system.
  `GET /golden/run` and CI fail if a route or an urgency silently changes.
- **Full audit trail** (SQLite, `app/store.py`): every ticket, its decision, every rule
  result, and every human review, reconstructable by `ticket_id`.
- **Record/replay of Gemini calls** so tests are fast, free and deterministic and the
  demo runs with no live key.

## Architecture

```
Ticket (n8n webhook)
  -> FastAPI POST /triage
       - Gemini extracts signals only (validated schema, fails closed on bad JSON)
       - rule engine (14 rules) -> flags -> route + urgency
       - Gemini drafts a reply -> narration guardrail checks it against the flags
       - saved to the audit trail
  -> n8n routes by `route`:
       auto_draft      -> quick approval lane
       escalate        -> emergency lane, needs eyes now
       billing_review   -> a person checks the numbers
       manager_review   -> legal risk, repeat contact, or low confidence
  -> human approves, edits or rejects -> n8n POST /human/{ticket_id}
  -> status becomes "ready to send" or "rejected", recorded in the audit trail
```

## Run it

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # set SERVICE_API_KEY; GEMINI_API_KEY optional in replay mode
pytest                        # 11 tests incl. the rule engine, the golden gate and API auth
uvicorn app.main:app --reload --port 8099
```

`GET /rules` and `GET /golden/run` (with the `x-service-key` header) need no Gemini key.
`POST /triage` needs `LLM_MODE=live` or `record` plus a real `GEMINI_API_KEY`, or a
matching recorded cassette in `data/cassettes/` for `replay` mode.

## n8n workflow

One workflow, two real entry points on the same canvas: the ticket intake webhook, and
the human review step. See `build-spec.md` for the exact node by node plan. It is built
directly on the n8n instance through n8n's own MCP server once connected, the same way
Ember and Oak's sibling projects were, not a blind hand written workflow file.

## Known limits

- Sending a real reply is not built. Approval only marks a ticket ready to send.
- The 14 rule catalog is a real, readable starting point, not exhaustive; a real
  deployment would extend it with the business's actual escalation policy.
- Gemini's free tier limit is 15 requests per minute for this model. Fine for a demo,
  worth a paid tier before real volume.
- Cover and ERD images (`docs/`) reflect the earlier, Sheet based version and need
  regenerating against the new SQLite schema.
