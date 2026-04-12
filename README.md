# Child Pickup Confirmation App

Automated Saturday-night SMS confirmation workflow for Sunday child pickups, backed by Google Sheets.

See `docs/superpowers/specs/2026-04-11-child-pickup-design.md` for the full design.

## Develop

```
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest
```

## Deploy

Requires AWS SAM CLI.

```
sam build
sam deploy --guided
```
