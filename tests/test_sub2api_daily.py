import importlib.util
import json
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("sub2api_daily", ROOT / "sub2api_daily.py")
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class FakeResponse:
    def __init__(self, payload, status=200, text=None):
        self.status_code = status
        self.text = text if text is not None else json.dumps(payload)
        self.headers = {}


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.headers = {}
        self.proxies = {}
        self.calls = []
        self.closed = False

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.response

    def close(self):
        self.closed = True


class FakeTransport:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.sessions = []

    def __call__(self):
        if not self.responses:
            raise AssertionError("unexpected HTTP request")
        session = FakeSession(self.responses.pop(0))
        self.sessions.append(session)
        return session


def envelope(data):
    return {"code": 0, "data": data}


class AccountParsingTests(unittest.TestCase):
    def test_password_and_session_lines(self):
        password_accounts = MODULE.parse_accounts(
            "主号|https://sub2api.example|a@example.com|password"
        )
        session_accounts = MODULE.parse_accounts(
            "小号|https://sub2api.example|token-1|42",
            sessions=True,
        )
        self.assertEqual(password_accounts[0].email, "a@example.com")
        self.assertEqual(password_accounts[0].password, "password")
        self.assertEqual(session_accounts[0].access_token, "token-1")
        self.assertEqual(session_accounts[0].user_id, "42")

    def test_json_accounts(self):
        accounts = MODULE.parse_accounts(
            json.dumps(
                [
                    {
                        "name": "json",
                        "site": "https://sub2api.example",
                        "accessToken": "token-json",
                        "userId": "7",
                    }
                ]
            )
        )
        self.assertEqual(accounts[0].label, "json")
        self.assertEqual(accounts[0].access_token, "token-json")

    def test_site_normalization_rejects_api_base(self):
        with self.assertRaises(MODULE.ConfigError):
            MODULE.normalize_site("https://sub2api.example/api/v1")

    def test_site_host_is_normalized_and_short_email_is_redacted(self):
        self.assertEqual(
            MODULE.normalize_site("https://SUB2API.EXAMPLE"),
            "https://sub2api.example",
        )
        self.assertEqual(MODULE.redact_identifier("a@example.com"), "a***@example.com")
        self.assertNotIn("a@example.com", MODULE.sanitize_message("failed for a@example.com"))


class FlowTests(unittest.TestCase):
    def account(self):
        return MODULE.Account(
            name="测试",
            site="https://sub2api.example",
            access_token="access-token",
        )

    def client(self, *responses):
        transport = FakeTransport(*responses)
        client = MODULE.Sub2APIClient(
            wait_seconds=0,
            session_factory=transport,
        )
        return client, transport

    def test_strict_claim_requires_status_and_claim_fields(self):
        client, transport = self.client(
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": False,
                        "reward_min": 0.1,
                        "reward_max": 1,
                    }
                )
            ),
            FakeResponse(
                envelope(
                    {
                        "reward_amount": 0.25,
                        "new_balance": 10,
                        "checked_in_at": "2026-01-02T03:04:05Z",
                        "message": "ok",
                    }
                )
            ),
            FakeResponse(envelope({"enabled": True, "checked_in_today": True})),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "CLAIMED")
        self.assertEqual(result.reward_amount, Decimal("0.25"))
        self.assertEqual(result.new_balance, Decimal("10"))
        self.assertEqual(result.checked_in_at, "2026-01-02T03:04:05Z")
        self.assertEqual(
            [session.calls[0][0] for session in transport.sessions],
            ["GET", "POST", "GET"],
        )
        post_kwargs = transport.sessions[1].calls[0][2]
        self.assertNotIn("json", post_kwargs)
        self.assertNotIn("data", post_kwargs)

    def test_missing_strict_claim_field_is_unconfirmed(self):
        client, _ = self.client(
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": False,
                        "reward_min": 0.1,
                        "reward_max": 1,
                    }
                )
            ),
            FakeResponse(
                envelope(
                    {
                        "reward_amount": 0.25,
                        "new_balance": 10,
                        "message": "ok",
                    }
                )
            ),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "UNCONFIRMED")
        self.assertIn("checked_in_at", result.message)

    def test_status_falls_back_to_legacy_endpoint(self):
        client, transport = self.client(
            FakeResponse({"code": 1, "message": "not supported"}, status=404),
            FakeResponse(envelope({"checked_in": False, "reward": 0.5})),
        )
        result = MODULE.run_account(1, self.account(), client, query_only=True)
        self.assertEqual(result.status, "QUERY")
        self.assertEqual(result.source, "legacy")
        self.assertEqual(transport.sessions[1].calls[0][1], "https://sub2api.example/api/v1/redeem/checkin")

    def test_already_checked_in_skips_post(self):
        client, transport = self.client(
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": True,
                        "reward_amount": 0.5,
                    }
                )
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "ALREADY")
        self.assertEqual(len(transport.sessions), 1)

    def test_duplicate_claim_uses_after_status(self):
        client, _ = self.client(
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": False,
                        "reward_min": 0.1,
                        "reward_max": 1,
                    }
                )
            ),
            FakeResponse(
                {"code": 409, "reason": "DAILY_CHECKIN_ALREADY_DONE"},
                status=409,
            ),
            FakeResponse(envelope({"enabled": True, "checked_in_today": True})),
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "ALREADY")

    def test_login_then_claim(self):
        account = MODULE.Account(
            name="login",
            site="https://sub2api.example",
            email="a@example.com",
            password="password",
        )
        client, transport = self.client(
            FakeResponse(
                envelope(
                    {
                        "access_token": "new-token",
                        "refresh_token": "refresh-token",
                        "token_type": "Bearer",
                        "expires_in": 3600,
                        "user": {"id": 42},
                    }
                )
            ),
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": False,
                        "reward_min": 0.1,
                        "reward_max": 1,
                    }
                )
            ),
            FakeResponse(
                envelope(
                    {
                        "reward_amount": 0.25,
                        "new_balance": 10,
                        "checked_in_at": "2026-01-02T03:04:05Z",
                    }
                )
            ),
            FakeResponse(envelope({"enabled": True, "checked_in_today": True})),
        )
        result = MODULE.run_account(1, account, client)
        self.assertEqual(result.status, "CLAIMED")
        self.assertEqual(account.access_token, "new-token")
        self.assertEqual(account.user_id, "42")
        self.assertEqual(transport.sessions[0].calls[0][1], "https://sub2api.example/api/v1/auth/login")

    def test_manual_challenge_is_not_success(self):
        client, _ = self.client(
            FakeResponse(
                {"code": 1, "message": "CAPTCHA_REQUIRED"},
                status=403,
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "MANUAL_REQUIRED")
        self.assertFalse(result.ok)

    def test_false_captcha_flag_does_not_trigger_manual_required(self):
        client, _ = self.client(
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": True,
                        "requires_captcha": False,
                    }
                )
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "ALREADY")
        self.assertTrue(result.ok)

    def test_chinese_challenge_is_manual_required(self):
        client, _ = self.client(
            FakeResponse(
                {"code": 1, "message": "请完成安全验证"},
                status=403,
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "MANUAL_REQUIRED")
        self.assertFalse(result.ok)

    def test_disabled_business_response_is_inactive(self):
        client, _ = self.client(
            FakeResponse(
                {"code": 1, "reason": "DAILY_CHECKIN_DISABLED"},
                status=403,
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "INACTIVE")
        self.assertTrue(result.ok)

    def test_token_disabled_auth_error_is_not_inactive(self):
        client, _ = self.client(
            FakeResponse({"message": "Token disabled"}, status=401)
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "AUTH_EXPIRED")
        self.assertFalse(result.ok)

    def test_role_forbidden_is_not_inactive(self):
        client, _ = self.client(
            FakeResponse(
                {"reason": "DAILY_CHECKIN_ROLE_FORBIDDEN"},
                status=403,
            )
        )
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "API_ERROR")
        self.assertFalse(result.ok)

    def test_login_message_ok_is_not_treated_as_business_code(self):
        account = MODULE.Account(
            name="login-message",
            site="https://sub2api.example",
            email="a@example.com",
            password="password",
        )
        client, _ = self.client(
            FakeResponse(
                {
                    "message": "ok",
                    "data": {"access_token": "new-token"},
                }
            ),
            FakeResponse(
                envelope({"enabled": True, "checked_in_today": True})
            ),
        )
        result = MODULE.run_account(1, account, client)
        self.assertEqual(result.status, "ALREADY")
        self.assertEqual(account.access_token, "new-token")

    def test_claim_readback_recovers_expired_session(self):
        account = MODULE.Account(
            name="refresh",
            site="https://sub2api.example",
            access_token="old-token",
            refresh_token="refresh-token",
        )
        client, transport = self.client(
            FakeResponse(
                envelope(
                    {
                        "enabled": True,
                        "checked_in_today": False,
                        "reward_min": 0.1,
                        "reward_max": 1,
                    }
                )
            ),
            FakeResponse(
                envelope(
                    {
                        "reward_amount": 0.25,
                        "new_balance": 10,
                        "checked_in_at": "2026-01-02T03:04:05Z",
                    }
                )
            ),
            FakeResponse({}, status=401),
            FakeResponse(
                envelope(
                    {
                        "access_token": "new-token",
                        "refresh_token": "new-refresh-token",
                    }
                )
            ),
            FakeResponse(envelope({"enabled": True, "checked_in_today": True})),
        )
        result = MODULE.run_account(1, account, client)
        self.assertEqual(result.status, "CLAIMED")
        self.assertEqual(account.access_token, "new-token")
        self.assertEqual(
            transport.sessions[3].calls[0][1],
            "https://sub2api.example/api/v1/auth/refresh",
        )

    def test_auth_expired_is_not_success(self):
        client, _ = self.client(FakeResponse({}, status=401))
        result = MODULE.run_account(1, self.account(), client)
        self.assertEqual(result.status, "AUTH_EXPIRED")
        self.assertFalse(result.ok)


if __name__ == "__main__":
    unittest.main()
