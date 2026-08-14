# LogiConnect API (backend)

FastAPI backend for the LogiConnect / FindMyGP prototype — real auth, persistence,
payments, real-time tracking & messaging, real geocoding/pricing, and a
pluggable carrier-API integration layer (Chronopost / Colissimo / DHL).

## Stack

- **FastAPI** + **SQLAlchemy 2.0 (async)** + **PostgreSQL**
- **JWT** auth (access + refresh tokens)
- **Stripe** for payments (test mode by default)
- **Mapbox** for geocoding + distance (real road distance domestically, great-circle for the Dakar↔France air/sea corridor)
- **WebSockets** for live tracking updates and messaging delivery
- Carrier integrations use an **adapter pattern**: a mock/simulation adapter runs by
  default; the moment you set a real API key in `.env`, the matching real adapter
  is used automatically — no code changes required.

## Quick start (local dev)

Requires Docker (for Postgres) and Python 3.9+.

```bash
cd backend
cp .env.example .env        # fill in real secrets as you get them — safe to leave blank for now
docker compose up -d db     # starts only Postgres
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # loads the 17 prototype carriers into the DB
uvicorn app.main:app --reload
```

API docs: http://localhost:8000/docs

## Full stack via Docker Compose

```bash
cd backend
cp .env.example .env
docker compose up --build
```

## Environment variables

See `.env.example` for the full list. Nothing in the app hard-fails at startup if
a third-party key is missing — it degrades gracefully:

| Missing key | Behavior |
|---|---|
| `MAPBOX_ACCESS_TOKEN` | Distance falls back to a fixed estimate (25 km) instead of a real geocoded distance. |
| `STRIPE_SECRET_KEY` | Payment endpoints return `503` with a clear message instead of crashing. |
| `CHRONOPOST_API_KEY` / `COLISSIMO_API_KEY` / `DHL_API_KEY` | That carrier's tracking uses the built-in simulation adapter instead of the real network. |

**Never commit `.env`** — it's gitignored. Only `.env.example` (placeholders) is tracked.

## Carrier API integrations — current status

Chronopost, Colissimo, and DHL all require a merchant/developer account and a
signed contract before their real tracking APIs can be called — this repo
does **not** include real credentials for any of them. What's implemented:

- `app/services/carriers/base.py` — the adapter interface every carrier plugs into.
- `app/services/carriers/mock_adapter.py` — default adapter, simulates a realistic
  status progression on an accelerated clock so the whole booking → tracking flow
  is demoable today.
- `app/services/carriers/{chronopost,colissimo,dhl}_adapter.py` — **best-effort
  skeletons**, not verified against a live account. The endpoint shapes are based
  on each network's historically documented APIs and **must be checked against
  current official docs** (and your actual contract) before going live.
- `app/services/carriers/registry.py` — picks the real adapter if its API key is
  set in `.env`, otherwise silently falls back to the mock adapter.

Three seeded carriers are pre-wired to a network for demo purposes: **France
Colis National** → Colissimo, **RoutePartner Colis** → Chronopost, **Téranga Air
Cargo** → DHL. All three currently run on the mock adapter since no real keys
are configured.

## Real-time

- `GET /ws/tracking/{booking_id}?token=<jwt access token>` — pushes a JSON
  message for every new tracking status.
- `GET /ws/messaging/{conversation_id}?token=<jwt access token>` — pushes a
  JSON message for every new chat message.

Both check that the connecting user is a participant (client or the assigned
carrier) before accepting the connection.

## Known simplifications (be aware before going to production)

- **Schema management**: tables are created with `Base.metadata.create_all` on
  startup rather than Alembic migrations. Fine for an MVP; add Alembic before
  you need to evolve the schema without dropping data.
- **Real carrier shipment creation** (`create_shipment` on the real adapters)
  raises `NotImplementedError` — only tracking retrieval is scaffolded, since
  label/shipment creation needs contract-specific request shapes.
- **No rate limiting / abuse protection** on public endpoints yet.
- **No email verification / password reset flow** — registration is instant.

## Deployment

The `Dockerfile` + `docker-compose.yml` are deploy-ready for Railway, Render, or
Fly.io — point any of them at this `backend/` directory, set the same env vars
from `.env.example` in their dashboard, and provision a managed Postgres
(or use the `db` service for smaller deployments). The API binds to
`0.0.0.0:8000` and reads `DATABASE_URL` from the environment, which is the
standard contract all three platforms expect.
