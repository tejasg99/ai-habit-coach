from fastapi import FastAPI, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from app.db.session import DbSession

app = FastAPI(title="AI habit coach API", version="0.1.0")

@app.get("/health")
def health():
    return { "status": "OK"}

@app.get("/health/db")
def health_db(db: DbSession):
    try:
        db.execute(text("SELECT 1"))
        return { "database": "OK" }
    except SQLAlchemyError:
        raise HTTPException(status_code=503, detail="Database unavailable")