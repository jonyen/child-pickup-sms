# Child Pickup Confirmation App — Design

**Date:** 2026-04-11
**Status:** Approved (pending user spec review)

## Purpose

Automate the weekly child pickup confirmation workflow for DMV. The source of truth is a Google Sheet with a `Pickup Schedule` tab (one row per child, one column per Sunday pickup date) and an `All DMV KidsInfo` tab (parent names and phone numbers). Every Saturday at 5pm ET, the app texts parents whose child has no override in the next day's column, asks them to confirm that the default pickup person (`ON-GOING` column value) will pick up their child, and writes replies back into the sheet. At 9pm ET, unresponded rows are marked `NO RESPONSE` and a summary email is sent to organizers.

## Scope

**In scope:**
- Reading from and writing to the existing Google Sheet.
- Weekly send on Saturday 5pm ET for Sunday pickup.
- Parsing free-form SMS replies (YES-variant regex fast path, Claude Haiku fallback).
- Updating the target Sunday column with the resolved pickup person.
- 9pm cutoff with `NO RESPONSE` write-back and summary email.

**Out of scope:**
- A web dashboard or admin UI. (Organizers inspect and edit the sheet directly.)
- Pickup scheduling logic beyond one pickup date per run.
- Maintaining a database of sitter phone numbers. Parents are always the confirmers.
- Ad-hoc (non-Sunday) pickup events. Only Sunday columns are processed.

## Stack

- **Runtime:** Python 3.12 on AWS Lambda
- **Entry points:** AWS API Gateway (HTTP, `POST /sms`) + AWS EventBridge (two schedule rules: send and cutoff)
- **SMS:** Twilio (one SMS-capable US number, REST API for sending, webhook for receiving)
- **State:** Google Sheets — new `Pending Confirmations` tab in the same spreadsheet
- **LLM fallback:** Anthropic Claude Haiku for parsing non-obvious replies
- **Email:** AWS SES for cutoff summary
- **Secrets:** AWS Secrets Manager (Twilio creds, Google service account JSON, Anthropic key)
- **Infrastructure as code:** AWS SAM (`template.yaml`)

## Architecture

A single Lambda function (`child-pickup-handler`) handles all three flows by dispatching on event shape:

1. **EventBridge schedule — send** (Sat 5pm ET): reads pickup schedule, groups blank rows by `ON-GOING` value, looks up parent phones, sends Twilio SMS, writes `Pending Confirmations` rows.
2. **API Gateway POST `/sms`**: Twilio posts incoming parent replies; the handler validates the signature, matches the reply to a pending row by `From` number, parses the body, writes the resolved value to the target date column, marks the pending row resolved.
3. **EventBridge schedule — cutoff** (Sat 9pm ET): finds still-pending rows, writes `NO RESPONSE` to their cells, emails a summary via SES.

### Module layout

```
src/
  handler.py          # Lambda entrypoint; dispatches by event shape
  sheets.py           # Google Sheets client, row grouping, write helpers
  kids_info.py        # Parse All DMV KidsInfo tab into lookup by child name
  twilio_client.py    # Send SMS, validate incoming webhook signature, compose bodies
  parser.py           # Regex fast path + Claude Haiku fallback
  pending.py          # Read/write the Pending Confirmations tab
  cutoff.py           # Cutoff flow logic
  send.py             # Send flow logic
  reply.py            # Reply flow logic
  config.py           # Env vars + Secrets Manager fetching with cold-start cache
  email_client.py     # SES summary email composition and send
  logging_setup.py    # Structured JSON logging config
tests/
  ...                 # pytest with mocked Google Sheets / Twilio / Claude
template.yaml         # SAM template
```

## Data model

### Existing: `Pickup Schedule` tab (read + write target date column only)

Columns: `Last Name`, `Full Name`, `ON-GOING`, then one column per Sunday date (header format `M/D`, e.g. `4/12`).

- `Full Name` is the join key to `All DMV KidsInfo`.
- `ON-GOING` holds the default pickup person(s) as free-form text (e.g. `"Hanseul or Deandra"`, `"Shara"`, `"A2N/Launch sitters"`).
- A **blank** date cell means the default (`ON-GOING`) person is picking up. A **filled** date cell is an override.

### Existing: `All DMV KidsInfo` tab (read-only)

Relevant columns: `Name (First & Last)`, `Mother`, `Mother's phone #`, `Father`, `Father's phone #`. Joined to Pickup Schedule by full name.

### New: `Pending Confirmations` tab

Primary state for pending and historical confirmation requests.

| Column | Purpose |
|---|---|
| `id` | UUID, primary key |
| `sent_at` | ISO8601 timestamp when SMS sent |
| `pickup_date` | The Sunday date (ISO: `2026-04-12`) |
| `sheet_row_numbers` | Comma-separated row numbers in Pickup Schedule for the children in this group |
| `children_names` | Comma-separated full names |
| `ongoing_person` | The exact value from the ON-GOING column |
| `parent_phones` | Comma-separated E.164 numbers that received the SMS |
| `parent_names` | Comma-separated names (for summary email) |
| `status` | `pending` / `confirmed` / `changed` / `no_response` |
| `resolved_at` | ISO8601 when reply received or cutoff hit |
| `reply_text` | Raw text of parent's reply (for audit) |
| `resolved_value` | What got written to the pickup cell (empty if confirmed, new name if changed, `NO RESPONSE` if timed out) |

## Send flow (Saturday 5pm ET)

**Trigger:** EventBridge rule `child-pickup-send`, cron `0 21 ? * SAT *` (21:00 UTC ≈ 5pm ET; see DST note in Open Questions).

**Steps:**

1. **Determine target date** = tomorrow (Sunday). Format as `M/D` to match sheet column header (e.g. `4/12`).
2. **Load Pickup Schedule.** Find the column whose header exactly matches the target date. If not found, log error, send alert email via SES, abort.
3. **Load KidsInfo** into a lookup: `full_name → {mother, mother_phone, father, father_phone}`.
4. **Collect blank rows** in the target column. For each, capture row number, child full name, `ON-GOING` value.
5. **Group by `ON-GOING` value** (verbatim string match). All children sharing the same ongoing-person string form one group. Within a group, collect parent phones from KidsInfo across all children and dedupe — mother and father each appear once per group regardless of how many of their children are in it.
6. **Idempotency check:** skip any group whose `(pickup_date, sheet_row_numbers)` is already represented by a pending or resolved row in `Pending Confirmations`.
7. **For each group:**
   - Compose SMS body (templates below).
   - Append a `Pending Confirmations` row with `status=pending`.
   - Send SMS to each parent phone via Twilio. Retry once on failure; on permanent failure, note the failed number in logs and in the send-time error list.
8. **Send-time errors** (missing child in KidsInfo, missing both parent phones, Twilio send failures) are collected and passed forward to be included in the cutoff summary email.

**SMS body templates:**

Single child, single pickup person:
> `Hi, this is the DMV pickup coordinator. Confirming {person} is picking up {child} tomorrow ({M/D}). Reply YES to confirm, or reply with who will pick {him/her/them} up instead.`

Multiple children, same pickup person:
> `Hi, this is the DMV pickup coordinator. Confirming {person} is picking up {child1}, {child2}, and {child3} tomorrow ({M/D}). Reply YES to confirm, or reply with who will pick them up instead.`

Two-parent recipient (same message sent to both mother and father):
> `Hi, this is the DMV pickup coordinator. One of you — confirming {person} is picking up {child} tomorrow ({M/D}). Reply YES to confirm, or reply with who will pick {him/her/them} up instead.`

The gendered pronoun is hard to get right from a spreadsheet; the spec uses "them" as a safe default.

## Reply flow (Twilio webhook → API Gateway → Lambda)

**Trigger:** Twilio `POST /sms` on API Gateway when a parent replies. Payload is form-encoded: `From`, `Body`, `MessageSid`, signature header.

**Steps:**

1. **Verify Twilio signature** using the `X-Twilio-Signature` header and auth token. Reject non-matching requests with 403.
2. **Normalize `From`** to E.164.
3. **Look up pending confirmation:** query `Pending Confirmations` for rows where `status=pending`, `pickup_date` = the coming Sunday, and `parent_phones` contains the `From` number. If multiple match, take most recent by `sent_at`. If none match, reply with `"Thanks, but we don't have a pending pickup confirmation for this number right now."` and exit.
4. **Parse the reply:**
   - **Fast path (regex):** strip whitespace and punctuation, uppercase, match against `^(YES|Y|YEP|YEAH|YUP|CONFIRMED?|OK|OKAY|SURE)$`. If match, treat as confirmation.
   - **LLM fallback:** otherwise call Claude Haiku with the ongoing person, children's names, and reply text, requesting structured JSON `{action: "confirm" | "change" | "ambiguous", new_pickup_person: string | null}`.
   - **Confirm** → write empty string (blank) to pickup cells (preserves the "default ongoing" state), set `status=confirmed`, `resolved_value=""`.
   - **Change** → write `new_pickup_person` to pickup cells, set `status=changed`, `resolved_value=new_pickup_person`.
   - **Ambiguous** → return TwiML `<Message>Sorry, didn't catch that — could you reply YES to confirm {ongoing_person}, or just the name of who's picking up?</Message>` and leave the row `pending`.
5. **Update Pickup Schedule:** for each row number in `sheet_row_numbers`, write the resolved value into the target date column.
6. **Update pending row:** `status`, `resolved_at`, `reply_text`, `resolved_value`.
7. **Respond to Twilio** with TwiML — empty `<Response/>` for confirmations and changes, `<Message>...</Message>` for ambiguous prompts.

**Reply-flow edge cases:**

- **Parent replies twice within 30 minutes:** second reply wins; re-open the pending row and re-resolve.
- **Parent replies more than 30 minutes after resolution:** no-op + auto-response `"Already recorded as {resolved_value or 'confirmed'}. Contact the coordinator if this needs to change."`
- **Parent replies after cutoff:** auto-response `"The confirmation window closed at 9pm. Please contact the coordinator."` No sheet write.
- **Sender isn't in the pending row's `parent_phones`:** no-op, log only. (Shouldn't happen.)

## Cutoff flow (Saturday 9pm ET)

**Trigger:** EventBridge rule `child-pickup-cutoff`, cron `0 1 ? * SUN *` (01:00 UTC Sunday ≈ 9pm ET Saturday).

**Steps:**

1. **Find pending rows** in `Pending Confirmations` with `status=pending` AND `pickup_date` = tomorrow's Sunday (date passed explicitly by the handler).
2. **For each pending row:** write `NO RESPONSE` into each target date cell (by `sheet_row_numbers`); update row to `status=no_response`, `resolved_at=now`, `resolved_value="NO RESPONSE"`.
3. **Compose summary email** — always sent, even with zero non-responders, so recipients get a predictable digest. Contents:
   - Pickup date
   - Confirmed groups (pickup person, children)
   - Changed groups (new person, children, original ongoing person)
   - Non-responders: children names, ongoing person, parent names + phones
   - Send-time errors (missing phones, Twilio failures)
4. **Send via SES** to `SUMMARY_EMAIL_RECIPIENTS`. Retry once on transient failure; log loudly on permanent failure (sheet data is still correct).
5. **Idempotency:** skip rows already in a terminal status.

**Cutoff edge case:** if clock skew causes the reply flow and cutoff flow to race on the same row, the loser sees a non-`pending` status and skips. If a parent replies after the row is marked `NO RESPONSE`, the reply flow auto-responds about the closed window and does not overwrite.

## Configuration

### Environment variables
- `SPREADSHEET_ID` — Google Sheets ID
- `PICKUP_TAB_NAME` — default `Pickup Schedule` (confirm exact name during setup)
- `KIDS_INFO_TAB_NAME` — default `All DMV KidsInfo`
- `PENDING_TAB_NAME` — default `Pending Confirmations`
- `TWILIO_FROM_NUMBER` — E.164
- `SUMMARY_EMAIL_RECIPIENTS` — comma-separated list (populated at deploy time)
- `SUMMARY_EMAIL_FROM` — verified SES sender
- `COORDINATOR_NAME` — default `DMV pickup coordinator`
- `TIMEZONE` — `America/New_York`
- `LOG_LEVEL` — `INFO`
- `DRY_RUN` — `true`/`false`; when `true`, no SMS / email / sheet writes, just logging

### Secrets (AWS Secrets Manager)
- `child-pickup/twilio` — `{account_sid, auth_token}`
- `child-pickup/google-service-account` — full service account JSON
- `child-pickup/anthropic` — `{api_key}`

### External setup (manual, one-time)
- **Google:** create a GCP project, enable Sheets API, create a service account, download JSON into Secrets Manager, share the spreadsheet with the service account email as Editor.
- **Twilio:** buy an SMS-capable US number, set its messaging webhook to `https://{api-gw-domain}/sms`.
- **SES:** verify sender domain or address; if in sandbox, also verify recipient addresses or request production access.

## Error handling

- **Send flow:** per-group errors (missing phones, send failure) isolated and collected. One bad group never aborts the whole send.
- **Reply flow:** any exception still returns TwiML 200 with empty response to prevent Twilio retries confusing the parent. Errors logged to CloudWatch.
- **Cutoff flow:** per-row errors isolated. SES send retried once.
- **Sheets API transients (429, 5xx):** exponential backoff with jitter, up to 3 retries via the `google-api-python-client` built-in helpers.

## Observability

- **Structured JSON logs** to CloudWatch, with `pending_id`, `pickup_date`, `child_names`, `flow` fields on every event.
- **CloudWatch Alarms:**
  - Lambda error rate > 0 → SNS → email.
  - Zero `SendFlowGroupsProcessed` custom metric on a Saturday → SNS → email. Protects against silent "ran but did nothing" failures.
- Saved CloudWatch Log Insights queries for common investigations.

## Testing

- **Unit tests** (pytest, mocked deps):
  - `parser.py`: regex variants, Claude fallback (mocked), edge cases (mixed language, multiple names).
  - `sheets.py`: blank detection, grouping, header matching.
  - `twilio_client.py`: message composition for 1-child, multi-child, two-parent.
  - `handler.py`: event-shape dispatch.
- **Integration tests** against a test spreadsheet (copy with fake phones) + Twilio test credentials; runnable via `sam local invoke` and in a CI PR job.
- **Dry-run mode** (`DRY_RUN=true`) reads everything and logs intended actions without any side effects.
- **First real run:** dry run → single-row live test → full live run.

## Open questions / TODOs at deploy time

- **Exact Pickup Schedule tab name:** user to confirm before first deploy.
- **Initial `SUMMARY_EMAIL_RECIPIENTS` list:** user will populate at deploy time.
- **DST handling for EventBridge cron:** cron expressions in EventBridge are UTC. The fixed offsets above (`21:00` for send, `01:00 SUN` for cutoff) are correct for EDT. During EST (Nov–Mar) they shift by one hour — send becomes 4pm ET, cutoff becomes 8pm ET. Acceptable for MVP; if not, we add a conditional or switch to EventBridge Scheduler with `timezone` support (preferred long-term).
- **Twilio number provisioning:** user to purchase before first deploy.
- **SES sender verification and production-mode request:** user to complete before first deploy.
