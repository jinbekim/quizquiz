# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Daily Quiz는 Mattermost 채널에 코드베이스 관련 퀴즈를 자동 출제하는 봇입니다. Claude Code CLI를 사용해 GitHub 레포지토리를 분석하고 퀴즈를 생성합니다.

## Commands

```bash
# 의존성 설치
uv sync --dev

# 데이터베이스 초기화
uv run daily-quiz init

# 수동 퀴즈 출제
uv run daily-quiz quiz --type codebase --difficulty medium

# 수동 채점
uv run daily-quiz grade

# 봇 서버 실행 (스케줄러 포함)
uv run daily-quiz serve

# 린트
uv run ruff check .
uv run ruff format .

# 타입 체크
uv run mypy src/

# 테스트
uv run pytest
uv run pytest tests/test_specific.py -k "test_name"
```

## Architecture

```
src/
├── main.py              # CLI 엔트리포인트 (argparse)
├── config.py            # pydantic-settings 기반 환경변수 관리
├── ai/
│   └── claude_code.py   # Claude Code CLI subprocess 호출
├── analysis/
│   └── github.py        # GitHub API (httpx async client)
├── bot/
│   └── mattermost.py    # Mattermost 봇 (mattermostdriver)
├── db/
│   ├── models.py        # SQLAlchemy 2.0 모델
│   ├── database.py      # DB 연결 관리
│   └── repository.py    # Repository 패턴 DAL
├── quiz/
│   ├── generator.py     # 퀴즈 생성 엔진
│   └── session.py       # 세션 관리 & 채점
└── scheduler/
    └── jobs.py          # APScheduler cron 작업
```

### 핵심 흐름

1. **퀴즈 생성**: `quiz/generator.py` → `analysis/github.py`로 코드 분석 → `ai/claude_code.py`로 문제 생성
2. **퀴즈 출제**: `quiz/session.py` → `bot/mattermost.py`로 채널에 게시
3. **응답 수집**: Mattermost 리액션(이모지) 기반
4. **채점**: `quiz/session.py`에서 리액션 수집 → 정답 비교 → 점수 기록

### 데이터 모델

- `Quiz`: 퀴즈 문제 (type, difficulty, question, options, answer)
- `QuizSession`: 퀴즈 출제 세션 (active → completed)
- `UserResponse`: 사용자 응답 기록
- `User`: 사용자 점수/스트릭 관리

## Environment Variables

`.env.example` 참조. 필수:
- `MATTERMOST_URL`, `MATTERMOST_TOKEN`, `MATTERMOST_CHANNEL_ID`
- `GITHUB_TOKEN`, `GITHUB_REPO`

## Quiz Types

- `codebase`: 코드베이스 구조 관련
- `library`: 사용 중인 라이브러리 관련
- `recent_change`: 최근 커밋 기반
