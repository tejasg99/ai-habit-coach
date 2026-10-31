from contextlib import asynccontextmanager

from fastapi import FastAPI

import app.models  # noqa: F401 - for linters to not to raise an error as this import is unused but needed
from app.api.routes import auth, health, logs, notifications, onboarding, plan, progress, users
from app.core.config import settings
from app.core.logging import configure_logging

configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = None
    if settings.SCHEDULER_ENABLED:
        from app.jobs.scheduler import start_scheduler  # imported only when needed

        scheduler = start_scheduler()
    yield
    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(title="AI habit coach API", version="0.1.0", lifespan=lifespan)

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(onboarding.router)
app.include_router(plan.router)
app.include_router(logs.router)
app.include_router(progress.router)
app.include_router(notifications.router)
