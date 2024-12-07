"""
Brain Wave Collective
https://brainwavecollective.ai
  Revolutionizing Video Creation with TwelveLabs Jockey and NVIDIA AI Workbench. 
  Saddle Stack (AKA Jockbench) is our submission to the Dell x NVIDIA HackAI Challenge
File: main.py
Created: 2024
Authors: Thienthanh Trinh & Daniel Ritchie
Copyright (c) 2024 Brain Wave Collective
"""

# app/main.py

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import weave
import os
from pathlib import Path
from app.core.config import get_settings
from app.core.logger import setup_logging
from app.services.jockey_service import JockeyService
from app.api.endpoints import text_processor, connections, jockey, video

from starlette.websockets import WebSocketDisconnect

logger = setup_logging()
settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    try:
        # Initialize Weave if API key exists
        if settings.weave_api_key:
            try:
                import wandb
                wandb.login(key=settings.weave_api_key)
                weave.init('text-to-video-app')
                logger.info("Weave logging initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Weave logging: {e}")

        # Initialize services
        app.state.settings = settings
        app.state.jockey_service = JockeyService()
        await app.state.jockey_service.initialize()  # Initialize Jockey service

        logger.info("Application startup complete")
        yield

    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
    finally:
        # Cleanup services
        try:
            await app.state.jockey_service.close()
            logger.info("Application shutdown complete")
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

# Determine if we're in production
is_production = os.path.basename(os.getcwd()) == "dist"

app = FastAPI(
    title="Lights, Camera, Jockey!",
    description="Brain Wave Collective presents generative videos from your own content using Jockey by TwelveLabs",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration - must be before any routes
origins = [
    "http://localhost:5173",
    "ws://localhost:5173",
    "http://localhost:9000",
    "ws://localhost:9000",
    "http://127.0.0.1:5173",
    "ws://127.0.0.1:5173",
    "http://127.0.0.1:9000",
    "ws://127.0.0.1:9000",
]

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]
)

# Configure static files
is_production = os.path.basename(os.getcwd()) == "dist"
if is_production:
    app.mount("/", StaticFiles(directory=".", html=True), name="static")
else:
    static_dir = Path("app/static")
    if not static_dir.exists():
        logger.error(f"Static directory not found: {static_dir}")
        raise RuntimeError("Static directory not found")
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# API routes
app.include_router(text_processor.router, prefix="/api")
app.include_router(connections.router)
app.include_router(jockey.router, prefix="/api/jockey")
app.include_router(video.router, prefix="/api/jockey")

# /api/jockey/video/{index_id}/{filename}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    try:
        # Initialize services
        app.state.settings = settings
        app.state.jockey_service = JockeyService()
        logger.info("Application startup complete")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise
        
@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown"""
    try:
        await app.state.jockey_service.close()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

@app.get("/{full_path:path}")
async def serve_spa(full_path: str):
    """Serve SPA for non-API routes"""
    try:
        if not full_path.startswith("api/"):
            file_path = "index.html" if is_production else "app/static/index.html"
            if not os.path.exists(file_path):
                logger.error(f"SPA file not found: {file_path}")
                raise HTTPException(status_code=404, detail="File not found")
            return FileResponse(file_path)
    except Exception as e:
        logger.error(f"Error serving SPA: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        services_status = {
            "jockey_service": "healthy" if app.state.jockey_service else "unavailable",
        }
        
        return {
            "status": "healthy",
            "environment": "production" if is_production else "development",
            "services": services_status
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail="Health check failed")