from fastapi import FastAPI

from api.routers import chat, healthz

llm_backend = FastAPI(title="LLM Backend - DemoObject")

llm_backend.include_router(chat.router)
llm_backend.include_router(healthz.router)
