from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.v1 import api_router
from app.core.config import settings

_OPENAPI_TAGS = [
    {"name": "auth",           "description": "Login, logout, token refresh"},
    {"name": "users",          "description": "User profile and management"},
    {"name": "sanatoriums",    "description": "Sanatorium listing and management"},
    {"name": "rooms",          "description": "Room categories, availability, search"},
    {"name": "bookings",       "description": "Booking creation, listing, cancellation"},
    {"name": "exchange-rates", "description": "USD/UZS exchange rate management"},
]


@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield


app = FastAPI(
    title=settings.PROJECT_NAME,
    debug=settings.DEBUG,
    lifespan=lifespan,
    openapi_tags=_OPENAPI_TAGS,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

uploads_dir = Path(settings.UPLOAD_DIR)
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount(
    settings.UPLOAD_URL_PREFIX,
    StaticFiles(directory=uploads_dir),
    name="uploads",
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"name": settings.PROJECT_NAME, "docs": "/docs"}
