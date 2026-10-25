from fastapi import FastAPI

import app.models  # noqa: F401 - for linters to not to raise an error as this import is unused but needed
from app.api.routes import auth, health, onboarding, plan, users

app = FastAPI(title="AI habit coach API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(onboarding.router)
app.include_router(plan.router)
