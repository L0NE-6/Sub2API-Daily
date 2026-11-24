<div align="center">

<sub><strong>L0NE-6 · DAILY SIGNAL</strong></sub>

# 🧩 Sub2API Daily

**Sub2API daily check-in · multi-account · strict status and claim readback · JSONL**

[简体中文](../README.md) · [English](README.en.md) · [繁體中文](README.zh-Hant.md) · [日本語](README.ja.md) · [한국어](README.ko.md) · [Português (BR)](README.pt-BR.md)

</div>

## What it does

Logs in to a Sub2API site, reads the daily check-in state, claims the reward,
and reads the state again. A claim is reported as `CLAIMED` only when the
response contains `reward_amount`, `new_balance`, `checked_in_at`, and the
subsequent status has `checked_in_today=true`.

## Configuration

Use `SUB2API_ACCOUNTS` with `label|site|email|password`, or
`SUB2API_SESSIONS` with `label|site|accessToken|userId`. JSON account lists and
single-account variables are also supported. A site URL must be the site root,
not `/api/v1` or `/v1`.

## Protocol

```http
GET  /api/v1/redeem/checkin/status
GET  /api/v1/redeem/checkin          # fallback when status is unsupported
POST /api/v1/redeem/checkin          # no body
Authorization: Bearer <ACCESS_TOKEN>
```

The claim response must contain finite `reward_amount` and `new_balance`, plus
a valid RFC3339 `checked_in_at`. The post-claim status must confirm
`checked_in_today=true`. Missing fields or an unreadable status are
`UNCONFIRMED`, never success.

## Run locally

```bash
python -m pip install -r requirements.txt
export SUB2API_ACCOUNTS='main|https://sub2api.example|user@example.com|password'
python sub2api_daily.py
python sub2api_daily.py --query
python sub2api_daily.py --only 1,3-4
```

## Deploy

For Qinglong, upload `sub2api_daily.py`, set the account variable, and run
`task sub2api_daily.py`. For GitHub Actions, add the same value as a Secret and
run the included workflow.

## Privacy

Do not commit passwords, tokens, account files, reports, logs, or screenshots
containing credentials. The script redacts identifiers, secrets, and
notification credentials from output and errors.

## Test

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
python -m ruff check .
```

All tests use fake HTTP sessions and do not call the live service.
