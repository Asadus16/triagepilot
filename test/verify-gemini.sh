#!/usr/bin/env bash
# Verifies the exact Gemini call TriagePilot's n8n workflow will make, against the real API.
# Usage: GEMINI_API_KEY=... BUSINESS_NAME="Bright Smile Dental" BUSINESS_TYPE="a dental clinic" \
#        CATEGORIES="appointments,billing,insurance,general,other" \
#        TICKET_TEXT="..." ./verify-gemini.sh
set -euo pipefail

: "${GEMINI_API_KEY:?Set GEMINI_API_KEY}"
BUSINESS_NAME="${BUSINESS_NAME:-Bright Smile Dental}"
BUSINESS_TYPE="${BUSINESS_TYPE:-a dental clinic}"
CATEGORIES="${CATEGORIES:-appointments,billing,insurance,general,other}"
TICKET_TEXT="${TICKET_TEXT:-My appointment reminder said Tuesday but the office called it Wednesday, which is right? I have work off Tuesday.}"
MODEL="${MODEL:-gemini-3.5-flash-lite}"

# Turn "a,b,c" into a JSON array of quoted strings, for both the instructions and the schema enum.
CATEGORY_JSON=$(python3 -c "import json,sys; print(json.dumps(sys.argv[1].split(',')))" "$CATEGORIES")
CATEGORY_LIST=$(echo "$CATEGORIES" | tr ',' ' ')

BODY=$(python3 -c "
import json, sys
system_text = f'You triage support tickets for {sys.argv[1]}, {sys.argv[2]}. Categories: {sys.argv[3]}. Never invent facts not in the ticket. Draft a short, polite reply a staff member can edit before sending.'
print(json.dumps({
  'systemInstruction': {'parts': [{'text': system_text}]},
  'contents': [{'parts': [{'text': sys.argv[4]}]}],
  'generationConfig': {
    'responseMimeType': 'application/json',
    'responseSchema': {
      'type': 'OBJECT',
      'properties': {
        'urgency': {'type': 'STRING', 'enum': ['low', 'medium', 'high']},
        'topic': {'type': 'STRING', 'enum': json.loads(sys.argv[5])},
        'draft_reply': {'type': 'STRING'}
      },
      'required': ['urgency', 'topic', 'draft_reply']
    }
  }
}))
" "$BUSINESS_NAME" "$BUSINESS_TYPE" "$CATEGORY_LIST" "$TICKET_TEXT" "$CATEGORY_JSON")

curl -s -X POST "https://generativelanguage.googleapis.com/v1beta/models/${MODEL}:generateContent?key=${GEMINI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d "$BODY" | python3 -c "
import json, sys
d = json.load(sys.stdin)
if 'candidates' not in d:
    print('ERROR:', json.dumps(d, indent=2)); sys.exit(1)
print(d['candidates'][0]['content']['parts'][0]['text'])
"
