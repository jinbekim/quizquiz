.PHONY: install init quiz grade serve generate clean help quiz-types

# 기본 설정
PYTHON := uv run
CLI := $(PYTHON) daily-quiz

help: ## 도움말 표시
	@echo "Daily Quiz - Mattermost 퀴즈 봇"
	@echo ""
	@echo "사용 가능한 명령어:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## 의존성 설치
	uv sync --dev

init: ## 데이터베이스 초기화
	$(CLI) init

quiz: ## 퀴즈 출제 (랜덤 타입)
	$(CLI) quiz

quiz-codebase: ## 코드베이스 구조 퀴즈 출제
	$(CLI) quiz --type codebase

quiz-library: ## 라이브러리 활용 퀴즈 출제
	$(CLI) quiz --type library

quiz-recent: ## 최근 변경사항 퀴즈 출제
	$(CLI) quiz --type recent_change

quiz-types: ## 퀴즈 타입 목록 조회
	@echo "사용 가능한 퀴즈 타입:"
	@echo "  codebase      - 코드베이스 구조 관련 퀴즈"
	@echo "  library       - 사용 중인 라이브러리 관련 퀴즈"
	@echo "  recent_change - 최근 커밋 기반 퀴즈"

grade: ## 활성 세션 정답 공개
	$(CLI) grade

serve: ## 스케줄러 서버 실행 (Ctrl+C로 종료)
	$(CLI) serve

generate: ## 테스트용 퀴즈 생성 (Mattermost 미게시)
	$(CLI) generate

generate-n: ## 테스트용 퀴즈 N개 생성 (예: make generate-n N=5)
	$(CLI) generate -n $(N)

clean: ## 생성된 파일 정리 (DB, 퀴즈 파일)
	rm -f quiz.db
	rm -rf quizzes/
	@echo "정리 완료"

# 난이도별 퀴즈 출제
quiz-easy: ## 쉬운 난이도 퀴즈 출제
	$(CLI) quiz --difficulty easy

quiz-hard: ## 어려운 난이도 퀴즈 출제
	$(CLI) quiz --difficulty hard
