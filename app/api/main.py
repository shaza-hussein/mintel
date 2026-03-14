import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routers.pricing import router as pricing_router

app = FastAPI(
    title="MinTel",
    version="1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(pricing_router)