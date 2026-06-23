# Habit Dashboard

Read-only mirror of TickTick habits + GitHub commit activity. Dark-themed dashboard with streaks, completion rates, and 30-day heatmaps.

**https://habits.xmzr.dev**

## Stack

- **Backend:** FastAPI (Python) on port 8090
- **Frontend:** Vanilla HTML/CSS/JS (GitHub dark theme)
- **Data:** TickTick Open API (habits) + GitHub GraphQL (commits)
- **Hosting:** Cloudflare Tunnel → systemd user service

## Files

| File | Purpose |
|------|---------|
| `server.py` | FastAPI backend — `/api/habits`, `/api/github`, serves dashboard |
| `habit_client.py` | TickTick Habit API client (OAuth, check-ins) |
| `dashboard.html` | Frontend — hero stats, GitHub card, habit cards |

## Setup

```bash
python3 -m venv .venv
.venv/bin/pip install fastapi uvicorn requests

# Needs TickTick OAuth token in ~/.hermes/.env (TICKTICK_ACCESS_TOKEN)
# Needs GitHub CLI (gh) authenticated for contribution data
```

## Deploy

```bash
# Systemd user service
systemctl --user enable --now habits.service

# Tunnel ingress added to ~/.cloudflared/config.yml:
#   - hostname: habits.xmzr.dev
#     service: http://127.0.0.1:8090
```
