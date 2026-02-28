from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routes import generate_stream, sessions, assets

from fastapi.staticfiles import StaticFiles
import os

app = FastAPI(title="ExplainFlow API")

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

@app.get("/")
def read_root():
    return {"message": "ExplainFlow API is running"}
