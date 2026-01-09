# Daily Quiz

Mattermost 채널에 코드베이스 관련 퀴즈를 자동 출제하는 봇.
Claude Code CLI를 활용하여 로컬 레포지토리를 분석하고 퀴즈를 생성합니다.

## 주요 기능

- **자동 퀴즈 출제**: 평일 오전 10시 자동 출제
- **자동 정답 공개**: 오후 4시 정답 및 해설 공개
- **3가지 퀴즈 유형**: 코드베이스 구조, 라이브러리 활용, 최근 변경사항
- **난이도 조절**: easy / medium / hard
- **JSON 파일 저장**: 모든 퀴즈가 `quizzes/` 폴더에 저장됨

## 퀴즈 유형

| 타입 | 설명 | 예시 |
|------|------|------|
| `codebase` | 프로젝트 구조, 아키텍처 | "라우터 설정 파일의 위치는?" |
| `library` | 의존성 패키지 사용법 | "Vue Query의 staleTime 기본값은?" |
| `recent_change` | 최근 커밋/변경사항 | "이 커밋에서 추가된 기능은?" |

## 설치

### 사전 요구사항

- Python 3.11+
- [uv](https://github.com/astral-sh/uv) 패키지 매니저
- [Claude Code CLI](https://claude.ai/code) 설치 및 인증

### 설치 과정

```bash
# 1. 의존성 설치
make install

# 2. 환경 변수 설정
cp .env.example .env
# .env 파일 편집 (아래 참고)

# 3. 대상 레포지토리 클론
git clone <your-repo-url> ./your-repo

# 4. 데이터베이스 초기화
make init
```

## 환경 변수 (.env)

```env
# Mattermost Incoming Webhook (필수)
MATTERMOST_WEBHOOK_URL=https://your-mattermost.com/hooks/xxxx

# 대상 레포지토리 경로 (필수)
TARGET_REPO_PATH=./your-repo
TARGET_REPO_NAME=your-repo

# Claude Code CLI 경로 (기본: claude)
CLAUDE_CODE_PATH=claude

# 스케줄 설정 (cron 형식)
QUIZ_PUBLISH_CRON=0 10 * * 1-5    # 평일 오전 10시
QUIZ_GRADING_CRON=0 16 * * 1-5    # 평일 오후 4시
```

## 사용법

### Make 명령어

```bash
make install     # 의존성 설치
make init        # DB 초기화
make quiz        # 퀴즈 출제 (랜덤 타입)
make grade       # 정답 공개
make serve       # 스케줄러 서버 실행
make generate    # 테스트용 퀴즈 생성 (Mattermost 게시 안함)
```

### 상세 명령어

```bash
# 퀴즈 출제 (타입 지정)
uv run daily-quiz quiz --type codebase
uv run daily-quiz quiz --type library
uv run daily-quiz quiz --type recent_change

# 난이도 지정
uv run daily-quiz quiz --type library --difficulty easy
uv run daily-quiz quiz --type library --difficulty hard

# 테스트용 퀴즈 생성 (여러 개)
uv run daily-quiz generate -n 5
uv run daily-quiz generate --type codebase -n 3
```

## 프로젝트 구조

```
daily-quiz/
├── src/
│   ├── main.py              # CLI 엔트리포인트
│   ├── config.py            # 설정 관리
│   ├── ai/
│   │   └── claude_code.py   # Claude Code CLI 연동
│   ├── analysis/
│   │   └── local_repo.py    # 로컬 레포지토리 분석
│   ├── bot/
│   │   └── webhook.py       # Mattermost Webhook
│   ├── db/
│   │   ├── database.py      # DB 연결
│   │   ├── models.py        # SQLAlchemy 모델
│   │   └── repository.py    # 데이터 접근 계층
│   ├── quiz/
│   │   ├── generator.py     # 퀴즈 생성 엔진
│   │   └── session.py       # 세션 관리
│   └── scheduler/
│       └── jobs.py          # APScheduler 작업
├── quizzes/                 # 생성된 퀴즈 JSON 파일
├── .env                     # 환경 변수
├── quiz.db                  # SQLite 데이터베이스
├── Makefile
└── pyproject.toml
```

## Mattermost 설정

1. **Incoming Webhook 생성**
   - Mattermost > 통합 (Integrations) > Incoming Webhooks
   - "Webhook 추가" 클릭
   - 채널 선택 후 저장
   - 생성된 URL을 `.env`의 `MATTERMOST_WEBHOOK_URL`에 설정

2. **퀴즈 메시지 형식**
   - 문제와 4지선다 보기가 테이블로 표시됨
   - 팀원들은 이모지 반응(1️⃣ 2️⃣ 3️⃣ 4️⃣)으로 답변

## 라이선스

MIT
