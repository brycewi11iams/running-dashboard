#!/usr/bin/env python3
"""
Fetch Coros health data and write to data/daily.json.
Run locally after a workout, then push the file to update the dashboard.

Usage (run from the repo root):
  Windows PowerShell:
    $env:COROS_EMAIL="you@example.com"; $env:COROS_PASSWORD="yourpass"; python scripts/fetch_coros.py
    git add data/daily.json && git commit -m "chore: Coros sync" && git push

  macOS / Linux:
    COROS_EMAIL=you@example.com COROS_PASSWORD=yourpass python scripts/fetch_coros.py
    git add data/daily.json && git commit -m "chore: Coros sync" && git push

Endpoint note: Coros does not publish an official API. These endpoints are
derived from community reverse-engineering and may change without notice.
Each fetch is independently try/caught so partial data still writes to disk.
"""
import hashlib
import json
import os
import sys
from datetime import datetime, timezone, timedelta

try:
    import requests
except ImportError:
    print("ERROR: 'requests' not installed. Run: pip install requests", file=sys.stderr)
    sys.exit(1)

BASE = "https://athlete.coros.com"


def login(email: str, password: str) -> tuple:
    """Authenticate. Returns (access_token, user_id)."""
    pwd_hash = hashlib.md5(password.encode("utf-8")).hexdigest()
    resp = requests.post(
        f"{BASE}/account/login",
        json={"account": email, "accountType": 2, "pwd": pwd_hash},
        timeout=30,
    )
    resp.raise_for_status()
    body = resp.json()
    code = body.get("apiCode", "")
    if code != "0000":
        raise RuntimeError(f"Coros login failed (apiCode={code}): {body.get('message', '')}")
    result = body["result"]
    return result["accessToken"], result["userId"]


def api_get(path: str, token: str, user_id: str, params: dict = None) -> dict:
    headers = {"accessToken": token}
    qp = {"userId": user_id, **(params or {})}
    resp = requests.get(f"{BASE}{path}", headers=headers, params=qp, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_sleep(token: str, user_id: str, date_ymd: str) -> dict:
    """date_ymd: YYYYMMDD. Returns normalized sleep dict or None."""
    try:
        data = api_get("/v2/sleep/getMainSleep", token, user_id, {"date": date_ymd})
        if data.get("apiCode") != "0000":
            return None
        r = data.get("result") or {}
        sleep_min = r.get("sleepTime") or r.get("totalSleepTime") or 0
        return {
            "score": r.get("sleepScore"),
            "hours": round(sleep_min / 60, 2),
            "deep_ratio": r.get("deepSleepRatio"),
            "light_ratio": r.get("lightSleepRatio"),
            "rem_ratio": r.get("remSleepRatio"),
            "awake_minutes": r.get("awakeDuration"),
        }
    except Exception as exc:
        print(f"[WARN] Sleep fetch failed for {date_ymd}: {exc}", file=sys.stderr)
        return None


def fetch_hrv(token: str, user_id: str, date_ymd: str) -> dict:
    try:
        data = api_get("/v2/hrv/getHrvInfo", token, user_id, {"date": date_ymd})
        if data.get("apiCode") != "0000":
            return None
        r = data.get("result") or {}
        return {
            "avg": r.get("avgHrv"),
            "baseline": r.get("baselineHrv"),
            "normal_low": r.get("normalLow"),
            "normal_high": r.get("normalHigh"),
            "evaluation": r.get("evaluation"),
        }
    except Exception as exc:
        print(f"[WARN] HRV fetch failed for {date_ymd}: {exc}", file=sys.stderr)
        return None


def fetch_recovery(token: str, user_id: str, date_ymd: str) -> dict:
    try:
        data = api_get("/v2/recovery/getRecovery", token, user_id, {"date": date_ymd})
        if data.get("apiCode") != "0000":
            return None
        r = data.get("result") or {}
        return {
            "percentage": r.get("recoveryPercent"),
            "level": r.get("recoveryLevel"),
        }
    except Exception as exc:
        print(f"[WARN] Recovery fetch failed for {date_ymd}: {exc}", file=sys.stderr)
        return None


def fetch_training_load(token: str, user_id: str, start_ymd: str, end_ymd: str) -> list:
    """Returns list of {date, stl, ltl, ratio, comment} sorted oldest→newest."""
    try:
        data = api_get(
            "/v2/trainingLoad/loadList",
            token,
            user_id,
            {"startDate": start_ymd, "endDate": end_ymd},
        )
        if data.get("apiCode") != "0000":
            return []
        items = (data.get("result") or {}).get("list") or []
        out = []
        for item in items:
            raw_date = str(item.get("date", ""))
            # Date might be YYYYMMDD or YYYY-MM-DD
            if len(raw_date) == 8:
                iso = f"{raw_date[:4]}-{raw_date[4:6]}-{raw_date[6:8]}"
            else:
                iso = raw_date[:10]
            stl = item.get("acl") or item.get("stl") or 0
            ltl = item.get("ctl") or item.get("ltl") or 0
            ratio = round(stl / ltl, 2) if ltl > 0 else 0.0
            out.append({
                "date": iso,
                "stl": stl,
                "ltl": ltl,
                "ratio": ratio,
                "comment": item.get("comment") or "",
            })
        return sorted(out, key=lambda x: x["date"])
    except Exception as exc:
        print(f"[WARN] Training load fetch failed: {exc}", file=sys.stderr)
        return []


def main() -> None:
    email = os.environ.get("COROS_EMAIL", "").strip()
    password = os.environ.get("COROS_PASSWORD", "").strip()
    if not email or not password:
        print("ERROR: COROS_EMAIL and COROS_PASSWORD env vars required.", file=sys.stderr)
        sys.exit(1)

    now_utc = datetime.now(timezone.utc)
    # Central Time: use UTC-5 (approximation; handles both CST/CDT conservatively)
    now_ct = now_utc - timedelta(hours=5)
    today_iso = now_ct.strftime("%Y-%m-%d")
    today_ymd = now_ct.strftime("%Y%m%d")
    week_ago_ymd = (now_ct - timedelta(days=6)).strftime("%Y%m%d")

    print(f"[Coros] Fetching data for {today_iso} (CT) …")

    try:
        token, user_id = login(email, password)
        print(f"[Coros] Authenticated as user {user_id}")
    except Exception as exc:
        print(f"ERROR: Login failed — {exc}", file=sys.stderr)
        sys.exit(1)  # hard fail so you know immediately if credentials are wrong

    sleep = fetch_sleep(token, user_id, today_ymd)
    hrv = fetch_hrv(token, user_id, today_ymd)
    recovery = fetch_recovery(token, user_id, today_ymd)
    tl_list = fetch_training_load(token, user_id, week_ago_ymd, today_ymd)
    today_tl = next((t for t in tl_list if t["date"] == today_iso), None)

    output = {
        "date": today_iso,
        "fetched_at": now_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sleep": sleep,
        "hrv": hrv,
        "rhr": None,  # RHR not available via Coros API for this account
        "recovery": recovery,
        "training_load": today_tl,
        "history": {
            "training_load": tl_list,
        },
    }

    os.makedirs("data", exist_ok=True)
    with open("data/daily.json", "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

    fetched = [k for k, v in output.items() if v is not None and k not in ("date", "fetched_at", "history")]
    print(f"[Coros] Written data/daily.json  fetched: {', '.join(fetched)}")


if __name__ == "__main__":
    main()
