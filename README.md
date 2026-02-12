# Plant Tracker — Marchantia Growth Monitor

Automated image-analysis pipeline and web app for monitoring **Marchantia polymorpha** plant growth and health.

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Run the Analysis Pipeline (CLI)

Place your plant images in `test-plant/` (filenames like `Plant_00.jpg`, `Plant_01.jpg`, …).

```bash
cd backend
python scripts/run_phase1.py --image-dir ../test-plant
```

This will process each image, detect QR codes, segment the plant, compute metrics, and store results in `data/plant_tracker.db`.

### Start the API Server

```bash
cd backend
uvicorn app.main:app --reload
```

API docs at [http://localhost:8000/docs](http://localhost:8000/docs).

### Start the Frontend

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173).

## Project Structure

```
Plant_Tracker/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application
│   │   ├── config.py            # Settings & thresholds
│   │   ├── database.py          # SQLAlchemy engine & session
│   │   ├── models.py            # ORM models
│   │   ├── schemas.py           # Pydantic schemas
│   │   ├── crud.py              # Database helpers
│   │   ├── routers/             # API route modules
│   │   └── analysis/            # CV pipeline modules
│   ├── scripts/
│   │   └── run_phase1.py        # CLI batch processor
│   ├── tests/                   # pytest suite
│   └── requirements.txt
├── frontend/                    # React + Vite UI
├── test-plant/                  # Input images
├── data/                        # SQLite database (created at runtime)
└── README.md
```

## Database Schema

| Table          | Key Columns                                                        |
| -------------- | ------------------------------------------------------------------ |
| `plants`       | id, qr_code (unique), name, created_at                            |
| `images`       | id, plant_id (FK), filename, filepath, captured_at                 |
| `measurements` | id, image_id (FK), plant_id (FK), area_px, area_mm2, health_score |

## Configuration

All thresholds are configurable via environment variables (prefixed `PT_`) or by editing `backend/app/config.py`.

| Variable                      | Default | Description                       |
| ----------------------------- | ------- | --------------------------------- |
| `PT_OVERGROWTH_THRESHOLD_MM2` | 400     | Area threshold for overgrowth     |
| `PT_RULER_TICK_DISTANCE_MM`   | 10      | Physical mm between ruler ticks   |
| `PT_HEALTH_WEIGHT_GREENNESS`  | 0.4     | Weight for greenness in score     |
| `PT_HEALTH_WEIGHT_SATURATION` | 0.3     | Weight for saturation in score    |
| `PT_HEALTH_WEIGHT_GROWTH`     | 0.3     | Weight for growth trend in score  |

## Testing

```bash
cd backend
pytest tests/ -v
```
