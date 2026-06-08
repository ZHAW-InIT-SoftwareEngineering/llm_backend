from fastapi import FastAPI

from api.routers import chat, healthz

app = FastAPI(title="LLM - DemoObject")
app.include_router(chat.router)
app.include_router(healthz.router)
