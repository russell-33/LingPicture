import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.config import settings
from src.core.internal_auth import validate_internal_request
from src.router import rag, agent, picture

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="YunPicture AI Service", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def verify_internal_token(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)
    # 本地回环请求放行（Agent 工具调用内部 RAG/Agent API）
    if request.client and request.client.host in ("127.0.0.1", "::1"):
        return await call_next(request)
    if not validate_internal_request(request):
        return JSONResponse(status_code=401, content={"detail": "Invalid internal token"})
    return await call_next(request)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"{request.method} {request.url.path}")
    response = await call_next(request)
    return response


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(rag.router, prefix="/api/v1")
app.include_router(agent.router, prefix="/api/v1")
app.include_router(picture.router, prefix="/api/v1")
