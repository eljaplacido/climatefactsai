# Local Platform Runbook (English)

This is the current “day-to-day” local run path for CliLens (API + UI + background worker + tracing).

## Option A: Run everything with Docker (recommended)

```bash
docker-compose -f docker-compose.simple.yml up -d
docker-compose -f docker-compose.simple.yml ps
```

Open:
- Frontend: `http://localhost:5300`
- API docs: `http://localhost:5400/docs`
- Jaeger (traces): `http://localhost:5686`

## Option B: Develop locally (API/UI on host, DB/Redis in Docker)

Start Postgres + Redis (+ Jaeger) from the repo root:

```bash
docker-compose -f docker-compose.simple.yml up -d postgres redis jaeger
```

Create a Python 3.11 venv and install deps:

```powershell
py -3.11 -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt -r api\requirements.txt
```

Run the API locally (port 5400 to match the UI defaults):

```powershell
python -m uvicorn api.main:app --reload --host 0.0.0.0 --port 5400
```

Run the Next.js frontend locally:

```powershell
cd src\frontend
npm install
$env:NEXT_PUBLIC_API_URL="http://localhost:5400"
npm run dev
```

## Seeding demo content

If you want articles immediately in the UI, run one of the seeders from the repo root (with Postgres up):

```powershell
python populate_demo_articles.py
```

## Shutting down

```bash
docker-compose -f docker-compose.simple.yml down
```

