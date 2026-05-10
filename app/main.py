from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from adapter.factory import get_spring_adapter
from app.api import order, voice
from domain.api_response import ApiErrorResponse, HealthCheckResponse
from core.exceptions import KioskError, SpringApiError
from service.mcp_client import initialize_mcp_client

_API_DESCRIPTION = """
## 개요

NUNCHI KIOSK AI Server는 키오스크 주문 대화를 처리하는 백엔드 API입니다.
프론트엔드 또는 키오스크 클라이언트는 이 문서를 기준으로 세션을 시작하고, 사용자의 발화를 전달하고, AI 응답을 받아 화면이나 음성으로 출력할 수 있습니다.

## 빠른 시작

1. `POST /api/order/start`를 호출해 주문 세션을 생성합니다.
2. 응답으로 받은 `session_id`를 저장합니다.
3. 사용자가 말하거나 입력한 문장을 `POST /api/order/chat`으로 전달합니다.
4. 응답의 `reply`를 화면에 보여주거나 TTS 입력으로 사용합니다.

## 이 문서에서 확인할 수 있는 것

- 각 API의 역할과 호출 순서
- 요청 바디에 어떤 값을 넣어야 하는지
- 응답 필드가 무엇을 의미하는지
- 예시 요청과 예시 응답
- 오류가 발생했을 때 어떤 형식으로 내려오는지

## 응답 규칙

- 정상 응답은 각 API에 지정된 응답 스키마를 따릅니다.
- 비즈니스 규칙 위반이나 내부 처리 오류는 주로 `400`으로 반환됩니다.
- Spring 백엔드 연동 실패나 타임아웃은 주로 `502`로 반환됩니다.
- 요청 형식이 잘못되면 FastAPI 기본 검증 오류 형식으로 `422`가 반환됩니다.

## 참고 경로

- Swagger UI: `/docs`
- ReDoc: `/redoc`
- OpenAPI JSON: `/openapi.json`
"""

_OPENAPI_TAGS = [
    {
        "name": "order",
        "description": (
            "주문 세션 생성과 AI 대화 처리를 담당하는 핵심 API입니다. "
            "대부분의 클라이언트는 이 태그의 API만으로 주문 대화 흐름을 구성할 수 있습니다."
        ),
    },
    {
        "name": "voice",
        "description": "음성 입력 기반 주문 처리용 API입니다. 현재는 명세만 제공되며 실제 기능은 아직 구현되지 않았습니다.",
    },
    {
        "name": "health",
        "description": "배포 상태 확인, 모니터링, 로드밸런서 점검에 사용하는 기본 헬스 체크 API입니다.",
    },
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    await initialize_mcp_client()
    yield
    await get_spring_adapter().close()


app = FastAPI(
    title="NUNCHI KIOSK AI Server",
    version="0.1.0",
    summary="키오스크 주문 세션 생성과 AI 대화 처리를 위한 백엔드 API",
    description=_API_DESCRIPTION,
    openapi_tags=_OPENAPI_TAGS,
    lifespan=lifespan,
)

# CORS 설정
# 브라우저에서 FastAPI를 직접 호출할 때 발생하는 preflight OPTIONS 요청을 허용한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://43.201.20.11:8080",
        "http://43.201.20.11",
        "http://localhost:8080",
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(order.router, prefix="/ai")
app.include_router(voice.router, prefix="/ai")


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


@app.get(
    "/health",
    tags=["health"],
    response_model=HealthCheckResponse,
    summary="서버 상태 확인",
    description=(
            "서버가 요청을 받을 수 있는 상태인지 빠르게 확인하는 API입니다.\n\n"
            "일반적으로 배포 직후 상태 점검, 로드밸런서 헬스 체크, 모니터링 시스템 연동에 사용합니다."
    ),
    response_description="서버가 정상 동작 중이면 `status=ok`를 반환합니다.",
    responses={
        502: {
            "model": ApiErrorResponse,
            "description": "의존 서비스 연동 과정에서 예외가 전파된 경우입니다.",
        }
    },
)
async def health_check() -> HealthCheckResponse:
    return {"status": "ok"}