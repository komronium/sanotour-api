# SanaTour API

Backend for the SanaTour aggregator — a B2B/B2C platform for booking
Uzbekistan sanatoriums with a built-in markup engine for travel agents.

**Stack:** FastAPI · PostgreSQL · Redis · SQLAlchemy 2 (async) · Alembic · JWT auth · uv

## Status

| Iteration | Scope | State |
|---|---|---|
| v0.1 | Auth + User + RBAC | shipped |
| **v0.2** | Sanatorium CRUD + media | current |
| v0.3 | Rooms + availability + markup engine | planned |
| v0.4 | Booking flow (no payment) | planned |

See [`docs/ROADMAP.md`](docs/ROADMAP.md) for the 28-day plan and
[`docs/TZ.md`](docs/TZ.md) for the full spec.

## Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dep management
- Docker + Docker Compose (for Postgres and Redis)

## Setup

```bash
# 1. Install dependencies
uv sync

# 2. Copy and edit env
cp .env.example .env
# Edit .env — set JWT_SECRET_KEY, INITIAL_SUPER_ADMIN_EMAIL/PASSWORD

# 3. Start Postgres + Redis
docker compose up -d

# 4. Run migrations
uv run alembic upgrade head

# 5. Create test database (one-time, for pytest)
docker exec sanotour-postgres psql -U sanotour -d sanotour \
  -c "CREATE DATABASE sanotour_test;"

# 6. Seed initial super_admin
uv run python -m scripts.seed

# 7. Start dev server (port 8000 may be occupied locally — use 8001)
uv run uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

API docs: http://127.0.0.1:8001/docs

## Authentication

The API uses JWT bearer tokens.

**Get a token:**
```bash
curl -X POST http://127.0.0.1:8001/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"yourpassword"}'
```

**Use it in Swagger UI:**
1. Open `/docs`
2. Click **Authorize**
3. Paste the `access_token` value (no `Bearer ` prefix needed)
4. All protected endpoints will now include the token automatically

**Roles:** `super_admin` (platform), `admin` (sanatorium), `agent` (B2B), `customer` (B2C)

## Endpoints

### Health + auth (v0.1)

| Method | Path | Auth |
|---|---|---|
| `GET` | `/api/v1/health` | — |
| `GET` | `/api/v1/health/db` | — |
| `POST` | `/api/v1/auth/register` | — (creates customer) |
| `POST` | `/api/v1/auth/login` | — |
| `POST` | `/api/v1/auth/refresh` | — (refresh token in body) |

### Users (v0.1)

| Method | Path | Auth |
|---|---|---|
| `GET` | `/api/v1/users/me` | any role |
| `GET` | `/api/v1/users` | super_admin |
| `GET` | `/api/v1/users/{id}` | super_admin |
| `PATCH` | `/api/v1/users/{id}` | super_admin |

### Sanatoriums (v0.2)

| Method | Path | Auth | Notes |
|---|---|---|---|
| `GET` | `/api/v1/sanatoriums` | optional | filters: `city`, `status`, `stars`, `q` (name search); `sort=name\|stars\|created_at` (prefix `-` for desc); `limit`, `offset` |
| `GET` | `/api/v1/sanatoriums/{id}` | optional | public sees only approved; admin sees own; super_admin sees all |
| `POST` | `/api/v1/sanatoriums` | super_admin | creates with `status=pending` |
| `PATCH` | `/api/v1/sanatoriums/{id}` | super_admin or owning admin | name change auto-regenerates slug |
| `POST` | `/api/v1/sanatoriums/{id}/approve` | super_admin | flips status to `approved` |
| `POST` | `/api/v1/sanatoriums/{id}/images` | super_admin or owning admin | multipart; JPEG/PNG/WebP up to 10 MB; `caption`, `is_primary`, `order` form fields |

Image files are served from `/uploads/...` (FastAPI `StaticFiles` in dev; nginx in prod).

## Tests

```bash
uv run pytest
```

Tests use a separate database (`sanotour_test`) and recreate the schema once
per session. See [`tests/conftest.py`](tests/conftest.py) for fixtures.

## Project layout

```
app/
  api/v1/routers/   # HTTP routers
  api/deps.py       # auth deps (HTTPBearer, get_current_user, require_roles)
  core/             # config, database, security (bcrypt, JWT)
  models/           # SQLAlchemy models
  schemas/          # Pydantic schemas
  services/         # business logic
alembic/            # migrations
scripts/            # seed.py
tests/              # pytest fixtures + tests
docs/               # TZ.md, ROADMAP.md
```

## Tooling

```bash
uv run alembic revision --autogenerate -m "..."   # new migration
uv run alembic upgrade head                       # apply
uv run alembic downgrade -1                       # roll back one
uv run ruff check .                               # lint
uv run ruff format .                              # format
docker compose down -v                            # nuke local DB
```
