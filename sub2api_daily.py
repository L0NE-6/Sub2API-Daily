#!/usr/bin/env python3
"""Sub2API daily check-in runner with strict server-side readback."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import urlparse

import requests


VERSION = "1.0.0"
PROVIDER = "sub2api"

LOGIN_PATH = "/api/v1/auth/login"
REFRESH_PATH = "/api/v1/auth/refresh"
CHECKIN_STATUS_PATH = "/api/v1/redeem/checkin/status"
CHECKIN_PATH = "/api/v1/redeem/checkin"

ACCOUNTS_ENV = "SUB2API_ACCOUNTS"
SESSIONS_ENV = "SUB2API_SESSIONS"
ACCOUNT_FILE_ENV = "SUB2API_ACCOUNT_FILE"
SITE_ENV = "SUB2API_SITE"
EMAIL_ENV = "SUB2API_EMAIL"
PASSWORD_ENV = "SUB2API_PASSWORD"
ACCESS_TOKEN_ENV = "SUB2API_ACCESS_TOKEN"
USER_ID_ENV = "SUB2API_USER_ID"
PROXY_ENV = "SUB2API_PROXY"
WAIT_ENV = "SUB2API_WAIT_SECONDS"
DEFAULT_ACCOUNT_FILE = "sub2api_accounts.txt"

DEFAULT_TIMEOUT = 20.0
DEFAULT_WAIT_SECONDS = 0.5
SUCCESS_STATUSES = {"CLAIMED", "ALREADY", "QUERY", "INACTIVE"}
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?86[- ]?)?(1[3-9]\d{9})(?!\d)")
EMAIL_PATTERN = re.compile(
    r"(?<![A-Za-z0-9._%+-])([A-Za-z0-9._%+-]+)@([A-Za-z0-9.-]+\.[A-Za-z]{2,})(?![A-Za-z0-9.-])"
)
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


class Sub2APIError(Exception):
    """Base class for controlled Sub2API errors."""


class ConfigError(Sub2APIError):
    """Account or command configuration is invalid."""


class SessionExpired(Sub2APIError):
    """The Sub2API session is no longer accepted."""


class ManualRequired(Sub2APIError):
    """The site requires a captcha or another manual login step."""

    def __init__(self, kind: str, message: str) -> None:
        super().__init__(message)
        self.kind = kind


class APIError(Sub2APIError):
    """The service returned an HTTP, JSON, or business error."""

    def __init__(self, message: str, *, status: int = 0, code: str = "") -> None:
        super().__init__(message)
        self.status = status
        self.code = code


@dataclass
class Account:
    name: str
    site: str
    email: str = ""
    password: str = ""
    access_token: str = ""
    refresh_token: str = ""
    user_id: str = ""

    @property
    def label(self) -> str:
        value = self.name or self.email or self.user_id or self.site
        return redact_identifier(value)

    @property
    def fingerprint(self) -> Tuple[str, str]:
        return (self.site, self.email or self.user_id or self.access_token)


@dataclass
class CheckinStatus:
    source: str
    enabled: bool
    checked_in_today: bool
    reward_amount: Optional[Decimal] = None
    reward_min: Optional[Decimal] = None
    reward_max: Optional[Decimal] = None


@dataclass
class RunResult:
    index: int
    label: str
    status: str
    message: str
    http_status: int = 0
    reward_amount: Optional[Decimal] = None
    new_balance: Optional[Decimal] = None
    checked_in_at: str = ""
    source: str = ""
    detail_lines: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in SUCCESS_STATUSES

    def as_dict(self) -> Dict[str, Any]:
        return {
            "type": "account",
            "provider": PROVIDER,
            "index": self.index,
            "label": self.label,
            "status": self.status,
            "ok": self.ok,
            "message": self.message,
            "http_status": self.http_status,
            "reward_amount": format_decimal(self.reward_amount),
            "new_balance": format_decimal(self.new_balance),
            "checked_in_at": self.checked_in_at,
            "source": self.source,
            "details": list(self.detail_lines),
        }


def emit(payload: Dict[str, Any]) -> None:
    print(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str),
        flush=True,
    )


def env_text(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def redact_phone(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        phone = match.group(1)
        return "%s****%s" % (phone[:3], phone[-4:])

    return PHONE_PATTERN.sub(replace, str(text or ""))


def redact_email(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        local, domain = match.group(1), match.group(2)
        visible = local[:1] if local else "*"
        return "%s***@%s" % (visible, domain)

    return EMAIL_PATTERN.sub(replace, str(text or ""))


def redact_identifier(value: Any) -> str:
    text = redact_phone(redact_email(str(value or "").strip()))
    return text[:120] or "Sub2API"


def sanitize_message(message: Any, account: Optional[Account] = None) -> str:
    text = str(message or "").replace("\r", " ").replace("\n", " ").strip()
    if account is not None:
        for secret in (account.password, account.access_token, account.refresh_token):
            if secret:
                text = text.replace(secret, "[redacted-secret]")
    for name in (
        "PUSHPLUS_TOKEN",
        "BARK_URL",
        "WECOM_WEBHOOK",
        "DINGTALK_WEBHOOK",
        "GENERIC_WEBHOOK_URL",
        PROXY_ENV,
    ):
        value = env_text(name)
        if value:
            text = text.replace(value, "[redacted-%s]" % name.lower())
    return redact_phone(redact_email(text))[:800]


def parse_decimal(value: Any) -> Optional[Decimal]:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value).strip())
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    return number


def format_decimal(value: Optional[Decimal]) -> Optional[str]:
    if value is None:
        return None
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f").rstrip("0").rstrip(".")


def normalize_token(value: Any) -> str:
    token = str(value or "").strip()
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    if not token or any(char.isspace() for char in token):
        return ""
    if any(ord(char) < 32 or ord(char) == 127 for char in token):
        return ""
    return token


def is_loopback(hostname: str) -> bool:
    host = str(hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1", "[::1]"}


def normalize_site(value: Any) -> str:
    raw = str(value or "").strip()
    if not raw or len(raw) > 2048:
        raise ConfigError("Sub2API site URL is empty or too long")
    parsed = urlparse(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("Sub2API site must be an absolute http(s) URL")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ConfigError("Sub2API site cannot contain credentials, query, or fragment")
    if parsed.scheme == "http" and not is_loopback(parsed.hostname or ""):
        raise ConfigError("Sub2API only allows http for loopback test sites")
    path = (parsed.path or "").rstrip("/")
    if re.search(r"(?:^|/)(?:api/)?v1$", path, re.IGNORECASE):
        raise ConfigError("Sub2API site must be the site root, not an API base")
    if any(segment in {".", ".."} for segment in path.split("/") if segment):
        raise ConfigError("Sub2API site path contains traversal")
    return "%s://%s%s" % (parsed.scheme, parsed.netloc.lower(), path)


def _json_accounts(value: Any) -> List[Account]:
    items = value.get("accounts") if isinstance(value, dict) else value
    if not isinstance(items, list):
        raise ConfigError("SUB2API account JSON must be a list or an object with accounts[]")
    accounts: List[Account] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        site = normalize_site(item.get("site") or item.get("baseURL") or item.get("base"))
        name = str(item.get("name") or item.get("label") or item.get("note") or "").strip()
        email = str(item.get("email") or item.get("loginEmail") or "").strip()
        password = str(item.get("password") or "")
        access = normalize_token(
            item.get("accessToken") or item.get("access_token") or item.get("token")
        )
        refresh = normalize_token(
            item.get("refreshToken") or item.get("refresh_token")
        )
        user_id = str(item.get("userId") or item.get("user_id") or item.get("uid") or "").strip()
        if not email and not access:
            continue
        if email and not password and not access:
            continue
        accounts.append(
            Account(
                name=name,
                site=site,
                email=email,
                password=password,
                access_token=access,
                refresh_token=refresh,
                user_id=user_id,
            )
        )
    return accounts


def parse_accounts(raw: str, *, sessions: bool = False) -> List[Account]:
    text = str(raw or "").strip()
    if not text:
        return []
    if text.startswith("[") or text.startswith("{"):
        try:
            return _json_accounts(json.loads(text))
        except json.JSONDecodeError as error:
            raise ConfigError("SUB2API account JSON is invalid: %s" % error) from error

    accounts: List[Account] = []
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("|", 3)
        if sessions:
            if len(parts) != 4:
                raise ConfigError(
                    "SUB2API session line %d must be label|site|accessToken|userId"
                    % line_number
                )
            name, site, token, user_id = parts
            token = normalize_token(token)
            if not token:
                raise ConfigError("SUB2API session line %d has no valid token" % line_number)
            accounts.append(
                Account(
                    name=name.strip(),
                    site=normalize_site(site),
                    access_token=token,
                    user_id=user_id.strip(),
                )
            )
            continue
        if len(parts) != 4:
            raise ConfigError(
                "SUB2API account line %d must be label|site|email|password"
                % line_number
            )
        name, site, email, password = parts
        email = email.strip()
        if not email or not password:
            raise ConfigError("SUB2API account line %d has empty email or password" % line_number)
        accounts.append(
            Account(
                name=name.strip(),
                site=normalize_site(site),
                email=email,
                password=password,
            )
        )
    return accounts


def load_accounts(account_file: Optional[str] = None) -> List[Account]:
    accounts = parse_accounts(env_text(ACCOUNTS_ENV))
    accounts.extend(parse_accounts(env_text(SESSIONS_ENV), sessions=True))
    if not accounts:
        path = account_file or env_text(ACCOUNT_FILE_ENV)
        if not path and Path(DEFAULT_ACCOUNT_FILE).exists():
            path = DEFAULT_ACCOUNT_FILE
        if path:
            try:
                raw = Path(path).read_text(encoding="utf-8")
            except OSError as error:
                raise ConfigError("cannot read SUB2API account file: %s" % error) from error
            accounts = parse_accounts(raw)
    if not accounts:
        site = env_text(SITE_ENV)
        email = env_text(EMAIL_ENV)
        password = env_text(PASSWORD_ENV)
        access = normalize_token(env_text(ACCESS_TOKEN_ENV))
        user_id = env_text(USER_ID_ENV)
        if site and (access or (email and password)):
            accounts = [
                Account(
                    name="",
                    site=normalize_site(site),
                    email=email,
                    password=password,
                    access_token=access,
                    user_id=user_id,
                )
            ]
    deduped: List[Account] = []
    seen = set()
    for account in accounts:
        if account.fingerprint in seen:
            continue
        seen.add(account.fingerprint)
        deduped.append(account)
    if not deduped:
        raise ConfigError(
            "SUB2API_ACCOUNTS, SUB2API_SESSIONS, SUB2API_ACCOUNT_FILE, or single-account variables are not configured"
        )
    return deduped


def parse_only(value: str, total: int) -> set[int]:
    if not value.strip():
        return set(range(1, total + 1))
    selected: set[int] = set()
    for part in value.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            try:
                start, end = int(start_text), int(end_text)
            except ValueError as error:
                raise ConfigError("invalid --only range: %s" % part) from error
            if start > end:
                start, end = end, start
            selected.update(range(start, end + 1))
        else:
            try:
                selected.add(int(part))
            except ValueError as error:
                raise ConfigError("invalid --only item: %s" % part) from error
    if not selected or min(selected) < 1 or max(selected) > total:
        raise ConfigError("--only contains an account outside 1..%d" % total)
    return selected


def response_data(payload: Any) -> Any:
    if isinstance(payload, dict) and isinstance(payload.get("data"), dict):
        return payload["data"]
    return payload


def response_code(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for source in (payload, payload.get("data")):
        if isinstance(source, dict):
            for key in ("reason", "error", "code"):
                value = source.get(key)
                if isinstance(value, dict):
                    value = value.get("code") or value.get("reason")
                if value is not None and str(value).strip():
                    return str(value).strip()
    return ""


def response_message(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for source in (payload, payload.get("data")):
        if isinstance(source, dict):
            for key in ("message", "msg", "detail", "reason"):
                value = source.get(key)
                if value is not None and str(value).strip():
                    return str(value).strip()
    return ""


def is_challenge_text(text: str) -> bool:
    lower = str(text or "").lower()
    return any(
        marker in lower
        for marker in (
            "captcha",
            "turnstile",
            "cf-challenge",
            "__cf_chl_",
            "just a moment",
            "attention required",
            "checking your browser",
            "验证码",
            "人机验证",
            "需要验证",
            "请完成验证",
            "安全验证",
            "驗證碼",
            "人機驗證",
            "需要驗證",
            "請完成驗證",
            "安全驗證",
        )
    )


def is_inactive_response(payload: Any) -> bool:
    code = response_code(payload).upper()
    if code in {
        "DAILY_CHECKIN_DISABLED",
        "CHECKIN_DISABLED",
    }:
        return True
    lower = response_message(payload).lower()
    has_context = any(
        marker in lower
        for marker in ("check-in", "checkin", "check in", "签到", "簽到")
    )
    has_inactive_marker = any(
        marker in lower
        for marker in (
            "not enabled",
            "disabled",
            "not available",
            "未开启",
            "未啟用",
            "未启用",
            "不可用",
        )
    )
    return has_context and has_inactive_marker


def is_checkin_forbidden_response(payload: Any) -> bool:
    return response_code(payload).upper() == "DAILY_CHECKIN_ROLE_FORBIDDEN"


def valid_rfc3339(value: str) -> bool:
    if not RFC3339_PATTERN.match(value):
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


class Sub2APIClient:
    """HTTP client with an injectable session factory for offline tests."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        wait_seconds: float = DEFAULT_WAIT_SECONDS,
        proxy: str = "",
        session_factory: Any = None,
        sleeper: Any = time.sleep,
    ) -> None:
        self.timeout = max(1.0, float(timeout))
        self.wait_seconds = max(0.0, float(wait_seconds))
        self.proxy = str(proxy or "").strip()
        self.session_factory = session_factory or requests.Session
        self.sleeper = sleeper

    def _new_session(self) -> Any:
        session = self.session_factory()
        session.headers.update(
            {
                "Accept": "application/json",
                "User-Agent": "Sub2API-Daily/1.0",
            }
        )
        if self.proxy:
            session.proxies.update({"http": self.proxy, "https": self.proxy})
        return session

    def _request(
        self,
        account: Account,
        method: str,
        path: str,
        *,
        token: str = "",
        body: Optional[Dict[str, Any]] = None,
        query: Optional[Dict[str, Any]] = None,
    ) -> Tuple[int, Any]:
        session = self._new_session()
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = "Bearer %s" % token
        if body is not None:
            headers["Content-Type"] = "application/json"
        request_kwargs: Dict[str, Any] = {
            "headers": headers,
            "params": query,
            "timeout": self.timeout,
            "allow_redirects": False,
        }
        if body is not None:
            request_kwargs["json"] = body
        try:
            response = session.request(
                method,
                account.site + path,
                **request_kwargs,
            )
        except requests.RequestException as error:
            raise APIError(
                "Sub2API network request failed: %s"
                % sanitize_message(error, account)
            ) from error
        finally:
            session.close()

        status = int(getattr(response, "status_code", 0) or 0)
        text = getattr(response, "text", "") or ""
        if 300 <= status < 400:
            raise APIError(
                "Sub2API returned a redirect (HTTP %d)" % status,
                status=status,
                code="REDIRECT",
            )
        try:
            payload = json.loads(text, parse_float=Decimal, parse_int=int)
        except (json.JSONDecodeError, TypeError) as error:
            if is_challenge_text(text):
                raise ManualRequired("CAPTCHA", "Sub2API requires a browser challenge") from error
            raise APIError(
                "Sub2API returned non-JSON data (HTTP %d)" % status,
                status=status,
                code="INVALID_JSON",
            ) from error
        if not isinstance(payload, dict):
            raise APIError(
                "Sub2API JSON top level is not an object (HTTP %d)" % status,
                status=status,
                code="INVALID_RESPONSE",
            )
        if (
            payload.get("requires_captcha") is True
            or payload.get("captcha_required") is True
            or is_challenge_text(response_message(payload))
            or is_challenge_text(response_code(payload))
        ):
            raise ManualRequired("CAPTCHA", "Sub2API requires a browser challenge")
        return status, payload

    def login(self, account: Account) -> str:
        if not account.email or not account.password:
            raise ConfigError("Sub2API account has no email/password for login")
        status, payload = self._request(
            account,
            "POST",
            LOGIN_PATH,
            body={"email": account.email, "password": account.password},
        )
        if status in (401, 403):
            raise SessionExpired("Sub2API login was rejected")
        data = response_data(payload)
        if not isinstance(data, dict):
            raise APIError(
                "Sub2API login data is not an object",
                status=status,
                code="INVALID_RESPONSE",
            )
        if data.get("requires_2fa") or data.get("requires_totp") or data.get("two_factor_required"):
            raise ManualRequired("TWO_FACTOR", "Sub2API login requires 2FA")
        if data.get("requires_captcha") or data.get("captcha_required"):
            raise ManualRequired("CAPTCHA", "Sub2API login requires a captcha")
        if payload.get("success") is False or response_code(payload) not in {"", "0", "SUCCESS"}:
            raise APIError(
                "Sub2API login failed: %s"
                % sanitize_message(response_message(payload) or response_code(payload), account),
                status=status,
                code=response_code(payload),
            )
        token = normalize_token(data.get("access_token") or data.get("accessToken"))
        if not token:
            raise APIError(
                "Sub2API login returned no access_token",
                status=status,
                code="INVALID_RESPONSE",
            )
        account.access_token = token
        refresh = normalize_token(data.get("refresh_token") or data.get("refreshToken"))
        if refresh:
            account.refresh_token = refresh
        user = data.get("user") if isinstance(data.get("user"), dict) else {}
        if not account.user_id and user.get("id") is not None:
            account.user_id = str(user["id"])
        return token

    def refresh(self, account: Account) -> str:
        if not account.refresh_token:
            raise SessionExpired("Sub2API has no refresh_token")
        status, payload = self._request(
            account,
            "POST",
            REFRESH_PATH,
            body={"refresh_token": account.refresh_token},
        )
        data = response_data(payload)
        if status in (401, 403) or not isinstance(data, dict):
            raise SessionExpired("Sub2API refresh was rejected")
        if data.get("requires_captcha") or data.get("captcha_required"):
            raise ManualRequired("CAPTCHA", "Sub2API refresh requires a captcha")
        token = normalize_token(data.get("access_token") or data.get("accessToken"))
        if not token:
            raise SessionExpired("Sub2API refresh returned no access_token")
        account.access_token = token
        refresh = normalize_token(data.get("refresh_token") or data.get("refreshToken"))
        if refresh:
            account.refresh_token = refresh
        return token

    def recover(self, account: Account) -> str:
        if account.refresh_token:
            try:
                return self.refresh(account)
            except (SessionExpired, APIError, ManualRequired):
                pass
        if account.email and account.password:
            return self.login(account)
        raise SessionExpired(
            "Sub2API session expired and the account has no refresh token or password"
        )

    def status(self, account: Account, token: str) -> Tuple[CheckinStatus, int]:
        status, payload = self._request(account, "GET", CHECKIN_STATUS_PATH, token=token)
        source = "status"
        if status in (404, 405):
            status, payload = self._request(account, "GET", CHECKIN_PATH, token=token)
            source = "legacy"
        if is_checkin_forbidden_response(payload):
            raise APIError(
                "Sub2API check-in is not available for this account",
                status=status,
                code=response_code(payload),
            )
        if status in (401, 403) and is_inactive_response(payload):
            return (
                CheckinStatus(
                    source=source,
                    enabled=False,
                    checked_in_today=False,
                ),
                status,
            )
        if status in (401, 403):
            raise SessionExpired("Sub2API session expired")
        if is_inactive_response(payload):
            return (
                CheckinStatus(
                    source=source,
                    enabled=False,
                    checked_in_today=False,
                ),
                status,
            )
        if not 200 <= status < 300:
            raise APIError(
                "Sub2API check-in status failed (HTTP %d): %s"
                % (status, sanitize_message(response_message(payload), account)),
                status=status,
                code=response_code(payload),
            )
        if payload.get("success") is False or response_code(payload) not in {"", "0", "SUCCESS"}:
            raise APIError(
                "Sub2API check-in status failed: %s"
                % sanitize_message(response_message(payload) or response_code(payload), account),
                status=status,
                code=response_code(payload),
            )
        data = response_data(payload)
        if not isinstance(data, dict):
            raise APIError(
                "Sub2API check-in status data is not an object",
                status=status,
                code="INVALID_RESPONSE",
            )
        if isinstance(data.get("enabled"), bool) and isinstance(data.get("checked_in_today"), bool):
            return (
                CheckinStatus(
                    source=source,
                    enabled=data["enabled"],
                    checked_in_today=data["checked_in_today"],
                    reward_amount=parse_decimal(data.get("reward_amount")),
                    reward_min=parse_decimal(data.get("reward_min")),
                    reward_max=parse_decimal(data.get("reward_max")),
                ),
                status,
            )
        if isinstance(data.get("checked_in"), bool) and parse_decimal(data.get("reward")) is not None:
            reward = parse_decimal(data.get("reward"))
            return (
                CheckinStatus(
                    source="legacy",
                    enabled=bool(reward and reward > 0),
                    checked_in_today=data["checked_in"],
                    reward_amount=reward if data["checked_in"] else None,
                ),
                status,
            )
        raise APIError(
            "Sub2API status lacks enabled/checked_in_today or legacy checked_in/reward",
            status=status,
            code="INVALID_RESPONSE",
        )

    def claim(self, account: Account, token: str) -> Tuple[int, Any]:
        return self._request(account, "POST", CHECKIN_PATH, token=token)


def claim_data(payload: Any) -> Dict[str, Any]:
    data = response_data(payload)
    if not isinstance(data, dict):
        return {}
    return data


def run_account(
    index: int,
    account: Account,
    client: Sub2APIClient,
    query_only: bool = False,
) -> RunResult:
    label = account.label
    try:
        token = account.access_token
        if not token:
            token = client.login(account)
        try:
            before, before_status = client.status(account, token)
        except SessionExpired:
            token = client.recover(account)
            before, before_status = client.status(account, token)

        if not before.enabled:
            return RunResult(
                index=index,
                label=label,
                status="INACTIVE",
                message="站点当前没有开启每日签到活动",
                http_status=before_status,
                reward_amount=before.reward_amount,
                source=before.source,
            )
        if query_only:
            return RunResult(
                index=index,
                label=label,
                status="QUERY",
                message="查询完成；未发送签到请求",
                http_status=before_status,
                reward_amount=before.reward_amount,
                source=before.source,
            )
        if before.checked_in_today:
            return RunResult(
                index=index,
                label=label,
                status="ALREADY",
                message="今日已签到（服务端状态确认）",
                http_status=before_status,
                reward_amount=before.reward_amount,
                source=before.source,
            )

        claim_status, payload = client.claim(account, token)
        if claim_status in (401, 403):
            token = client.recover(account)
            claim_status, payload = client.claim(account, token)
        if claim_status == 409 or response_code(payload).upper() == "DAILY_CHECKIN_ALREADY_DONE":
            try:
                after, after_status = client.status(account, token)
            except SessionExpired:
                try:
                    token = client.recover(account)
                    after, after_status = client.status(account, token)
                except Sub2APIError as error:
                    return RunResult(
                        index=index,
                        label=label,
                        status="UNCONFIRMED",
                        message="重复领取后无法恢复会话并回读状态：%s"
                        % sanitize_message(error, account),
                        http_status=claim_status,
                        source=before.source,
                    )
            except Sub2APIError as error:
                return RunResult(
                    index=index,
                    label=label,
                    status="UNCONFIRMED",
                    message="重复领取后无法回读状态：%s" % sanitize_message(error, account),
                    http_status=claim_status,
                    source=before.source,
                )
            if after.checked_in_today:
                return RunResult(
                    index=index,
                    label=label,
                    status="ALREADY",
                    message="今日已签到（重复领取回读确认）",
                    http_status=after_status,
                    reward_amount=after.reward_amount,
                    source=after.source,
                )
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="服务端返回重复领取，但状态未确认今日已签",
                http_status=after_status,
                source=after.source,
            )
        if not 200 <= claim_status < 300:
            if is_challenge_text(response_message(payload)):
                return RunResult(
                    index=index,
                    label=label,
                    status="MANUAL_REQUIRED",
                    message="签到需要浏览器验证码或 Cloudflare 验证，请手动完成",
                    http_status=claim_status,
                    source=before.source,
                )
            return RunResult(
                index=index,
                label=label,
                status="API_ERROR",
                message=sanitize_message(
                    response_message(payload) or "签到失败（HTTP %d）" % claim_status,
                    account,
                ),
                http_status=claim_status,
                source=before.source,
            )

        data = claim_data(payload)
        reward = parse_decimal(data.get("reward_amount"))
        new_balance = parse_decimal(data.get("new_balance"))
        checked_at = str(data.get("checked_in_at") or "")
        if reward is None or reward < 0:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="领取响应缺少有效的 reward_amount",
                http_status=claim_status,
                source=before.source,
            )
        if new_balance is None:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="领取响应缺少有效的 new_balance",
                http_status=claim_status,
                reward_amount=reward,
                source=before.source,
            )
        if not valid_rfc3339(checked_at):
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="领取响应缺少有效的 checked_in_at",
                http_status=claim_status,
                reward_amount=reward,
                new_balance=new_balance,
                source=before.source,
            )

        if client.wait_seconds:
            client.sleeper(client.wait_seconds)
        try:
            after, after_status = client.status(account, token)
        except SessionExpired:
            try:
                token = client.recover(account)
                after, after_status = client.status(account, token)
            except Sub2APIError as error:
                return RunResult(
                    index=index,
                    label=label,
                    status="UNCONFIRMED",
                    message="领取响应完整，但恢复会话后仍无法回读状态：%s"
                    % sanitize_message(error, account),
                    http_status=claim_status,
                    reward_amount=reward,
                    new_balance=new_balance,
                    checked_in_at=checked_at,
                    source=before.source,
                )
        except Sub2APIError as error:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="领取响应完整，但状态回读失败：%s"
                % sanitize_message(error, account),
                http_status=claim_status,
                reward_amount=reward,
                new_balance=new_balance,
                checked_in_at=checked_at,
                source=before.source,
            )
        if not after.checked_in_today:
            return RunResult(
                index=index,
                label=label,
                status="UNCONFIRMED",
                message="领取响应完整，但服务端状态仍显示今日未签到",
                http_status=after_status,
                reward_amount=reward,
                new_balance=new_balance,
                checked_in_at=checked_at,
                source=after.source,
            )
        return RunResult(
            index=index,
            label=label,
            status="CLAIMED",
            message="签到成功，服务端已回读今日状态和奖励字段",
            http_status=after_status,
            reward_amount=reward,
            new_balance=new_balance,
            checked_in_at=checked_at,
            source=after.source,
        )
    except ManualRequired as error:
        return RunResult(
            index=index,
            label=label,
            status="MANUAL_REQUIRED",
            message="需要人工处理：%s" % sanitize_message(error, account),
        )
    except SessionExpired as error:
        return RunResult(
            index=index,
            label=label,
            status="AUTH_EXPIRED",
            message=sanitize_message(error, account),
        )
    except ConfigError as error:
        return RunResult(
            index=index,
            label=label,
            status="CONFIG_ERROR",
            message=sanitize_message(error, account),
        )
    except APIError as error:
        return RunResult(
            index=index,
            label=label,
            status="UNCONFIRMED"
            if error.code in {"INVALID_RESPONSE", "INVALID_JSON"}
            else "API_ERROR",
            message=sanitize_message(error, account),
            http_status=error.status,
        )


def build_summary(results: Sequence[RunResult]) -> Dict[str, Any]:
    counts: Dict[str, int] = {}
    for result in results:
        counts[result.status] = counts.get(result.status, 0) + 1
    return {
        "type": "SUMMARY",
        "provider": PROVIDER,
        "ok": bool(results) and all(result.ok for result in results),
        "accounts": len(results),
        "claimed": counts.get("CLAIMED", 0),
        "already": counts.get("ALREADY", 0),
        "query": counts.get("QUERY", 0),
        "inactive": counts.get("INACTIVE", 0),
        "manual_required": counts.get("MANUAL_REQUIRED", 0),
        "failed": sum(1 for result in results if not result.ok),
        "status_counts": counts,
    }


def build_report(results: Sequence[RunResult], summary: Dict[str, Any]) -> str:
    lines = [
        "Sub2API Daily",
        "账号：%d；已领取：%d；今日已签：%d；失败：%d"
        % (len(results), summary["claimed"], summary["already"], summary["failed"]),
    ]
    for result in results:
        lines.append(
            "%s 账号%d %s：%s"
            % ("✅" if result.ok else "❌", result.index, result.label, result.message)
        )
    return "\n".join(lines)


def _post_notification(url: str, payload: Dict[str, Any]) -> None:
    requests.post(url, json=payload, timeout=10)


def notify_all(title: str, content: str) -> None:
    pushplus = env_text("PUSHPLUS_TOKEN")
    if pushplus:
        try:
            _post_notification(
                "https://www.pushplus.plus/send",
                {"token": pushplus, "title": title, "content": content, "template": "markdown"},
            )
        except requests.RequestException:
            pass
    wecom = env_text("WECOM_WEBHOOK")
    if wecom:
        try:
            _post_notification(wecom, {"msgtype": "markdown", "markdown": {"content": content}})
        except requests.RequestException:
            pass
    dingtalk = env_text("DINGTALK_WEBHOOK")
    if dingtalk:
        try:
            _post_notification(
                dingtalk,
                {"msgtype": "markdown", "markdown": {"title": title, "text": content}},
            )
        except requests.RequestException:
            pass
    bark = env_text("BARK_URL")
    if bark:
        try:
            requests.get(bark, params={"title": title, "body": content}, timeout=10)
        except requests.RequestException:
            pass
    generic = env_text("GENERIC_WEBHOOK_URL")
    if generic:
        try:
            _post_notification(generic, {"title": title, "content": content})
        except requests.RequestException:
            pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Sub2API daily check-in")
    parser.add_argument("--query", "--status", action="store_true", dest="query", help="read status only")
    parser.add_argument("--only", default="", help="account indexes, e.g. 1,3-4")
    parser.add_argument("--accounts-file", default="", help="account file path")
    parser.add_argument("--wait-seconds", type=float, default=None, help="wait before status readback")
    parser.add_argument("--no-notify", action="store_true", help="disable notifications")
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        accounts = load_accounts(args.accounts_file or None)
        selected = parse_only(args.only, len(accounts))
    except ConfigError as error:
        emit(
            {
                "type": "SUMMARY",
                "provider": PROVIDER,
                "ok": False,
                "accounts": 0,
                "error": sanitize_message(error),
            }
        )
        return 2

    wait_seconds = (
        DEFAULT_WAIT_SECONDS
        if args.wait_seconds is None
        else max(0.0, float(args.wait_seconds))
    )
    if args.wait_seconds is None and env_text(WAIT_ENV):
        try:
            wait_seconds = max(0.0, float(env_text(WAIT_ENV)))
        except ValueError:
            pass

    client = Sub2APIClient(
        wait_seconds=wait_seconds,
        proxy=env_text(PROXY_ENV),
    )
    results: List[RunResult] = []
    for index, account in enumerate(accounts, 1):
        if index not in selected:
            continue
        result = run_account(index, account, client, query_only=args.query)
        results.append(result)
        emit(result.as_dict())

    summary = build_summary(results)
    emit(summary)
    if not args.no_notify:
        notify_all("Sub2API Daily", build_report(results, summary))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
