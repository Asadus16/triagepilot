# TriagePilot

A support ticket triage automation that works for any business. One n8n workflow, one config block at the
top (business name, business type, category list, tone). Change those four things and it runs for a dental
clinic, a plumbing company, a SaaS product or a coffee shop, with no other edits.

## What it does

1. A ticket comes in through a webhook (from a contact form, a helpdesk, an email forwarding rule, anything
   that can POST JSON).
2. A shared secret in the request header is checked, so random requests are dropped before anything runs.
3. Gemini reads the ticket and returns urgency (low, medium, high), a topic from the business's own category
   list, and a draft reply, as validated structured JSON, not free text that has to be parsed and hoped for.
4. The ticket, its classification and the draft land in a Google Sheet, which is the support inbox tracker,
   with a status column starting at "pending approval."
5. A second, separate workflow watches the sheet. When a human changes a row's status to "approved," it marks
   the row ready to send. Sending itself (a Gmail node) is a deliberate later step, not built yet, since a
   real send should never happen without this project first being wired to a real inbox by the business
   owner.

## Why this design

- **No agent loop.** Classifying and drafting from the ticket text alone is one Gemini call, not a chain of
  tool calls. Adding a loop here would be complexity with no requirement behind it.
- **No paid lookup API.** Nothing here needs to search the web or enrich the ticket from outside, so nothing
  costs money beyond Gemini's free tier at demo volume.
- **Human approval before any send**, always. This is the same rule used in the Ember and Oak project's order
  lookups and in `app-security-baseline.md`: an AI system that can act on real customers needs a person in the
  loop before anything goes out.
- **Structured output, not parsed prose.** Gemini's `responseSchema` forces the exact shape below; there is no
  regex pulling a category out of a paragraph.

## Status

Confirmed with a live call to the real Gemini API (`gemini-3.5-flash-lite`), see `test/verify-gemini.sh` and
its recorded output in this file below. **The n8n workflow itself is not built yet.**

n8n has an official, first party MCP server built into every edition, including Cloud (confirmed against
n8n's own docs and blog, 2026-09-26, not from memory). It exposes tools such as `create_workflow`,
`update_workflow`, `list_workflows` and `execute_workflow`, backed by n8n's own REST API. Once the user
enables it (Settings, Instance-level MCP, then Connect a client, Claude Code) and connects this session to
it, the workflow gets built directly through those tools instead of hand written JSON or manual API calls,
so the real instance validates every step immediately.

n8n's own blog calls this feature "Public Preview" and names real rough edges: complex branching often needs
manual cleanup, node choice can go wrong when options overlap, and it can over build before refining. Its
output gets checked here rather than trusted blindly. See `build-spec.md` for the exact node by node plan it
gets built against.

## Verified Gemini call and response

Request (see `test/verify-gemini.sh` for the exact, runnable version):

```json
{
  "systemInstruction": { "parts": [{ "text": "You triage support tickets for Bright Smile Dental, a dental clinic. Categories: appointments, billing, insurance, general, other. Never invent facts not in the ticket. Draft a short, polite reply a staff member can edit before sending." }] },
  "contents": [{ "parts": [{ "text": "My appointment reminder said Tuesday but the office called it Wednesday, which is right? I have work off Tuesday." }] }],
  "generationConfig": {
    "responseMimeType": "application/json",
    "responseSchema": {
      "type": "OBJECT",
      "properties": {
        "urgency": { "type": "STRING", "enum": ["low", "medium", "high"] },
        "topic": { "type": "STRING", "enum": ["appointments", "billing", "insurance", "general", "other"] },
        "draft_reply": { "type": "STRING" }
      },
      "required": ["urgency", "topic", "draft_reply"]
    }
  }
}
```

Real response, unedited:

```json
{
  "urgency": "medium",
  "topic": "appointments",
  "draft_reply": "Hello, thank you for reaching out to Bright Smile Dental. We apologize for the confusion regarding your appointment day. Let us check our schedule and confirm the correct date for you right away."
}
```

Swapping only the business name, type and category list in `systemInstruction` is the entire per business
setup. Nothing else in the request changes.

## Setup, once n8n access is provided

1. n8n Cloud account, with Settings, Instance-level MCP, enabled, and Claude Code connected as a client
   (n8n's own "Connect a client" flow gives the exact command, then one OAuth sign in).
2. A Google account connected in n8n as a Google Sheets credential (OAuth, done inside n8n's UI).
3. The Gemini API key, added in n8n as an HTTP header credential or a generic credential, never hard coded in
   a node.
4. A webhook secret, any random string, set once in the config block and required in the request header.

## Known limits

- Sending real replies is not built. Approval only marks a row ready.
- Not connected to a real ticketing system yet. The webhook accepts whatever JSON shape is documented in
  `build-spec.md`, so any real contact form, helpdesk or email forwarding rule needs to be pointed at it in
  that shape.
- Gemini's free tier limit is 15 requests per minute for this model, same as the Ember and Oak project. Fine
  for a demo, worth a paid tier before real volume.
