import os
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from backend.app.database import Base, engine
from backend.app.services.queue_service import init_db_seeds
from backend.app.api.routes import router as api_router

# Ensure DB tables exist on import
Base.metadata.create_all(bind=engine)
init_db_seeds()

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    print("Application shutdown complete.")

app = FastAPI(
    title="Intelligent Queue Prediction & Management System API",
    description="Student-facing REST API providing real-time queue states, ML-powered forecasts, best visit times, and operational metrics.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static plots directory so frontend can display actual vs predicted, confusion matrix, etc.
PLOTS_DIR = os.path.join(PROJECT_ROOT, "ml", "plots")
if os.path.exists(PLOTS_DIR):
    app.mount("/plots", StaticFiles(directory=PLOTS_DIR), name="plots")

# Include API routes both directly and with /api prefix for maximum client compatibility
app.include_router(api_router, prefix="/api", tags=["Queue System"])
app.include_router(api_router, tags=["Direct Routes"])

# Serve frontend build if dist directory exists
FRONTEND_DIST = os.path.join(PROJECT_ROOT, "frontend", "dist")
if os.path.exists(FRONTEND_DIST):
    app.mount("/assets", StaticFiles(directory=os.path.join(FRONTEND_DIST, "assets")), name="assets")

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    fav_svg = os.path.join(FRONTEND_DIST, "favicon.svg")
    if os.path.exists(fav_svg):
        from fastapi.responses import FileResponse
        return FileResponse(fav_svg, media_type="image/svg+xml")
    from fastapi.responses import Response
    return Response(status_code=204)

@app.get("/")
def root():
    index_html = os.path.join(FRONTEND_DIST, "index.html")
    if os.path.exists(index_html):
        from fastapi.responses import FileResponse
        return FileResponse(index_html)
    return {
        "status": "online",
        "system": "Intelligent Queue Prediction & Management System",
        "version": "1.0.0",
        "docs_url": "/docs",
        "api_endpoints": [
            "/api/facilities",
            "/api/facilities/{id}/status",
            "/api/facilities/{id}/forecast?hours=3",
            "/api/predict",
            "/api/facilities/{id}/best-time",
            "/api/facilities/{id}/hourly-pattern",
            "/api/peaks",
            "/api/recommendations",
            "/api/analytics/trends",
            "/api/model/metrics"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8000, reload=True)
