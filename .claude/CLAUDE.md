# CLAUDE.md — NUNCHI KIOSK FastAPI AI 서버

## 필수 숙지 문서
이 프로젝트를 작업하기 전에 반드시 아래 두 문서를 읽을 것.

- `.claude/PROJECT.md` — 전체 아키텍처, MCP 도구 정의, FastAPI 서버 역할, Spring 통신 구조, 기능 요구사항 전체 목록
- `.claude/CONVENTION.md` — Pydantic / Service / Router / 예외처리 / 네이밍 코딩 컨벤션

## 계획 규칙
사용자가 **"계획을 써서 보여줘"** 또는 **"계획 보여줘"** 라고 요청할 때만:
1. `PLAN.md` 파일의 기존 내용을 모두 지우고
2. 구현 계획을 작성한 뒤
3. 사용자에게 파일을 확인하라고 안내한다.

## 보고 규칙
사용자가 **"문서로 보고해"** 라고 요청할 때만:
1. `RESULT.md` 파일의 기존 내용을 모두 지우고
2. 새로운 내용으로 작성한 뒤
3. 사용자에게 파일을 확인하라고 안내한다.

사용자가 **"작업한거 보고해"** 또는 **"보고해"** 라고 요청할 때만:
1. `RESULT.md` 파일의 기존 내용을 모두 지우고
2. 최근 작업 내용만 다시 작성한 뒤
3. 사용자에게 파일을 확인하라고 안내한다.

"설명해", "알려줘" 등 일반 질문은 파일 작성 없이 채팅으로 답변한다.

---

## 프로젝트 컨텍스트

- **서버 역할**: NUNCHI KIOSK의 AI 서버 (음성 처리 / 대화 / 추천 / MCP Tool 실행)
- **프로젝트 성격**: React 키오스크와 Spring 백엔드 사이에서 동작하는 FastAPI 기반 AI 오케스트레이션 서버
- **연동 대상**:
  - **React 프론트엔드** (음성 입력, UI 제어, WebSocket 연동)
  - **Spring 백엔드** (메뉴 / 주문 / 결제 / 세션 / 통계 API 제공)
  - **OpenAI API** (STT / LLM / TTS)

---

## 기술 스택

- Python 3.11+
- FastAPI
- Pydantic
- HTTPX
- WebSocket
- OpenAI API (Whisper / GPT / TTS)
- MCP Server

---

## FastAPI 서버 역할

FastAPI는 NUNCHI의 AI 서버이자 MCP 실행 서버다.

### 핵심 책임
- 음성 입력을 받아 STT로 텍스트 변환
- LLM으로 의도 분석, 응답 생성, 추천 로직 수행
- MCP Tool을 실행해 메뉴 조회, 주문, 결제 흐름 제어
- React 프론트에 WebSocket 또는 API로 UI 제어 이벤트 전달
- Spring 백엔드 API를 호출해 실제 데이터 조회 및 주문/결제 처리

### 처리 흐름
- React → FastAPI: 음성, 터치 이벤트, 눈치 감지 이벤트 전달
- FastAPI → OpenAI: STT / LLM / TTS 호출
- FastAPI → Spring: 메뉴 / 주문 / 결제 / 세션 / 통계 API 호출
- FastAPI → React: 추천, 대화 응답, 화면 제어 이벤트 전달

---

## MCP 설계 원칙

FastAPI는 MCP Tool을 직접 제공하고 실행한다.

### MCP DB Tool 지원
- 메뉴 조회, 판매 데이터, 추천 근거 조회 기능 제공
- Spring 백엔드의 데이터를 HTTP로 조회해 MCP Tool 결과로 반환
- 예: `get_menus`, `get_menu_detail`, `get_top_menus`, `get_today_recommendations`

### MCP UI Tool 지원
- React 키오스크 화면 제어 이벤트를 전송
- 예: 화면 이동, 메뉴 강조, 확인 모달 표시, 장바구니 반영

### MCP Payment Tool 지원
- 결제 플로우를 오케스트레이션
- Spring 결제 API 또는 센서/외부 장비 연동 로직과 연결
- 예: `confirm_order`, `process_card_payment`, `start_vein_scan`

### 통신 방식
- FastAPI ↔ React: REST + WebSocket
- FastAPI ↔ Spring: HTTP REST
- FastAPI ↔ OpenAI: API 호출

---

## 모듈 구조 원칙

```text
app            FastAPI 진입점, 라우터
service        음성 파이프라인, 에이전트, 추천 로직
adapter        OpenAI / Spring / 센서 연동
mcp            MCP 서버 및 Tool 구현
domain         Pydantic 모델
core           설정, 예외, 공통 유틸
```

예시 구조:
```text
capstone_ai
├── app
│   ├── main.py
│   └── api
├── service
├── adapter
├── mcp
│   └── tools
├── domain
├── core
└── .claude
```

---

## 코딩 규칙

### 공통
- 언어: 한국어로 소통, 코드 주석도 한국어
- 비즈니스 로직은 Router에 두지 않고 Service로 분리
- 외부 연동은 Adapter 계층으로 분리
- 데이터 구조는 Pydantic 모델로 명확히 정의
- 예외는 공통 예외 클래스로 변환해서 처리

### API 설계
- 일반 REST API는 `/api/**`
- MCP 서버 또는 MCP 관련 공개 경로는 별도 모듈로 분리
- 응답 구조는 일관되게 유지하고, 에러 응답도 공통 포맷을 따른다
- 응답 코드 구분을 명확히 한다 (200, 201, 400, 401, 404, 500)

### 보안
- OpenAI API Key, 내부 API Key, 센서 관련 민감 정보는 코드에 하드코딩하지 않는다
- Spring 호출용 내부 인증 헤더는 설정 파일로 관리한다
- 결제/생체인증 정보는 로그에 남기지 않는다

---

## FastAPI 서버 개발 시 주의사항

1. **MCP 우선 설계**: 어떤 기능을 만들든 "이 기능을 MCP Tool로 호출할 수 있는가?"를 먼저 고려한다.
2. **실제 계약 우선**: Spring 연동 코드는 추측으로 만들지 말고, 확정된 API 계약 기준으로 작성한다.
3. **병렬 입력 고려**: 터치와 음성 입력이 동시에 들어올 수 있으므로 상태 충돌을 조심한다.
4. **세션 관리**: 대화 세션과 주문 세션의 상태를 분리해 관리하고, 완료 또는 타임아웃 시 정리한다.
5. **눈치 기능 지원**: 침묵, 반복 탐색, 헤징 발화 같은 신호를 추천 로직에 반영할 수 있게 설계한다.
6. **응답 시간 3초 이내 목표**: 불필요한 Tool 호출과 중복 API 호출을 줄이고, 타임아웃을 짧게 관리한다.
7. **환각 방지**: 메뉴/가격/주문 상태는 반드시 Spring 또는 확정된 데이터 소스를 기준으로 답변한다.
