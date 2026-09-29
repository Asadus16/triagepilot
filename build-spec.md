# TriagePilot build spec

Exact node by node plan, built directly on the n8n instance through its REST API the moment an instance URL
and API key are available. Nothing here is guessed at blindly: the Gemini call in step 4 is the same one
verified live in `README.md` and `test/verify-gemini.sh`, and every other node uses n8n's own standard,
documented node types. Any parameter that turns out wrong on the real instance gets fixed immediately against
the real error, not guessed at twice.

## Workflow 1: Intake — exact node parameters

1. **Webhook**
   - HTTP Method: `POST`
   - Path: `triage/intake`
   - Response Mode: `Using 'Respond to Webhook' Node`
2. **If — Check secret**
   - Condition: `{{$json.headers['x-triage-secret']}}` is equal to `{{$node["Config"].json.webhook_secret}}`
   - False branch: goes straight to a **Respond to Webhook** node returning status 401,
     `{ "error": "unauthorized" }`, and nothing downstream runs.
3. **Set — Config** (the only node a new business ever has to edit)
   - `business_name` (string): e.g. `Bright Smile Dental`
   - `business_type` (string): e.g. `a dental clinic`
   - `categories` (string, comma separated): e.g. `appointments,billing,insurance,general,other`
   - `webhook_secret` (string): a random value, matches what the caller sends
   - `sheet_id` (string): the Google Sheet's ID from its URL
   - `sheet_tab` (string): e.g. `Tickets`
4. **HTTP Request — Gemini**
   - Method: `POST`
   - URL: `https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent`
   - Authentication: Generic Credential, Query Auth, `key` = the Gemini API key (n8n credential, never typed
     into the node body)
   - Body (JSON), with `{{ }}` filled from the Config node and the incoming webhook item exactly as proven
     live in `test/verify-gemini.sh`:
     ```json
     {
       "systemInstruction": { "parts": [{ "text": "You triage support tickets for {{ $('Config').item.json.business_name }}, {{ $('Config').item.json.business_type }}. Categories: {{ $('Config').item.json.categories }}. Never invent facts not in the ticket. Draft a short, polite reply a staff member can edit before sending." }] },
       "contents": [{ "parts": [{ "text": "{{ $json.body.subject }}: {{ $json.body.message }}" }] }],
       "generationConfig": {
         "responseMimeType": "application/json",
         "responseSchema": {
           "type": "OBJECT",
           "properties": {
             "urgency": { "type": "STRING", "enum": ["low", "medium", "high"] },
             "topic": { "type": "STRING", "enum": "{{ $('Config').item.json.categories.split(',') }}" },
             "draft_reply": { "type": "STRING" }
           },
           "required": ["urgency", "topic", "draft_reply"]
         }
       }
     }
     ```
5. **Set / Code — Parse Gemini reply**
   - Parses `{{$json.candidates[0].content.parts[0].text}}` (a JSON string) into three fields:
     `urgency`, `topic`, `draft_reply`.
6. **Google Sheets — Append row**
   - Spreadsheet: `{{ $('Config').item.json.sheet_id }}`, Sheet: `{{ $('Config').item.json.sheet_tab }}`
   - Columns, matching `sheet-template.csv` exactly: `ticket_id` (a generated uuid),
     `received_at` (`{{$now}}`), `customer_name`, `customer_email`, `subject`, `message` (from the webhook
     body), `urgency`, `topic`, `draft_reply` (from step 5), `status` (literal `pending approval`),
     `approved_at` (blank).
7. **Respond to Webhook**
   - Status 200, body `{ "received": true }`.

## Workflow 2: Approval watcher — exact node parameters

1. **Google Sheets Trigger**
   - Poll, Trigger On: Row Update, same spreadsheet and tab as above.
2. **If**
   - Condition: `{{$json.status}}` is equal to `approved`. False: stop, no further nodes.
3. **Set**
   - `approved_at` = `{{$now}}`, `status` = `ready to send`.
4. **Google Sheets — Update row**
   - Matches on `ticket_id`, writes back `status` and `approved_at` only.

Sending itself (a Gmail node reading `ready to send` rows) is a deliberate later addition, not built now, see
`README.md`.

## Resume checklist (for whichever session has the n8n MCP connection)

1. `ToolSearch` for `n8n` to confirm the MCP tools are live (`create_workflow`, `list_workflows`, etc.); if
   nothing matches, MCP is not connected on this account yet, stop and tell the user.
2. `list_workflows` first, so an existing partial attempt is not duplicated.
3. Build Workflow 1 exactly as specified above, using `Bright Smile Dental` as the demo Config values
   (already verified live, see README), then Workflow 2.
4. Send one real test POST to the webhook path with a sample ticket, confirm a correctly filled row appears
   in the Sheet with `status = pending approval`.
5. Manually change that row's status to `approved` in the Sheet, confirm Workflow 2 flips it to
   `ready to send` with an `approved_at` timestamp.
6. Compare what n8n's MCP server actually built against this spec node by node. It is officially "Public
   Preview" with known rough edges on branching and node choice (see README), so fix anything that drifted
   rather than assuming it matches. Do not redesign the workflow, only correct it to match this spec.
7. Report back plainly what was built, what the test run showed, and anything that had to be corrected.

## Credentials needed in n8n (set up inside n8n's UI, not in this repo)
- Gemini API key, as a generic credential or HTTP header credential.
- Google Sheets OAuth2 connection.
- The webhook secret, any random string, entered once into the Config node.
- Instance-level MCP enabled (Settings, Instance-level MCP), with Claude Code connected as a client, so this
  gets built through n8n's own `create_workflow` / `update_workflow` tools rather than hand written JSON.

## What is verified vs what is not yet

Verified against the live Gemini API: the exact request shape, the structured output schema, and that
swapping only the business name, type and categories is the entire per business change (see README). Verified
against n8n's own docs and blog (2026-09-26): the MCP server is official, ships in every edition including
Cloud, and exposes workflow build tools, though n8n's own blog calls it "Public Preview" with real rough
edges on complex branching and node selection. Not verified yet: how it actually behaves building this
specific workflow, since that needs the real connection. Its output gets checked step by step once building
starts, not trusted blindly.
