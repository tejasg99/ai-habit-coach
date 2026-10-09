from fastapi import FastAPI
from sqlalchemy import text
from app.db.session import DbSession

app = FastAPI(title="AI habit coach API", version="0.1.0")

@app.get("/health")
def health():
    return { "status": "OK"}

@app.get("/health/db")
def health_db(db: DbSession):
    db.execute(text("SELECT 1"))
    return { "database": "OK" }
