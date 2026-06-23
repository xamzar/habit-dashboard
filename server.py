#!/usr/bin/env python3
"""FastAPI server for TickTick habit dashboard."""

import json
import datetime
from pathlib import Path
from collections import defaultdict

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from habit_client import HabitClient

app = FastAPI(title="Habit Dashboard")
client = HabitClient()
THIS_DIR = Path(__file__).parent


# ── Pydantic models ───────────────────────────────────────────

class CheckinRequest(BaseModel):
    habit_id: str
    stamp: int  # YYYYMMDD


class CreateHabitRequest(BaseModel):
    name: str
    goal: float = 1.0
    repeat_rule: str = "RRULE:FREQ=DAILY;INTERVAL=1"


# ── Helpers ────────────────────────────────────────────────────

def _today_stamp() -> int:
    """Return today's date in HKT (UTC+8)."""
    import datetime as _dt
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    now_hkt = now_utc + _dt.timedelta(hours=8)
    return int(now_hkt.strftime("%Y%m%d"))


def _days_ago(days: int) -> int:
    """Return date N days ago in HKT."""
    import datetime as _dt
    now_utc = _dt.datetime.now(_dt.timezone.utc)
    now_hkt = now_utc + _dt.timedelta(hours=8)
    d = now_hkt.date() - _dt.timedelta(days=days)
    return int(d.strftime("%Y%m%d"))


def _compute_streak(checkin_dates: set[int], today: int) -> int:
    """Count consecutive days ending at `today`."""
    import datetime as _dt
    streak = 0
    d = today
    while d in checkin_dates:
        streak += 1
        # step back one day
        dt = _dt.datetime.strptime(str(d), "%Y%m%d") - _dt.timedelta(days=1)
        d = int(dt.strftime("%Y%m%d"))
    return streak


def _habit_with_stats(h: dict, checkins: dict[str, set[int]], today: int) -> dict:
    hid = h["id"]
    dates = checkins.get(hid, set())
    streak = _compute_streak(dates, today)
    checked_today = today in dates

    # weekly completion (last 7 days)
    last7 = sum(1 for d in range(_days_ago(6), today + 1) if d in dates)
    # monthly completion
    last30 = sum(1 for d in range(_days_ago(29), today + 1) if d in dates)

    return {
        **h,
        "streak": streak,
        "checked_today": checked_today,
        "completion_7d": last7,
        "completion_30d": last30,
        "total_checkins": len(dates),
    }


# ── API Routes ─────────────────────────────────────────────────

@app.get("/api/github")
def github_stats():
    """Return GitHub contribution stats via GraphQL."""
    import subprocess, json as _json
    query = """
    query {
      viewer {
        contributionsCollection {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                contributionCount
                date
                color
              }
            }
          }
        }
      }
    }
    """
    try:
        result = subprocess.run(
            ["gh", "api", "graphql", "-f", f"query={query}"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip())
        data = _json.loads(result.stdout)
        cal = data["data"]["viewer"]["contributionsCollection"]["contributionCalendar"]

        # Flatten all days
        all_days = []
        for week in cal["weeks"]:
            for day in week["contributionDays"]:
                all_days.append({
                    "date": day["date"],
                    "count": day["contributionCount"],
                    "color": day["color"],
                })

        # Compute stats from last 365 days
        today_str = all_days[-1]["date"] if all_days else ""
        today_count = all_days[-1]["count"] if all_days else 0

        # Streak: count consecutive days (backward from today) with commits
        streak = 0
        for day in reversed(all_days):
            if day["count"] > 0:
                streak += 1
            else:
                break

        # Last 7 and 30 days
        last7 = [d for d in all_days[-7:]]
        last30 = [d for d in all_days[-30:]]
        commits_7d = sum(d["count"] for d in last7)
        commits_30d = sum(d["count"] for d in last30)

        # Percent of days with commits
        active_7d = sum(1 for d in last7 if d["count"] > 0)
        active_30d = sum(1 for d in last30 if d["count"] > 0)

        return {
            "total": cal["totalContributions"],
            "today": {"date": today_str, "count": today_count},
            "streak": streak,
            "commits_7d": commits_7d,
            "commits_30d": commits_30d,
            "active_7d": active_7d,
            "active_30d": active_30d,
            "days": all_days,  # full year for heatmap
            "last30": last30,  # last 30 for quick display
        }
    except Exception as e:
        raise HTTPException(502, f"GitHub API error: {e}")

@app.get("/api/habits")
def get_habits():
    """Return all habits with computed stats (streaks, completion rates)."""
    try:
        habits = client.list_habits()
    except Exception as e:
        raise HTTPException(502, f"TickTick API error: {e}")

    if not habits:
        return {"habits": [], "today": _today_stamp()}

    # Get checkins for the last 30 days for all habits
    today = _today_stamp()
    from_stamp = _days_ago(29)
    to_stamp = _days_ago(-1)  # exclusive: include today
    habit_ids = [h["id"] for h in habits]

    try:
        checkin_data = client.get_checkins(habit_ids, from_stamp, to_stamp)
    except Exception as e:
        raise HTTPException(502, f"TickTick checkins error: {e}")

    # Build habit_id → set of checked-in date stamps
    checkins: dict[str, set[int]] = defaultdict(set)
    for entry in checkin_data:
        hid = entry["habitId"]
        for ci in entry.get("checkins", []):
            checkins[hid].add(ci["stamp"])

    enriched = [_habit_with_stats(h, checkins, today) for h in habits]
    # Attach check-in date sets for heatmap rendering
    for h in enriched:
        h["_checkin_dates"] = sorted(list(checkins.get(h["id"], set())))
    return {"habits": enriched, "today": today}


@app.get("/api/habits/{habit_id}")
def get_habit(habit_id: str):
    """Get a single habit with 30-day check-in data."""
    try:
        habit = client.get_habit(habit_id)
    except Exception as e:
        raise HTTPException(502, f"TickTick API error: {e}")

    today = _today_stamp()
    from_stamp = _days_ago(29)
    to_stamp = _days_ago(-1)  # exclusive: include today

    try:
        checkin_data = client.get_checkins([habit_id], from_stamp, to_stamp)
    except Exception as e:
        raise HTTPException(502, f"TickTick checkins error: {e}")

    dates: set[int] = set()
    for entry in checkin_data:
        for ci in entry.get("checkins", []):
            dates.add(ci["stamp"])

    result = _habit_with_stats(habit, {habit_id: dates}, today)
    result["_checkin_dates"] = sorted(list(dates))
    return result


@app.post("/api/habits/{habit_id}/checkin")
def checkin_habit(habit_id: str, body: CheckinRequest | None = None):
    """Check in to a habit for today (or a specific date)."""
    stamp = body.stamp if body else _today_stamp()
    try:
        result = client.checkin(habit_id, stamp)
    except Exception as e:
        raise HTTPException(502, f"TickTick API error: {e}")
    return result


@app.post("/api/habits")
def create_habit(body: CreateHabitRequest):
    """Create a new habit in TickTick."""
    import requests as req
    payload = {
        "name": body.name,
        "goal": body.goal,
        "repeatRule": body.repeat_rule,
        "type": "Boolean",
        "step": 1.0,
        "unit": "Count",
        "recordEnable": False,
    }
    r = req.post(
        "https://api.ticktick.com/open/v1/habit",
        headers=client._headers(),
        json=payload,
    )
    if r.status_code not in (200, 201):
        raise HTTPException(r.status_code, f"TickTick error: {r.text}")
    return r.json()


# ── Dashboard HTML ─────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def dashboard():
    html_path = THIS_DIR / "dashboard.html"
    if html_path.exists():
        return html_path.read_text()
    return "<h1>dashboard.html not found</h1>"


# ── Health ─────────────────────────────────────────────────────

@app.get("/health")
def health():
    try:
        client.list_habits()
        ticktick = "ok"
    except Exception as e:
        ticktick = str(e)
    return {"status": "ok", "ticktick": ticktick}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8090)
