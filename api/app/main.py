from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.config import limiter
from app.routes import assets, generate_stream, sessions, workflow

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="ExplainFlow API")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Ensure static directory exists
os.makedirs("app/static/assets", exist_ok=True)

# Mount the static directory to /static
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(generate_stream.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(assets.router, prefix="/api")
app.include_router(workflow.router, prefix="/api")

@app.get("/")
def read_root():
    return {"message": "ExplainFlow API is running"}
