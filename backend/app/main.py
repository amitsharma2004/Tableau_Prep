from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.connections import router as connections_router
from app.api.flows import router as flows_router
from app.api.runs import router as runs_router
from app.services.scheduler_worker import start_scheduler, stop_scheduler
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure app metadata schema (flows, runs, connections, audit) is ready
    Base.metadata.create_all(bind=engine)
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title="Tableau AI Prep",
    description="NL -> Claude plan -> human approval -> Hyper extract -> Tableau publish",
    lifespan=lifespan,
)

# MVP dev setup: the Next.js frontend runs on a different origin (port).
# Tighten this to the deployed frontend's real origin before production.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(connections_router)
app.include_router(flows_router)
app.include_router(runs_router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
