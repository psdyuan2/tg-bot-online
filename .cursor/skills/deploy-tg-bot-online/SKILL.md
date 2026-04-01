---
name: deploy-tg-bot-online
description: Deploys the tg-bot-online Telegram backend to the production VPS over SSH (git pull, venv, Alembic, PM2). Use when the user asks to deploy this project, update the remote server, sync .env, or restart tg-bot-online after changes.
---

# Deploy tg-bot-online (SSH + PM2)

This project runs **three** aiogram bots (admin, notify, benefit) in **one** Python process under PM2. The server does **not** use Docker; deployment uses `~/tg-bot-online`, a project-local `.venv`, and `run_bot.sh`.

## Prerequisites

- SSH access to the VPS as `ubuntu` (or your deploy user) with a key loaded (`ssh-add` / `ssh-agent`).
- Remote path: `~/tg-bot-online` (clone of this repo).
- On the server: `python3-venv`, `git`, `pm2`; first-time setup already created `.venv` and `pm2 start …/run_bot.sh --name tg-bot-online`.
- Local `.env` must include `ADMIN_BOT_TOKEN`, `NOTIFY_BOT_TOKEN`, `BENEFIT_BOT_TOKEN`, `DATABASE_URL`, and other vars per [.env.example](.env.example). Do **not** commit `.env`.

## Configuration (optional)

Create a **gitignored** file `env` at the repo root (same idea as `env.example` in older workflows) if you want scripted `ssh`/`scp` targets:

```bash
ip=<VPS_PUBLIC_IP>
user_name=ubuntu
```

Never put tokens or passwords in `env`.

## Deploy workflow

Execute from the **project root** on your machine.

1. **Commit and push** code (if there are local commits):

   ```bash
   git status
   git push origin main
   ```

2. **Upload environment** (overwrites remote secrets):

   ```bash
   scp .env ${user_name}@${ip}:~/tg-bot-online/.env
   ```

   If `.env` contains stray lines like `remote_server_*`, remove them on the server so only app keys remain:

   ```bash
   ssh ${user_name}@${ip} "sed -i.bak '/^remote_server/d' ~/tg-bot-online/.env"
   ```

3. **On the server: pull, deps, migrations, restart**:

   ```bash
   ssh ${user_name}@${ip} 'set -e
   cd ~/tg-bot-online
   git pull origin main
   .venv/bin/pip install -q -r requirements.txt
   .venv/bin/alembic upgrade head
   pm2 restart tg-bot-online --update-env
   pm2 save
   '
   ```

   Replace `${user_name}` / `${ip}` with values from your `env` file or type them explicitly (e.g. `ubuntu@43.133.43.126`).

4. **Verify**:

   ```bash
   ssh ${user_name}@${ip} "pm2 list && pm2 logs tg-bot-online --lines 25 --nostream"
   ```

   Expect **three** `Run polling` lines (admin bot, notify bot, benefit bot). If `BENEFIT_BOT_TOKEN` is missing or invalid, the process may exit or omit the third bot.

## Coexistence with other services

- This app **does not bind HTTP ports** (long polling only). It must not conflict with other Node/PM2 apps on the same host unless another process steals Telegram updates with the **same** bot token (avoid duplicate processes).

## Troubleshooting

| Issue | Action |
|-------|--------|
| `python3-venv` missing | `sudo apt-get install -y python3.12-venv` (adjust version) |
| Alembic fails | Ensure `DATABASE_URL` on the server points to a writable path (e.g. under `~/tg-bot-online/data/`) |
| PM2 shows `errored` | `pm2 logs tg-bot-online --lines 80`; often missing `BENEFIT_BOT_TOKEN` or bad `.env` syntax |
| Old code on server | Confirm `git pull` ran and branch is `main` |

## One-liner (after `scp` and optional `sed`)

```bash
ssh ubuntu@<VPS_IP> 'cd ~/tg-bot-online && git pull origin main && .venv/bin/pip install -q -r requirements.txt && .venv/bin/alembic upgrade head && pm2 restart tg-bot-online --update-env && pm2 save'
```

Use the real `ubuntu@<VPS_IP>` for your environment.
