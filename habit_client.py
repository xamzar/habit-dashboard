#!/usr/bin/env python3
"""TickTick Habit API client — reads auth from ~/.hermes/.env."""

import re
import time
import json
import requests
from pathlib import Path

ENV_PATH = Path.home() / ".hermes" / ".env"
API_BASE = "https://api.ticktick.com/open/v1"


def _read_env(var: str) -> str | None:
    if not ENV_PATH.exists():
        return None
    text = ENV_PATH.read_text()
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(f"{var}="):
            val = line[len(var) + 1 :]
            if " #" in val:
                val = val.split(" #")[0]
            val = val.strip("\"'")
            return val
    return None


class HabitClient:
    def __init__(self):
        self._token = None
        self._expires_at = 0

    @property
    def access_token(self) -> str:
        now = time.time()
        if self._token and now < self._expires_at - 60:
            return self._token

        token = _read_env("TICKTICK_ACCESS_TOKEN")
        if not token:
            raise RuntimeError("No TICKTICK_ACCESS_TOKEN in ~/.hermes/.env")
        self._token = token
        exp_str = _read_env("TICKTICK_EXPIRES_AT")
        if exp_str:
            try:
                self._expires_at = float(exp_str)
            except ValueError:
                self._expires_at = now + 3000
        else:
            self._expires_at = now + 3000
        return self._token

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
        }

    # ── Habit API ──────────────────────────────────────────────

    def list_habits(self) -> list[dict]:
        r = requests.get(f"{API_BASE}/habit", headers=self._headers())
        if r.status_code != 200:
            raise RuntimeError(f"List habits failed: {r.status_code} {r.text}")
        return r.json()

    def get_habit(self, habit_id: str) -> dict:
        r = requests.get(f"{API_BASE}/habit/{habit_id}", headers=self._headers())
        if r.status_code != 200:
            raise RuntimeError(f"Get habit failed: {r.status_code} {r.text}")
        return r.json()

    def checkin(self, habit_id: str, stamp: int, value: float = 1.0, goal: float = 1.0) -> dict:
        body = {"stamp": stamp, "value": value, "goal": goal}
        r = requests.post(
            f"{API_BASE}/habit/{habit_id}/checkin",
            headers=self._headers(),
            json=body,
        )
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Check-in failed: {r.status_code} {r.text}")
        try:
            return r.json()
        except Exception:
            return {"status": "checked_in"}

    def get_checkins(self, habit_ids: list[str], from_stamp: int, to_stamp: int) -> list[dict]:
        ids = ",".join(habit_ids)
        r = requests.get(
            f"{API_BASE}/habit/checkins",
            headers=self._headers(),
            params={"habitIds": ids, "from": from_stamp, "to": to_stamp},
        )
        if r.status_code != 200:
            raise RuntimeError(f"Get checkins failed: {r.status_code} {r.text}")
        return r.json()
