# Deploying SanaTour API to a VPS

End-to-end recipe: blank Ubuntu VPS → public HTTPS API at `https://api.example.com`.

The stack runs as four containers behind Caddy (auto-TLS via Let's Encrypt):

```
Internet ── 443 ──> Caddy ──> app (uvicorn:8000) ──> postgres
                                                 \─> redis
```

## 0. Prerequisites

- A VPS (1 vCPU / 1 GB RAM is enough for v0.1; bump to 2 GB once you add booking).
- A domain you control. DNS **A-record** for `api.example.com` pointing to the VPS public IP.
- SSH access as a non-root user with `sudo`.

## 1. Server bootstrap (one-time)

SSH into the VPS, then:

```bash
# Update + base tools
sudo apt update && sudo apt upgrade -y
sudo apt install -y git ufw

# Firewall — only SSH, HTTP, HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable

# Docker (official convenience script)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER
# log out and back in so the group takes effect
```

## 2. Clone the repo

```bash
git clone https://github.com/<you>/sanotour-api.git
cd sanotour-api
```

## 3. Configure secrets

```bash
cp .env.example .env
```

Open `.env` and switch the values from the LOCAL defaults to the PROD values
(comments in `.env.example` mark which lines change). At minimum, set:

| Variable | How to generate / what to set |
|---|---|
| `DOMAIN` | `api.example.com` (matches your DNS A-record) |
| `POSTGRES_PASSWORD` | `openssl rand -hex 24` |
| `DATABASE_URL` | embed the same password into the URL |
| `JWT_SECRET_KEY` | `openssl rand -hex 32` |
| `INITIAL_SUPER_ADMIN_EMAIL` / `_PASSWORD` | your admin credentials |
| `CORS_ORIGINS` | JSON array of frontend origins, e.g. `["https://app.example.com"]` |

Verify `.env` is **not** tracked by git:

```bash
git check-ignore .env   # should print: .env
```

## 4. First boot

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

What happens:
1. Postgres + Redis start, healthchecks turn green.
2. The `app` container runs `alembic upgrade head` (creates schema), then `python -m scripts.seed` (creates super_admin), then starts uvicorn on `:8000`.
3. Caddy starts, requests a Let's Encrypt cert for `$DOMAIN`, and proxies `:443 → app:8000`.

Watch logs until the app is up:

```bash
docker compose -f docker-compose.prod.yml logs -f app caddy
```

First TLS issuance can take 30–60 seconds. Once Caddy logs `certificate obtained successfully`, the API is live.

## 5. Smoke test

```bash
curl https://api.example.com/api/v1/health
# {"status":"ok"}

# Login as the seeded super_admin
curl -X POST https://api.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"<your INITIAL_SUPER_ADMIN_PASSWORD>"}'
```

OpenAPI docs: `https://api.example.com/docs`.

## 6. Day-to-day operations

### Deploy a new version

```bash
git pull
docker compose -f docker-compose.prod.yml up -d --build app
```

`app` re-runs `alembic upgrade head` on every start, so migrations apply automatically. Postgres and Redis are not recreated.

### View logs

```bash
docker compose -f docker-compose.prod.yml logs -f app
docker compose -f docker-compose.prod.yml logs -f caddy
```

### Database access

```bash
docker compose -f docker-compose.prod.yml exec postgres \
  psql -U sanotour -d sanotour
```

### Backups (manual, on demand)

```bash
docker compose -f docker-compose.prod.yml exec -T postgres \
  pg_dump -U sanotour sanotour | gzip > backup-$(date +%F).sql.gz
```

For automated daily backups, add a cron entry on the host:

```cron
0 3 * * * cd /home/<user>/sanotour-api && docker compose -f docker-compose.prod.yml exec -T postgres pg_dump -U sanotour sanotour | gzip > /home/<user>/backups/sanotour-$(date +\%F).sql.gz
```

### Restore from backup

```bash
gunzip -c backup-2026-05-10.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U sanotour -d sanotour
```

### Stop everything

```bash
docker compose -f docker-compose.prod.yml down
# add -v to also wipe data volumes (DESTRUCTIVE)
```

## 7. Notes and gotchas

- **Postgres and Redis ports are not exposed to the host** in `docker-compose.prod.yml` — they're only reachable from inside the Docker network. Don't add `ports:` mappings unless you also tighten `ufw`.
- **`docker-compose.yml`** (the dev one) still publishes Postgres on `:5432`. Don't run it on the VPS — only use `docker-compose.prod.yml` there.
- **Caddy stores certs in the `caddy_data` volume.** Don't delete it casually — you'll hit Let's Encrypt rate limits if you re-issue too often.
- **`uvicorn` runs single-process.** For v0.1 traffic that's fine; when you need more throughput, switch the `command` to use `--workers N` or put `gunicorn -k uvicorn.workers.UvicornWorker` in front.
- **Health check route:** `/api/v1/health` (no auth). Wire it into UptimeRobot or similar.
