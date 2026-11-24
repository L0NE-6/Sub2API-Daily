# Changelog

## v1.0.0 - 2026-11-24

- Added the standalone Sub2API daily check-in script.
- Added multi-account password and access-token account forms.
- Added login, refresh, status fallback, empty-body claim, and strict
  `checked_in_today`/`reward_amount`/`checked_in_at`/`new_balance` readback.
- Added neutral already-claimed handling and explicit manual, authentication,
  malformed-response, and unconfirmed outcomes.
- Added escaped-JSON and Chinese challenge detection, plus neutral handling for
  disabled check-in business responses.
- Prevented disabled-token and role-forbidden responses from being reported as
  successful inactive accounts, added email redaction, and recover expired
  sessions during post-claim status readback.
- Added optional notifications, offline tests, GitHub Actions, MIT licensing,
  usage policy, third-party notices, six-language documentation, and QR assets.
