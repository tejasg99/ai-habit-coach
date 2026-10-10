from fastapi import FastAPI

import app.models
from app.api.routes import auth, health

app = FastAPI(title="AI habit coach API", version="0.1.0")

app.include_router(health.router)
app.include_router(auth.router)