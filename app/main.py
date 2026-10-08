from fastapi import FastAPI

app = FastAPI(title="AI habit coach API", version="0.1.0")

@app.get("/health")
def health():
    return { "status": "OK"}