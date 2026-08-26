"""Thames Water account API client.

Reverse-engineered client for the "My Account" portal at
https://myaccount.thameswater.co.uk.

Authentication uses an Azure AD B2C user journey
(``B2C_1_ORAM_Prod_SignIn``) with ``response_type=id_token`` and
``response_mode=form_post``. The sequence is:

1. ``GET /mydashboard/my-meters-usage`` -> redirected to the B2C
   ``authorize`` endpoint which renders a self-asserted sign-in page
   containing a ``SETTINGS`` blob (csrf + transaction id).
2. ``POST .../SelfAsserted`` with ``request_type=RESPONSE`` and the
   credentials.
3. ``GET .../api/CombinedSigninAndSignup/confirmed`` which returns an
   auto-submitting HTML form containing the ``id_token``.
4. ``POST`` that form to ``https://myaccount.thameswater.co.uk/login``
   which establishes the ``OAUTH`` session cookie.

Usage data is then fetched from two JSON AJAX endpoints that require an
``X-Requested-With`` header and a matching ``Referer``.
"""

from __future__ import annotations

import html
import json
import re
import time
from datetime import datetime
from typing import Any, Optional

import requests

try:  # Imported as part of the Home Assistant package.
    from .const import (
        B2C_API,
        B2C_POLICY,
        B2C_TENANT_PATH,
        BASE_URL,
        GET_CONSUMPTION_PATH,
        GET_METERS_PATH,
        LOGIN_HOST,
        USER_AGENT,
        USAGE_PATH,
    )
except ImportError:  # pragma: no cover - standalone execution.
    from const import (  # type: ignore[no-redef]
        B2C_API,
        B2C_POLICY,
        B2C_TENANT_PATH,
        BASE_URL,
        GET_CONSUMPTION_PATH,
        GET_METERS_PATH,
        LOGIN_HOST,
        USER_AGENT,
        USAGE_PATH,
    )

# How long (seconds) a session is considered fresh before we re-validate it.
SESSION_MAX_AGE = 25 * 60


class ThamesWaterError(Exception):
    """Generic Thames Water API error."""


class ThamesWaterAuthError(ThamesWaterError):
    """Raised when authentication fails."""


def _extract_json_object(text: str, marker: str) -> Optional[dict]:
    """Extract the first JSON object following *marker* using brace counting."""
    start = text.find(marker)
    if start == -1:
        return None
    brace = text.find("{", start)
    if brace == -1:
        return None
    depth = 0
    in_string = False
    escaped = False
    for i in range(brace, len(text)):
        char = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    return json.loads(text[brace : i + 1])
                except json.JSONDecodeError:
                    return None
    return None


class ThamesWaterClient:
    """Blocking HTTP client for the Thames Water My Account portal."""

    def __init__(
        self,
        session: requests.Session,
        email: str,
        password: str,
        account_number: str | None = None,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._account_number = account_number
        self._last_login: float = 0.0
        self._meters: list[str] = []
        self._account: dict[str, Any] = {}

    # ------------------------------------------------------------------
    # Authentication
    # ------------------------------------------------------------------
    @property
    def _referer(self) -> str:
        if self._account_number:
            return f"{BASE_URL}{USAGE_PATH}?contractAccountNumber={self._account_number}"
        return f"{BASE_URL}{USAGE_PATH}"

    def _prepare_session(self) -> None:
        self._session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept-Language": "en-GB,en;q=0.9",
            }
        )

    def login(self) -> None:
        """Perform the full B2C sign-in flow and establish the session."""
        self._prepare_session()
        # Start clean: drop any stale auth cookies from a previous session.
        for cookie in list(self._session.cookies):
            if cookie.name in ("OAUTH", "JSESSIONID", "LoggedIntoMyAccount"):
                self._session.cookies.pop(cookie.name)

        # 1. Land on the B2C self-asserted sign-in page.
        response = self._session.get(self._referer, allow_redirects=True, timeout=60)
        response.raise_for_status()

        settings = _extract_json_object(response.text, "var SETTINGS")
        if not settings:
            # We may already be signed in (the page renders the dashboard).
            if "My water use" in response.text or "TW.bus.account" in response.text:
                self._last_login = time.time()
                self._cache_account(response.text)
                return
            raise ThamesWaterAuthError("Unable to locate the sign-in form.")

        csrf = settings.get("csrf")
        trans_id = settings.get("transId")
        hosts = settings.get("hosts", {})
        tenant = hosts.get("tenant", B2C_TENANT_PATH)
        policy = hosts.get("policy", B2C_POLICY)
        api = settings.get("api", B2C_API)

        if not csrf or not trans_id:
            raise ThamesWaterAuthError("Sign-in form missing CSRF/transaction data.")

        # 2. Submit credentials to the SelfAsserted endpoint.
        self_asserted = (
            f"{LOGIN_HOST}{tenant}/SelfAsserted"
        )
        resp = self._session.post(
            self_asserted,
            params={"tx": trans_id, "p": policy},
            data={
                "request_type": "RESPONSE",
                "email": self._email,
                "password": self._password,
            },
            headers={"X-CSRF-TOKEN": csrf},
            allow_redirects=False,
            timeout=60,
        )
        resp.raise_for_status()
        if resp.text.strip() != '{"status":"200"}':
            raise ThamesWaterAuthError(
                "Incorrect email or password (or account is locked)."
            )

        # 3. Fetch the confirmed page which contains the id_token form.
        confirmed = (
            f"{LOGIN_HOST}{tenant}/api/{api}/confirmed"
        )
        resp = self._session.get(
            confirmed,
            params={
                "rememberMe": "false",
                "csrf_token": csrf,
                "tx": trans_id,
                "p": policy,
            },
            allow_redirects=False,
            timeout=60,
        )
        resp.raise_for_status()

        fields = self._parse_auto_submit_form(resp.text)
        if "id_token" not in fields:
            raise ThamesWaterAuthError("Sign-in did not return an id_token.")

        # 4. Post the id_token back to My Account to create the session.
        action = fields.pop("__action", f"{BASE_URL}/login")
        resp = self._session.post(
            action, data=fields, allow_redirects=True, timeout=60
        )
        resp.raise_for_status()

        self._last_login = time.time()
        self._cache_account(resp.text)

    @staticmethod
    def _parse_auto_submit_form(text: str) -> dict[str, str]:
        """Parse a ``<form>`` with hidden inputs (B2C form_post payload)."""
        form_match = re.search(
            r"<form[^>]*action=['\"]([^'\"]+)['\"]", text, re.IGNORECASE
        )
        fields: dict[str, str] = {}
        if form_match:
            fields["__action"] = html.unescape(form_match.group(1))
        for name, value in re.findall(
            r"<input[^>]*name=['\"]([^'\"]+)['\"][^>]*value=['\"]([^'\"]*)['\"]",
            text,
            re.IGNORECASE,
        ):
            fields[html.unescape(name)] = html.unescape(value)
        return fields

    def _cache_account(self, page_text: str) -> None:
        match = re.search(
            r"TW\.bus\.account\s*=\s*(\{.*?\});", page_text, re.DOTALL
        )
        if not match:
            return
        try:
            self._account = json.loads(match.group(1))
        except json.JSONDecodeError:
            self._account = {}

    def _ensure_authenticated(self) -> None:
        if self._last_login and (time.time() - self._last_login) < SESSION_MAX_AGE:
            return
        self.login()

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _ajax_headers(self) -> dict[str, str]:
        return {"X-Requested-With": "XMLHttpRequest", "Referer": self._referer}

    def _request(self, path: str, params: dict[str, Any] | None = None) -> dict:
        self._ensure_authenticated()
        response = self._session.get(
            f"{BASE_URL}{path}",
            params=params,
            headers=self._ajax_headers(),
            timeout=60,
        )
        redirected_to_login = (
            "login.thameswater.co.uk" in response.url
            or "/Account/SignIn" in response.url
            or "var SETTINGS" in response.text[:2000]
        )
        if response.status_code == 403 or redirected_to_login:
            # Session expired / not authorised - retry once after re-login.
            self._last_login = 0.0
            self.login()
            response = self._session.get(
                f"{BASE_URL}{path}",
                params=params,
                headers=self._ajax_headers(),
                timeout=60,
            )
        response.raise_for_status()
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise ThamesWaterError("Unexpected non-JSON response.") from exc

    def get_meters(self) -> dict:
        """Return the raw ``getMeters`` payload."""
        return self._request(GET_METERS_PATH)

    def get_consumption(
        self,
        meter: str,
        granularity: str,
        start_date: str,
        start_month: str,
        start_year: str,
        end_date: str,
        end_month: str,
        end_year: str,
    ) -> dict:
        """Return the raw ``getSmartWaterMeterConsumptions`` payload."""
        return self._request(
            GET_CONSUMPTION_PATH,
            {
                "meter": meter,
                "startDate": start_date,
                "startMonth": start_month,
                "startYear": start_year,
                "endDate": end_date,
                "endMonth": end_month,
                "endYear": end_year,
                "granularity": granularity,
                "premiseId": "",
                "isForC4C": "false",
            },
        )

    @staticmethod
    def _parse_period_key(key: str) -> tuple[str, str, str]:
        """Parse a period key ``DDMMYYYYDDMMYYYY`` into (start, end) tuples."""
        return (
            (key[0:2], key[2:4], key[4:8]),
            (key[8:10], key[10:12], key[12:16]),
        )

    def get_usage(self) -> dict[str, Any]:
        """Fetch a normalised snapshot of water-usage data."""
        meters = self.get_meters()
        meter_list = meters.get("Meters") or []
        self._meters = [str(m) for m in meter_list]

        lines_30d = meters.get("Lines") or []
        daily_options = meters.get("Daily") or []
        monthly_options = meters.get("Monthly") or []

        # Determine the most recent available day from the Daily options.
        latest_day: tuple[str, str, str] | None = None
        if daily_options:
            latest_day = self._parse_period_key(daily_options[0]["Key"])[0]

        meter = self._meters[0] if self._meters else ""

        hourly_lines: list[dict] = []
        latest_read: float | None = None
        latest_read_dt: datetime | None = None
        latest_hour_usage: float | None = None

        if meter and latest_day:
            dd, mm, yyyy = latest_day
            hourly = self.get_consumption(
                meter, "H", dd, mm, yyyy, dd, mm, yyyy
            )
            hourly_lines = hourly.get("Lines") or []
            if hourly_lines:
                last = hourly_lines[-1]
                latest_read = float(last.get("Read") or 0)
                latest_hour_usage = float(last.get("Usage") or 0)
                label = str(last.get("Label", "0:00"))
                hour = int(label.split(":")[0]) if ":" in label else 0
                latest_read_dt = datetime(
                    int(yyyy), int(mm), int(dd), hour
                )

        # The daily view's per-day figure is authoritative (the hourly
        # "Usage" column does not always reconcile with the daily read).
        # Data typically lags a couple of days, so report the most recent
        # available day rather than "today".
        latest_day_usage = (
            float(lines_30d[-1].get("Usage") or 0) if lines_30d else None
        )

        last_30d_usage = sum(float(l.get("Usage") or 0) for l in lines_30d)

        average_usage = meters.get("AverageUsage")
        actual_usage = meters.get("ActualUsage")

        result: dict[str, Any] = {
            "meters": self._meters,
            "account_number": (
                self._account.get("Number") or self._account_number
            ),
            "premise_id": self._account.get("PremiseID"),
            "premise_address": self._account.get("FullPremiseAddress"),
            "latest_read": latest_read,
            "latest_read_dt": latest_read_dt,
            "latest_day_usage": latest_day_usage,
            "latest_hour_usage": latest_hour_usage,
            "last_30d_usage": last_30d_usage,
            "average_daily_usage": average_usage,
            "actual_usage": actual_usage,
            "is_estimated": bool(
                hourly_lines[-1].get("IsEstimated") if hourly_lines else False
            ),
            "hourly": hourly_lines,
            "daily": lines_30d,
            "daily_options": daily_options,
            "monthly_options": monthly_options,
        }
        return result
