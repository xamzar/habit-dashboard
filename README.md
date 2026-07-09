# Habit Dashboard

A personal dashboard that mirrors your [TickTick](https://ticktick.com) habits alongside your GitHub commit activity. Streaks, weekly/monthly completion rates, and 30-day heatmaps in a dark, GitHub-styled UI.

**Live:** https://habits.xmzr.dev

The dashboard is primarily a read-only mirror, but the backend also exposes write endpoints to check in and create habits (see [API](#api)).

## Stack

- **Backend:** FastAPI (Python) on `127.0.0.1:8090`
- **Frontend:** Vanilla HTML/CSS/JS (single file, GitHub dark theme)
- **Data:** TickTick Open API (habits + check-ins) and GitHub GraphQL (contributions)
- **Hosting:** Cloudflare Tunnel in front of a systemd user service

All dates are computed in Hong Kong time (UTC+8).

## Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI backend — API routes, stat computation, serves the dashboard |
| `habit_client.py` | TickTick Habit API client (token, list/get/checkin/checkins) |
| `dashboard.html` | Frontend — hero stats, GitHub card, per-habit cards + heatmaps |

## Setup

### 1. Install

```bash
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn requests
```

### 2. TickTick auth

The client reads a bearer token from `~/.hermes/.env`:

```ini
TICKTICK_ACCESS_TOKEN=your_ticktick_oauth_access_token
# optional — used to know when the token expires (unix seconds)
TICKTICK_EXPIRES_AT=1750000000
```

Get the token by registering an app in the [TickTick Developer Center](https://developer.ticktick.com) and completing the OAuth flow to obtain an access token. If `TICKTICK_EXPIRES_AT` is absent, the client assumes the token is valid for ~50 minutes.

### 3. GitHub auth

Contribution data comes from `gh api graphql`, so the [GitHub CLI](https://cli.github.com) must be installed and authenticated as the user whose commits you want to show:

```bash
gh auth login
```

### 4. Run

```bash
.venv/bin/python server.py
# or
.venv/bin/uvicorn server:app --host 127.0.0.1 --port 8090
```

Open http://127.0.0.1:8090.

## API

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | The dashboard HTML |
| `GET` | `/health` | Server + TickTick connectivity check |
| `GET` | `/api/github` | GitHub contribution stats (total, streak, 7/30-day counts, full-year days) |
| `GET` | `/api/habits` | All habits with computed stats and 30-day check-in dates |
| `GET` | `/api/habits/{id}` | A single habit with 30-day check-in data |
| `POST` | `/api/habits/{id}/checkin` | Check in to a habit (body: `{"habit_id", "stamp"}`; `stamp` is `YYYYMMDD`, defaults to today) |
| `POST` | `/api/habits` | Create a habit (body: `{"name", "goal"?, "repeat_rule"?}`) |

Example:

```bash
curl http://127.0.0.1:8090/api/habits
curl -X POST http://127.0.0.1:8090/api/habits \
  -H 'content-type: application/json' \
  -d '{"name": "Read", "goal": 1.0}'
```

## Deploy

Run as a systemd user service and expose it through a Cloudflare Tunnel:

```bash
systemctl --user enable --now habits.service
```

```yaml
# ~/.cloudflared/config.yml ingress
  - hostname: habits.xmzr.dev
    service: http://127.0.0.1:8090
```
