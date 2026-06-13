# NUNCHI-AI
![CI/CD](https://github.com/CapstoneDgu/NUNCHI-AI/actions/workflows/deploy.yml/badge.svg?branch=main)

<br/>

# 1. Project Overview (프로젝트 개요)
- 프로젝트 이름: NUNCHI-AI
- 프로젝트 설명: NUNCHI 키오스크의 AI 오케스트레이션 서버. 음성 파이프라인(STT → LLM → TTS), LangGraph 기반 주문 에이전트, MCP Tool 실행을 담당합니다. React 프론트엔드와 Spring 백엔드 사이에서 AI 흐름을 제어하며, Smithery.ai를 통해 외부 Claude Desktop과도 연동 가능합니다.

<br/>
<br/>

# 2. Team Members (팀원 및 팀 소개)
| 조효동 | 이현노 | 임현우 | 임호영 |
|:------:|:------:|:------:|:------:|
| <img src="https://github.com/hyodongg.png" alt="효동" width="150"> | <img src="https://github.com/leehyunro123.png" alt="현노" width="150"> | <img src="https://github.com/identicons/placeholder.png" alt="임현우" width="150"> | <img src="https://github.com/identicons/placeholder.png" alt="임호영" width="150"> |
| BE / AI | AI / 음성플로우 |
| [GitHub](https://github.com/hyodongg) | [GitHub](https://github.com/leehyunro123) 


<br/>
<br/>

# 3. Key Features (주요 기능)

## 3.1 시스템 구조

```
React (키오스크 UI)
    ↕  REST / WebSocket
[NUNCHI-AI — FastAPI]
    ├── OpenAI (Whisper STT / GPT / TTS)
    └── MCP Tool Router
          ├── DB Tool       → Spring 메뉴/주문/결제 API 호출
          ├── UI Tool       → React 화면 제어 이벤트 전송
          └── Payment Tool  → 결제 플로우 오케스트레이션
    ↕  HTTP REST
Spring Boot (NUNCHI)
    ↕
PostgreSQL + Redis
```

<br/>

## 3.2 음성 파이프라인

마이크 입력부터 TTS 응답 출력까지 전 과정을 처리합니다.

```
1. 음성 수신    키오스크 마이크에서 오디오 입력 수신
2. STT 변환     OpenAI Whisper로 음성 → 텍스트 변환
3. 의도 분류    LLM이 주문 / 추천 / 결제 / 일반 질문 의도 분류
4. 개체 추출    메뉴명, 수량, 옵션, 조건(알레르기 등) 추출
5. Tool 실행    MCP Tool 선택 및 체이닝 실행
6. TTS 응답     처리 결과를 음성으로 합성해 사용자에게 전달
```

<br/>

## 3.3 LangGraph 주문 에이전트

LangGraph로 구성된 상태 기반 에이전트입니다. 노드 단위로 의도 분류 → Tool 실행 → 응답 생성 흐름을 제어하며, 주문 모드에 따라 행동 지침 블록을 분리하여 동작합니다.

**에이전트 그래프 흐름**

```
입력 (음성 텍스트 / 채팅)
    │
    ▼
[intent_classifier]  ←  이전 대화 문맥 참조
    │
    ├─ 주문 / 담기   →  [order_agent]   →  add_to_cart Tool
    ├─ 추천 요청     →  [recommend_agent] →  get_menus Tool
    ├─ 결제          →  [payment_agent]  →  confirm_order Tool
    └─ 일반 질문     →  [chat_agent]     →  TTS 응답 생성
    │
    ▼
[response_builder]  →  TTS 합성 + UI Control Tool 이벤트 전송
```

**모드별 행동 지침 분리**

| 모드 | 동작 방식 |
|------|-----------|
| 일반 모드 | 터치 주문 보조, 음성 명령 기반 화면 원격 조작 |
| 아바타 모드 | 아바타 "눈치"로서 대화 주도, 추천 → 담기 → 결제 전 플로우 제어 |

**주요 설계 포인트**
- LLM 팩토리 도입으로 **OpenAI / Gemini 공급자 전환** 지원
- 장바구니 담기 시 **환각 방지 가드** — Tool 결과 검증 후 응답 생성
- 락 충돌(409) 발생 시 **자동 재시도 로직** 내장
- 직전 AI 메시지 문맥을 의도 분류에 반영하여 연속 대화 품질 향상

<br/>

## 3.4 MCP Tool 구성

| Tool | 설명 | 주요 기능 |
|------|------|-----------|
| **DB Tool** | Spring 백엔드 데이터 조회 | 메뉴 목록, 메뉴 상세, 인기 메뉴, 카테고리별 조회 |
| **UI Control Tool** | React 키오스크 화면 제어 | 화면 이동, 메뉴 강조, 장바구니 반영, 확인 모달 표시 |
| **Payment Tool** | 결제 플로우 오케스트레이션 | 주문 확정, 카드 결제, 결제 실패 대응 |

모든 Tool은 MCP 프로토콜 기반으로 동작하며, Spring API 실데이터를 기준으로 응답합니다. 메뉴·가격은 절대 하드코딩하지 않습니다.

<br/>

## 3.5 퀵바 Prefetch

아바타 모드에서 다음 발화를 예측하여 응답을 미리 prefetch합니다. 사용자가 퀵바 버튼을 누르는 순간 즉시 응답이 가능합니다.

> 예: `장바구니 확인해줘` · `조건 바꿔서 추천해줘` · `다른 메뉴도 추천해줘`

<br/>

## 3.6 Smithery MCP 연동

[Smithery.ai](https://smithery.ai)에 NUNCHI MCP 서버를 등록하여, 개인 Claude Desktop에서 간단한 명령어 한 줄로 연결할 수 있습니다.

<img width="1024" height="441" alt="image" src="https://github.com/user-attachments/assets/da7fd90d-e7b1-46fa-b6a7-3b2926420ba4" />

- 외국어 주문, 개인 맞춤 추천 등 개인 AI로 확장 활용 가능
- 추후 동국 AI CHAT과 연결하여 교내 AI와 함께 사용 가능

<!-- Smithery 스크린샷 삽입 위치 -->
<!-- <img src="smithery.png" alt="Smithery MCP 연동" width="600"/> -->

<br/>
<br/>

# 4. Tasks & Responsibilities (작업 및 역할 분담)

|  |  |  |
|--------|--------|--------|
| 조효동 | <img src="https://github.com/hyodongg.png" alt="효동" width="100"> | <ul><li>FastAPI AI 서버 설계 및 개발</li><li>LangGraph 주문 에이전트 구현 (모드별 행동 지침 분리)</li><li>MCP Tool 설계 및 구현</li><li>Smithery MCP 서버 배포 및 연동</li></ul> |
| 이현노 | <img src="https://github.com/leehyunro123.png" alt="현노" width="100"> | <ul><li>음성 원격조작 응답 액션 추가 및 의도 분기 구현</li><li>일반 모드 전용 프롬프트 설계 </li><li>의도 분류 튜닝 </li><li>결제 노드 화면 안내 전환 및 추천, 응답 파싱 보완</li></ul> |

<br/>
<br/>

# 5. Technology Stack (기술 스택)

|  |  |
|--------|--------|
| Python | ![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=flat-square&logo=python&logoColor=white) |
| FastAPI | ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white) |
| LangGraph | ![LangGraph](https://img.shields.io/badge/LangGraph-1C3C3C?style=flat-square&logo=langchain&logoColor=white) |
| OpenAI | ![OpenAI](https://img.shields.io/badge/OpenAI-412991?style=flat-square&logo=openai&logoColor=white) |
| Docker | ![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white) |
| GitHub Actions | ![GitHub Actions](https://img.shields.io/badge/GitHub_Actions-2088FF?style=flat-square&logo=githubactions&logoColor=white) |

<br/>
<br/>

# 6. Project Structure (프로젝트 구조)

```plaintext
NUNCHI-AI/
├── app/                # FastAPI 진입점, 라우터 (/api/**)
│   ├── main.py
│   └── api/
├── service/            # 음성 파이프라인, 에이전트, 추천 / 퀵바 로직
├── adapter/            # OpenAI / Spring 백엔드 연동
├── kiosk_mcp/          # MCP 서버 및 Tool 구현
│   └── tools/          # DB / UI / Payment Tool
├── domain/             # Pydantic 모델
├── core/               # 설정, 예외, 공통 유틸
├── .claude/            # 개발 컨텍스트 문서 (PROJECT.md, CONVENTION.md)
├── requirements.txt
└── Dockerfile
```

<br/>
<br/>

# 7. Development Workflow (개발 워크플로우)

## 브랜치 전략 (Branch Strategy)

Git Flow를 기반으로 하며, 다음 브랜치를 사용합니다.

- `main` Branch
  - 배포 가능한 상태의 코드를 유지합니다.
  - 모든 배포는 이 브랜치에서 이루어집니다.

- `dev` Branch
  - 개발 통합 브랜치입니다.
  - 기능 개발 완료 후 dev로 머지합니다.

- `{name}/{feature}` Branch
  - 팀원 각자의 기능 개발 브랜치입니다.
  - 예: `feat/#65/smithery`, `fix/#68/qa-3`

<br/>
<br/>

# 8. Coding Convention

## 명명 규칙 (Python)

```python
# 클래스: 파스칼 케이스
class OrderAgentService: ...

# 함수 & 변수: 스네이크 케이스
def get_menu_list(): ...
current_session_id = ""

# 상수: 어퍼 스네이크 케이스
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
```

<br/>

## 설계 원칙

```
- 비즈니스 로직은 Router에 두지 않고 Service로 분리
- 외부 연동(OpenAI, Spring)은 Adapter 계층으로 분리
- MCP Tool 구현은 kiosk_mcp/ 디렉터리에 집중
- 메뉴·가격은 절대 하드코딩 금지, Spring API 실데이터 기준
- AI 응답 시간 3초 이내 목표
```

<br/>
<br/>

# 9. 커밋 컨벤션

## 기본 구조

```
[Type] 설명
```

<br/>

## Type 종류

```
[Feat]    : 새로운 기능 추가
[Fix]     : 버그 수정
[Refactor]: 코드 리팩토링
[Chore]   : 빌드, 설정, 패키지 변경
[Docs]    : 문서 작성 / 수정
```

<br/>

## 커밋 예시

```
== ex1
[Feat] LangGraph 주문 에이전트 모드별 행동 지침 분리

일반 모드 / 아바타 모드 프롬프트 블록 분리 구조 추가

== ex2
[Fix] 장바구니 담기 락 충돌(409) 시 재시도 로직 추가

== ex3
[Chore] Smithery MCP 서버 배포 설정 추가
```
