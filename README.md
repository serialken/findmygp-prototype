# LogiConnect (FindMyGP)

Marketplace connecting clients with independent carriers and transport companies —
browse, book, track, message, and pay for a delivery. Local deliveries in France
today, with a first international corridor between **France and Sénégal** (air
freight and maritime groupage) already modeled.

The frontend is a real client of the backend API: authentication, carrier search,
booking with server-computed pricing, live tracking over WebSockets, real-time
messaging, and Stripe payments all talk to a running FastAPI + PostgreSQL backend
— nothing here is mock data.

## Project layout

```
.
├── index.html      Frontend — single-file React app (CDN React + Babel, no build step)
└── backend/        FastAPI + PostgreSQL API (auth, bookings, tracking, messaging, payments)
```

## Quick start

You need both pieces running at the same time: the backend API, and the frontend
served over HTTP (not opened as a `file://` path — the browser's CORS policy
blocks that against the API).

### 1. Backend

Requires Docker (for Postgres) and Python 3.9+. Full details, environment
variables, and deployment notes are in [`backend/README.md`](backend/README.md).

```bash
cd backend
cp .env.example .env        # safe to leave secrets blank for now — see below
docker compose up -d db     # starts Postgres only
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m app.seed          # loads 17 sample carriers (France + Sénégal) into the DB
uvicorn app.main:app --reload
```

The API is now on **http://localhost:8000** (interactive docs at `/docs`).

### 2. Frontend

From the repo root, in a second terminal:

```bash
python3 -m http.server 5500
```

Open **http://localhost:5500**. The page talks to the API at `http://localhost:8000`
by default — if you run the backend on a different port, update the `API_BASE`
constant near the top of the `<script>` block in `index.html` to match.

### 3. Try it

1. Click **Connexion → Créer un compte** and register a client account.
2. **Rechercher** a carrier (try pickup city `Dakar`, or leave it blank to see
   all 17), open a profile, and click **Demander une livraison**.
3. Walk through the booking steps — the price shown on the recap screen is a
   live quote from the API using that carrier's real rates, not a placeholder.
4. On the confirmation screen, **Voir le suivi & payer** opens the tracking
   page: click **Vérifier les mises à jour** to pull the (simulated, by
   default) carrier network status, and watch it update live — that's a real
   WebSocket push, not a page refresh.
5. **Payer** opens the Stripe payment panel. Without real Stripe keys
   configured it fails with a clear inline message instead of crashing — see
   below for enabling real payments.
6. **Messages** shows the conversation auto-created with that booking; sending
   a message persists it server-side and delivers it live over WebSocket.

## What's real vs. simulated right now

| Capability | Status |
|---|---|
| Auth, persistence, bookings, pricing | Real — PostgreSQL, JWT, server-computed prices |
| Tracking & messaging delivery | Real — WebSocket push, not polling |
| Distance/geocoding | Real Mapbox calls **if** `MAPBOX_ACCESS_TOKEN` is set in `backend/.env`; otherwise falls back to a fixed estimate |
| Payments | Real Stripe test-mode flow **if** `STRIPE_SECRET_KEY`/`STRIPE_PUBLISHABLE_KEY` are set; otherwise the payment panel shows a clear "not configured" message |
| Chronopost / Colissimo / DHL tracking | Simulated by default (accelerated mock progression); switches to real API calls automatically once the matching key is set — see the "Carrier API integrations" section in [`backend/README.md`](backend/README.md) |
| Customer reviews on carrier profiles | Cosmetic only — ratings/review counts are real, the written review text is generated client-side (no reviews table in the backend yet) |

Everything above is configured via `backend/.env` (copy it from `.env.example`,
never commit the real file — it's gitignored). Nothing hard-fails at startup
because a third-party key is missing.

## Known gaps

- No carrier-facing UI — a carrier account can be linked to a profile via the
  API (`POST /carriers/{id}/link-account`) but there's no screen for a
  transporteur to log in, reply to messages, or update their own tracking
  status. Everything in `index.html` is the client-facing experience.
- No Alembic migrations yet (schema is created on startup via `create_all`) —
  fine for this stage, would need addressing before evolving the schema
  against real data.

See [`backend/README.md`](backend/README.md) for the full backend
architecture, environment variables, and deployment instructions
(Railway/Render/Fly.io-ready via the included `Dockerfile` and
`docker-compose.yml`).
