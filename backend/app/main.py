import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.core.config import settings
from app.api.routes import router as api_router
from app.db.session import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("costpilot")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Authoritative Dataset-Driven Machine Learning Software Cost Estimation Platform",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes with prefix /api/v1 and also unversioned aliases for compatibility
app.include_router(api_router, prefix=settings.API_V1_STR)
app.include_router(api_router, prefix="")

# Frontend static files mounting
FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    async def serve_index():
        index_file = FRONTEND_DIR / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        return {"message": "CostPilot AI Backend Running. Frontend index.html not found."}


@app.on_event("startup")
async def startup_event():
    init_db()
    logger.info(f"{settings.PROJECT_NAME} v{settings.VERSION} started successfully.")
