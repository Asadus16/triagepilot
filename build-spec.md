# TriagePilot build spec — hybrid version

Replaces the earlier two-workflow, n8n-only spec. One workflow now, mirroring
claim-triage-agent's canvas: a webhook takes the ticket, a FastAPI call does the real
work, the result routes to one of four human review lanes, and a second trigger on the
same canvas handles the approval. Every node here does real work; nothing is here to
pad the node count.

## Prerequisite: the FastAPI service is running and reachable

This workflow calls a FastAPI service (`app/main.py` in this repo) over HTTP. It needs
to be deployed somewhere n8n Cloud can reach it (a small VPS, Render, Railway, Fly.io,
anywhere that runs Python), not on localhost. Get that URL before building the n8n side.

## Single workflow: node by node

1. **Webhook — Ticket Intake**
   - POST, path `triage/intake`.
2. **If — Validate**
   - Checks `customer_name`, `customer_email`, `subject`, `message` are all present and
     non empty. False: **Respond to Webhook**, status 400,
     `{ "error": "missing_fields" }`, stop.
3. **HTTP Request — Call FastAPI /triage**
   - POST `{{ $('Config').item.json.api_base_url }}/triage`
   - Header: `x-service-key` = the shared secret (n8n credential, never inline)
   - Body: `{ "customer_name": ..., "customer_email": ..., "subject": ..., "message": ... }`
     from the webhook body.
   - Returns the `Decision` object: `ticket_id`, `urgency`, `topic`, `route`,
     `draft_reply`, `confidence`, `reason_codes`.
4. **Switch — Route by outcome**
   - Four branches on `{{$json.route}}`: `auto_draft`, `escalate`, `billing_review`,
     `manager_review`.
5. **Four lane nodes** (Set, marked `manual`, same pattern as claim-triage-agent's
   Auto-approve payment / Adjuster approval / SIU review / Manual review):
   - **Auto-draft ready** — quick approval lane, no urgency.
   - **Escalate now** — emergency language, needs eyes immediately.
   - **Billing review** — money at stake, a person checks the numbers before it sends.
   - **Manager review** — legal risk, a repeat unresolved contact, or a low confidence
     read.
6. **Merge** the four lanes back together.
7. **Respond to Webhook**
   - 200, `{ "ticket_id": ..., "route": ..., "status": "pending approval" }`.

## Second trigger, same canvas: the approval step

8. **Webhook — Approval** (or a Form Trigger if the n8n plan supports it)
   - Takes `ticket_id` and `action` (`approved` / `edited` / `rejected`), optionally
     `note`.
9. **HTTP Request — Call FastAPI /human/{ticket_id}**
   - POST `{{ $('Config').item.json.api_base_url }}/human/{{$json.ticket_id}}`
   - Header: `x-service-key`, same credential as step 3.
   - Body: `{ "ticket_id": ..., "action": ..., "note": ... }`.
10. **Respond to Webhook**
    - 200, the updated status from FastAPI's response.

## Config node

One Set node, `Config`, read by every HTTP Request node above:
- `api_base_url`: where the FastAPI service is deployed.
- (The shared secret and Gemini key live in the FastAPI service's own `.env`, not here,
  n8n only needs the one shared secret to call it.)

## Credentials needed in n8n

- An HTTP header credential holding the FastAPI shared secret (`x-service-key`).
- Instance-level MCP enabled, with Claude Code connected as a client, so this gets
  built through n8n's own `create_workflow` tool.

## Resume checklist

1. Confirm the FastAPI service is deployed and `GET {base_url}/rules` returns the 14
   rule catalog.
2. `ToolSearch` for `n8n` to confirm the MCP tools are live.
3. `list_workflows`, check whether the old two-workflow version still exists; if so,
   ask before deleting it rather than assuming.
4. Build the single workflow above.
5. Test: POST a sample ticket to the intake webhook, confirm the response names a
   route, then POST an approval to the approval webhook with that `ticket_id` and
   confirm the status changes.
6. Compare what n8n's MCP server actually built against this spec and correct drift,
   the same caution as before, since it is officially "Public Preview."
7. Report back what was built, the test result, and anything corrected.
