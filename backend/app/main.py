from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.api import auth, chat, tests, runs, collections, dashboard, schedules, healing, settings, admin, projects, test_execution
from app.api import api_collections, api_requests, api_environments, api_runs, api_generation
from app.db.postgres import engine, Base
from app.services.scheduler import scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    await scheduler.start()

    yield

    # Shutdown: stop scheduler
    await scheduler.stop()
    await engine.dispose()


app = FastAPI(
    title="Autoflow API",
    description="AI-powered browser test automation",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(tests.router, prefix="/api/tests", tags=["tests"])
app.include_router(runs.router, prefix="/api/runs", tags=["runs"])
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])
app.include_router(schedules.router, prefix="/api/schedules", tags=["schedules"])
app.include_router(healing.router, prefix="/api/healing", tags=["healing"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])
app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
app.include_router(test_execution.router, prefix="/api/test-execution", tags=["test-execution"])

# API Testing routes
app.include_router(api_collections.router, prefix="/api/api-collections", tags=["api-collections"])
app.include_router(api_requests.router, prefix="/api/api-requests", tags=["api-requests"])
app.include_router(api_environments.router, prefix="/api/api-environments", tags=["api-environments"])
app.include_router(api_runs.router, prefix="/api/api-runs", tags=["api-runs"])
app.include_router(api_generation.router, prefix="/api/api-generation", tags=["api-generation"])


@app.get("/health")
async def health():
    return {"status": "healthy"}
