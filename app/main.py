"""FastAPI application entry point for the BIM cloud service."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.plugins.registry import discover_plugins

# ── Logging ───────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)

# ── Plugin auto-discovery (populates the registry) ───────────────
discover_plugins()

# ── FastAPI app ──────────────────────────────────────────────────
app = FastAPI(
    title="OpenPlans BIM Service",
    description=(
        "Automated Building Information Modeling (BIM) generation "
        "using IfcOpenShell. Accepts element payloads and returns "
        "compiled IFC files."
    ),
    version="1.0.0",
)

# ── CORS (allow all origins for dev; tighten in production) ──────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
