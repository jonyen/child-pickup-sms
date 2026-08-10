# Child Pickup Confirmation App

Automated Saturday-night SMS confirmation workflow for Sunday child pickups, backed by Google Sheets.

> **Status: proposal.** The implementation and its test suite are complete, but
> this has not been deployed and is not confirming anyone's pickups today. The
> design, flows, and setup steps below describe how it is meant to run, not how
> it currently runs.

## Why

The church keeps a Google Sheet tracking who picks up each child on Sundays. Coordinators message parents individually on Saturday nights to confirm, and parents have to open a laptop or navigate the Sheets app on their phone to update the spreadsheet — not something most people want to do on a Saturday evening. This app would turn that into a simple text message exchange: parents get a confirmation SMS and reply with a quick "yes", a name change, or "not coming." The sheet updates itself.

## Storyboard

```
 SATURDAY 5:00 PM                        THE GOOGLE SHEET
 ┌─────────────────────────┐             ┌──────────────────────────────────┐
 │  ⏰ EventBridge fires   │             │  Pickup Schedule                 │
 │  flow: "send"           │             │                                 │
 │                         │  reads -->  │  Name       │ ON-GOING │ 4/13   │
 │  Lambda wakes up and    │             │  ───────────┼──────────┼──────  │
 │  scans the sheet for    │             │  Emma Lee   │ Grandma  │        │
 │  blank cells in the     │             │  Noah Lee   │ Grandma  │        │
 │  Sunday column          │             │  Olivia Kim │ Dad      │        │
 └─────────────────────────┘             └──────────────────────────────────┘
             │                                     blank = needs confirmation
             ▼
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  Groups children by pickup person, looks up parent phones in KidsInfo  │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │
         ┌──────────────────────┴──────────────────────┐
         ▼                                             ▼
 ┌──────────────────────────────┐   ┌──────────────────────────────────────┐
 │  📱 SMS to Lee parents       │   │  📱 SMS to Kim parents               │
 │                              │   │                                      │
 │  "Hi, this is the DMV        │   │  "Hi, this is the DMV                │
 │   Coordinator. One of you —  │   │   Coordinator. Confirming Dad is     │
 │   confirming Grandma is      │   │   picking up Olivia Kim tomorrow     │
 │   picking up Emma Lee and    │   │   (4/13). Reply YES to confirm,      │
 │   Noah Lee tomorrow (4/13).  │   │   or reply with who will pick        │
 │   Reply YES to confirm, or   │   │   them up instead."                  │
 │   reply with who will pick   │   │                                      │
 │   them up instead."          │   │                                      │
 └──────────────────────────────┘   └──────────────────────────────────────┘


 SCENARIO A: Parent confirms              SCENARIO B: Parent changes
 ┌─────────────────────────────┐           ┌─────────────────────────────┐
 │  📱 Mrs. Lee replies:       │           │  📱 Mrs. Kim replies:       │
 │                             │           │                             │
 │    "Yes"                    │           │    "Uncle Joe will get her"  │
 │                             │           │                             │
 └──────────────┬──────────────┘           └──────────────┬──────────────┘
                │                                         │
                ▼                                         ▼
 ┌─────────────────────────────┐           ┌─────────────────────────────┐
 │  Twilio webhook → Lambda    │           │  Twilio webhook → Lambda    │
 │                             │           │                             │
 │  Regex matches "Yes"        │           │  Regex doesn't match →      │
 │  → action: confirm          │           │  Gemini classifies:         │
 │                             │           │  → action: change           │
 │  Writes "Grandma" to the   │           │  → new_pickup_person:       │
 │  sheet for Emma & Noah      │           │    "Uncle Joe"              │
 │                             │           │                             │
 │  📱 Notifies Mr. Lee:       │           │  Writes "Uncle Joe" to the  │
 │  "FYI — Grandma picking up  │           │  sheet for Olivia            │
 │   Emma Lee and Noah Lee has │           │                             │
 │   been confirmed. No need   │           │  📱 Notifies Mr. Kim:       │
 │   to reply."                │           │  "FYI — pickup for Olivia   │
 │                             │           │   Kim has been changed to   │
 └──────────────┬──────────────┘           │   Uncle Joe. No need to     │
                │                          │   reply."                   │
                │                          └──────────────┬──────────────┘
                ▼                                         ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │  THE SHEET AFTER REPLIES                                            │
 │                                                                     │
 │  Name       │ ON-GOING │ 4/13                                       │
 │  ───────────┼──────────┼───────────                                 │
 │  Emma Lee   │ Grandma  │ Grandma      ✓ confirmed                   │
 │  Noah Lee   │ Grandma  │ Grandma      ✓ confirmed                   │
 │  Olivia Kim │ Dad      │ Uncle Joe    ✎ changed                     │
 └──────────────────────────────────────────────────────────────────────┘


 SCENARIO C: Ambiguous reply
 ┌─────────────────────────────┐           ┌─────────────────────────────┐
 │  📱 Parent replies:         │           │  📱 App texts back:         │
 │                             │    →      │                             │
 │    "What time again?"       │           │  "Sorry, didn't catch that  │
 │                             │           │   — could you reply YES to  │
 └─────────────────────────────┘           │   confirm Grandma, or just  │
    Cell stays blank, parent                │   the name of who's        │
    can reply again before cutoff           │   picking up?"             │
    No notification to other parent         └─────────────────────────────┘


 SCENARIO D: Child not coming
 ┌─────────────────────────────┐
 │  📱 Mrs. Park replies:      │
 │                             │
 │    "She's sick today,       │
 │     not coming"             │
 │                             │
 └──────────────┬──────────────┘
                │
                ▼
 ┌─────────────────────────────┐
 │  Twilio webhook → Lambda    │
 │                             │
 │  Gemini classifies:         │
 │  → action: absent           │
 │                             │
 │  Writes "ABSENT" to the     │
 │  sheet for the child        │
 │                             │
 │  📱 Notifies Mr. Park:      │
 │  "FYI — Lily Park marked    │
 │   as not coming. No need    │
 │   to reply."                │
 └─────────────────────────────┘


 SATURDAY 9:00 PM — CUTOFF
 ┌─────────────────────────────────────────────────────────────────────────┐
 │  ⏰ EventBridge fires flow: "cutoff"                                   │
 │                                                                        │
 │  Lambda scans for any remaining blank cells:                           │
 │                                                                        │
 │    blank cell found → writes "NO RESPONSE"                             │
 │                                                                        │
 │  Then builds a summary and emails organizers via SES:                  │
 │                                                                        │
 │  ┌───────────────────────────────────────────────────────────────────┐  │
 │  │  📧 Pickup Summary for Sunday 4/13                               │  │
 │  │                                                                  │  │
 │  │  CONFIRMED                                                       │  │
 │  │    Grandma → Emma Lee, Noah Lee                                  │  │
 │  │                                                                  │  │
 │  │  CHANGED                                                         │  │
 │  │    Uncle Joe → Olivia Kim  (was: Dad)                            │  │
 │  │                                                                  │  │
 │  │  ABSENT                                                          │  │
 │  │    Lily Park                                                     │  │
 │  │                                                                  │  │
 │  │  NO RESPONSE                                                     │  │
 │  │    (none this week — everyone replied!)                           │  │
 │  └───────────────────────────────────────────────────────────────────┘  │
 └─────────────────────────────────────────────────────────────────────────┘
```

## How It Works

```
                         Google Sheets
                    +-----------------------+
                    | Pickup Schedule tab   |
                    | All DMV KidsInfo tab  |
                    +-----------+-----------+
                                |
                    reads/writes via Sheets API
                                |
+-------------------+     +-----v------+     +------------------+
| EventBridge       |     |            |     | Twilio           |
| Sat 5pm ET (send) +---->+   Lambda   +---->+ Send SMS to      |
| Sat 9pm ET (cut)  |     |  handler   |<----+ parents          |
+-------------------+     |            |     +------------------+
                          +-----+------+
                                |
          +-----------+---------+---------+
          |           |                   |
    +-----v----+ +----v-----+  +----------v---------+
    | Send     | | Reply    |  | Cutoff             |
    | flow     | | flow     |  | flow               |
    +----------+ +----------+  +--------------------+
    Reads blank   Parses SMS    Reads column for
    rows, groups  (regex/LLM),  blank rows (no
    by pickup     writes result response), writes
    person,       to sheet      NO RESPONSE, sends
    sends SMS,                  summary email via
    adds next                   SES
    week column
```

### Saturday 5pm ET - Send Flow

1. Reads the **Pickup Schedule** tab and finds the Sunday column
2. Collects rows where the date cell is **blank** (no override yet)
3. Groups children by their default pickup person (`ON-GOING` column)
4. Looks up parent phone numbers from the **All DMV KidsInfo** tab
5. Sends one SMS per group to both parents: *"Confirming [person] is picking up [children] tomorrow. Reply YES or tell us who instead."*
6. Creates a column for **next week** if it doesn't already exist

### Parent Replies - Reply Flow

1. Parent's SMS hits the **Twilio webhook** -> API Gateway -> Lambda
2. Reads blank rows in the pickup schedule and matches children to the sender's phone via **KidsInfo**
3. Parses the reply:
   - **Fast path**: `YES` / `Y` / `OK` / etc. (regex) -> confirmed; `NO` / `NOT COMING` / `ABSENT` / etc. (regex) -> absent
   - **Slow path**: free-form text -> Google Gemini Flash classifies as confirm, change, absent, or ambiguous
4. Writes the result to the pickup date column:
   - **Confirmed**: writes the ON-GOING person's name (cell is no longer blank)
   - **Changed**: writes the new pickup person's name
   - **Absent**: writes `ABSENT` (child not coming)
5. If ambiguous, texts back asking for clarification
6. For confirm/change/absent, notifies the **other parent** that a response was received and no reply is needed

### Saturday 9pm ET - Cutoff Flow

1. Reads the Sunday column and finds rows that are still **blank** (no reply received)
2. Writes `NO RESPONSE` into those blank cells
3. Builds a summary from the column state:
   - **Confirmed**: cell value matches ON-GOING person
   - **Changed**: cell value differs from ON-GOING person
   - **Absent**: cell value is `ABSENT`
   - **No response**: cell was blank (now `NO RESPONSE`), includes parent contact info
4. Emails the summary to organizers via SES

## Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12 on AWS Lambda |
| Scheduling | EventBridge (two cron rules) |
| SMS webhook | API Gateway HTTP API |
| SMS | Twilio |
| Data store | Google Sheets (Pickup Schedule is the single source of truth) |
| Reply parsing | Regex fast path + Google Gemini Flash fallback |
| Email | AWS SES |
| Secrets | AWS Secrets Manager |
| IaC | AWS SAM (`template.yaml`) |

## Setup

### Prerequisites

- AWS account with SAM CLI installed
- Twilio account with an SMS-capable US number (~$1.15/mo)
- Google Cloud project with Sheets API enabled
- Google Gemini API key

### 1. Get Google OAuth credentials

Create OAuth 2.0 credentials in the Google Cloud Console (Desktop app type), then run the one-time consent flow to get a refresh token. Store as:

```json
{
  "client_id": "...",
  "client_secret": "...",
  "refresh_token": "..."
}
```

### 2. Store secrets in AWS Secrets Manager

```bash
aws secretsmanager create-secret --name child-pickup/twilio \
  --secret-string '{"account_sid":"AC...","auth_token":"..."}'

aws secretsmanager create-secret --name child-pickup/google-oauth \
  --secret-string '{"client_id":"...","client_secret":"...","refresh_token":"..."}'

aws secretsmanager create-secret --name child-pickup/gemini \
  --secret-string '{"api_key":"..."}'
```

### 3. Configure Twilio webhook

After deploying, paste the `WebhookUrl` output into your Twilio phone number's Messaging settings ("A message comes in" -> Webhook -> POST).

### 4. Deploy

```bash
sam build --use-container
sam deploy --guided
```

Parameters to set during guided deploy:
- `SpreadsheetId` - the ID from your Google Sheets URL
- `TwilioFromNumber` - your Twilio number in E.164 format
- `SummaryEmailRecipients` - comma-separated email addresses
- `SummaryEmailFrom` - verified SES sender address
- `DryRun` - start with `true`, flip to `false` after verifying logs

### 5. Verify SES

Verify your sender email/domain in SES. If in sandbox mode, also verify recipient addresses.

## Develop

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Project Structure

```
src/child_pickup/
  handler.py            # Lambda entrypoint, dispatches by event shape
  config.py             # Env vars + Secrets Manager
  send.py               # Saturday 5pm send flow
  reply.py              # Twilio webhook reply flow
  cutoff.py             # Saturday 9pm cutoff flow
  sheets.py             # Google Sheets API wrapper
  kids_info.py          # KidsInfo tab parser
  pickup_schedule.py    # Pickup Schedule reader + grouping + next-week column
  twilio_client.py      # Twilio SMS send + signature verification
  parser.py             # Reply parser (regex + Google Gemini Flash)
  email_client.py       # SES summary email
  models.py             # Child, Group dataclasses
  logging_setup.py      # Structured JSON logging
```
