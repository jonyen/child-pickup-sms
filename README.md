# Child Pickup Confirmation App

Automated Saturday-night SMS confirmation workflow for Sunday child pickups, backed by Google Sheets.

## How It Works

```
                         Google Sheets
                    +-----------------------+
                    | Pickup Schedule tab   |
                    | All DMV KidsInfo tab  |
                    | Pending Confirms tab  |
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
    Reads blank   Parses SMS    Marks NO RESPONSE
    rows, groups  (regex/LLM),  for unreplied rows,
    by pickup     writes new    sends summary email
    person,       pickup name   via SES
    sends SMS     to sheet
```

### Saturday 5pm ET - Send Flow

1. Reads the **Pickup Schedule** tab and finds the Sunday column
2. Collects rows where the date cell is **blank** (no override yet)
3. Groups children by their default pickup person (`ON-GOING` column)
4. Looks up parent phone numbers from the **All DMV KidsInfo** tab
5. Sends one SMS per group to both parents: *"Confirming [person] is picking up [children] tomorrow. Reply YES or tell us who instead."*
6. Writes a pending confirmation row to the **Pending Confirmations** tab

### Parent Replies - Reply Flow

1. Parent's SMS hits the **Twilio webhook** -> API Gateway -> Lambda
2. Matches the reply to a pending confirmation by phone number
3. Parses the reply:
   - **Fast path**: `YES` / `Y` / `OK` / etc. (regex) -> confirmed
   - **Slow path**: free-form text -> Claude Haiku classifies as confirm, change, or ambiguous
4. Writes the result back to the pickup date column
5. If ambiguous, texts back asking for clarification

### Saturday 9pm ET - Cutoff Flow

1. Finds any still-pending confirmations
2. Writes `NO RESPONSE` into their pickup cells
3. Emails a summary to organizers via SES: confirmed, changed, no-response, and any errors

## Stack

| Component | Technology |
|-----------|-----------|
| Runtime | Python 3.12 on AWS Lambda |
| Scheduling | EventBridge (two cron rules) |
| SMS webhook | API Gateway HTTP API |
| SMS | Twilio |
| Data store | Google Sheets (source of truth + pending state) |
| Reply parsing | Regex fast path + Claude Haiku fallback |
| Email | AWS SES |
| Secrets | AWS Secrets Manager |
| IaC | AWS SAM (`template.yaml`) |

## Setup

### Prerequisites

- AWS account with SAM CLI installed
- Twilio account with an SMS-capable US number (~$1.15/mo)
- Google Cloud project with Sheets API enabled
- Anthropic API key

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

aws secretsmanager create-secret --name child-pickup/anthropic \
  --secret-string '{"api_key":"sk-ant-..."}'
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
  pickup_schedule.py    # Pickup Schedule reader + grouping
  pending.py            # Pending Confirmations tab store
  twilio_client.py      # Twilio SMS send + signature verification
  parser.py             # Reply parser (regex + Claude Haiku)
  email_client.py       # SES summary email
  models.py             # Child, Group, PendingConfirmation
  logging_setup.py      # Structured JSON logging
```
