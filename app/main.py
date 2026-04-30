from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapter.factory import get_spring_adapter
from app.api import order, voice
from core.exceptions import KioskError, SpringApiError


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 서버 시작 시 초기화할 것이 있으면 여기에 추가
    yield
    # 공유 HTTP 클라이언트 정리
    await get_spring_adapter().close()


app = FastAPI(
    title="NUNCHI KIOSK AI Server",
    version="0.1.0",
    lifespan=lifespan,
)

# 라우터 등록
app.include_router(order.router)
app.include_router(voice.router)


# 공통 예외 핸들러
@app.exception_handler(SpringApiError)
async def spring_api_error_handler(request, exc: SpringApiError):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=502,
        content={"code": exc.code, "message": exc.message},
    )


@app.exception_handler(KioskError)
async def kiosk_error_handler(request, exc: KioskError):
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=400,
        content={"code": exc.code, "message": exc.message},
    )


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    return {"status": "ok"}
