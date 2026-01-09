"""Quiz generation engine using local repository analysis."""

import json
import random
from datetime import datetime
from pathlib import Path
from typing import Optional

import structlog

from src.ai.claude_code import claude_client, GeneratedQuiz
from src.analysis.local_repo import local_repo
from src.db.database import get_db
from src.db.models import Quiz, QuizType
from src.db.repository import QuizRepository

logger = structlog.get_logger()

# Quiz export directory
QUIZ_EXPORT_DIR = Path("quizzes")

# Topic variations for more diverse questions
LIBRARY_TOPICS = [
    "기본 API 사용법",
    "고급 기능 활용",
    "설정 및 옵션",
    "흔한 실수와 해결법",
    "성능 최적화 팁",
    "TypeScript 타입 활용",
    "베스트 프랙티스",
    "다른 라이브러리와의 비교",
]

CODEBASE_TOPICS = [
    "파일/폴더 구조",
    "컴포넌트 역할",
    "라우팅 설정",
    "상태 관리",
    "API 호출 패턴",
    "스타일링 방식",
    "빌드 및 배포 설정",
    "테스트 구조",
]

RECENT_CHANGE_TOPICS = [
    "변경의 비즈니스 목적과 배경",
    "기존 동작 방식과 새로운 동작 방식의 차이",
    "이 변경이 사용자 경험에 미치는 영향",
    "변경으로 해결된 기술적 문제점",
    "코드 설계/아키텍처 결정의 이유",
    "이 변경과 관련된 프로젝트 컨벤션이나 패턴",
    "변경 전후의 데이터 흐름 차이",
    "이 기능이 전체 시스템에서 하는 역할",
]


class QuizGenerator:
    """Engine for generating quiz questions from local repository."""

    def __init__(self):
        self.repo = local_repo

    async def generate_codebase_quiz(self, difficulty: str = "medium") -> Optional[Quiz]:
        """Generate a quiz about codebase structure."""
        try:
            # Pull latest changes
            self.repo.git_pull()

            # Get repository context
            context = self.repo.get_repo_context()

            # Randomly select files to focus on
            all_files = context.sample_files or []
            if len(all_files) > 10:
                selected_files = random.sample(all_files, 10)
            else:
                selected_files = all_files

            # Random topic focus
            selected_topic = random.choice(CODEBASE_TOPICS)

            logger.info("codebase_quiz_focus", topic=selected_topic)

            # Build context string
            context_str = f"""
프로젝트: {context.name}

[퀴즈 주제]
{selected_topic}

디렉토리 구조:
{context.structure}

샘플 소스 파일:
{chr(10).join(f"- {f}" for f in selected_files)}
"""
            if context.package_json:
                scripts = context.package_json.get("scripts", {})
                context_str += f"""
npm scripts: {', '.join(list(scripts.keys())[:10])}

[요청사항]
위 프로젝트의 "{selected_topic}"에 관한 퀴즈를 만들어주세요.
이전에 출제된 문제와 다른 새로운 관점의 문제를 만들어주세요.
"""

            # Generate quiz using Claude
            generated = claude_client.generate_quiz(
                code_context=context_str,
                quiz_type=QuizType.CODEBASE.value,
                difficulty=difficulty,
            )

            if not generated:
                return None

            return self._create_quiz_from_generated(generated)
        except Exception as e:
            logger.error("failed_to_generate_codebase_quiz", error=str(e))
            return None

    async def generate_library_quiz(self, difficulty: str = "medium") -> Optional[Quiz]:
        """Generate a quiz about library usage."""
        try:
            # Get package.json
            package_json = self.repo.get_package_json()
            if not package_json:
                logger.warning("no_package_json_found")
                return None

            # Build context from dependencies
            deps = package_json.get("dependencies", {})
            dev_deps = package_json.get("devDependencies", {})

            # Interesting libraries to quiz about
            interesting_libs = [
                ("vue", "Vue 3 - 프레임워크 코어"),
                ("pinia", "Pinia - 상태 관리"),
                ("vue-router", "Vue Router - 라우팅"),
                ("axios", "Axios - HTTP 클라이언트"),
                ("echarts", "ECharts - 차트 라이브러리"),
                ("dayjs", "Day.js - 날짜 처리"),
                ("lodash-es", "Lodash - 유틸리티 함수"),
                ("zod", "Zod - 스키마 검증"),
                ("@tanstack/vue-query", "TanStack Query - 서버 상태 관리"),
                ("@vueuse/core", "VueUse - Composition 유틸리티"),
                ("radix-vue", "Radix Vue - UI 컴포넌트"),
                ("vite", "Vite - 빌드 도구"),
                ("typescript", "TypeScript - 타입 시스템"),
                ("vitest", "Vitest - 테스트 프레임워크"),
            ]

            # Filter to libraries actually in the project
            available_libs = [
                (name, desc) for name, desc in interesting_libs
                if name in deps or name in dev_deps
            ]

            if not available_libs:
                available_libs = interesting_libs[:5]  # fallback

            # Randomly select ONE library to focus on
            selected_lib, lib_desc = random.choice(available_libs)
            selected_topic = random.choice(LIBRARY_TOPICS)

            logger.info("library_quiz_focus", library=selected_lib, topic=selected_topic)

            context = f"""
프로젝트: {package_json.get('name', 'unknown')} (Vue 3 + TypeScript + Vite)

[퀴즈 대상 라이브러리]
{selected_lib} - {lib_desc}

[퀴즈 주제]
{selected_topic}

[요청사항]
위 라이브러리의 "{selected_topic}"에 관한 실용적인 퀴즈를 만들어주세요.
이전에 출제된 문제와 다른 새로운 관점의 문제를 만들어주세요.
"""

            generated = claude_client.generate_quiz(
                code_context=context,
                quiz_type=QuizType.LIBRARY.value,
                difficulty=difficulty,
            )

            if not generated:
                return None

            return self._create_quiz_from_generated(generated)
        except Exception as e:
            logger.error("failed_to_generate_library_quiz", error=str(e))
            return None

    async def generate_recent_change_quiz(self, difficulty: str = "medium") -> Optional[Quiz]:
        """Generate a quiz about recent changes."""
        try:
            # Pull and get recent commits
            self.repo.git_pull()
            commits = self.repo.get_recent_commits(limit=10)

            if not commits:
                logger.warning("no_recent_commits_found")
                return None

            # Pick a random commit
            commit = random.choice(commits)
            files_changed = self.repo.get_commit_files(commit.sha)
            diff_content = self.repo.get_commit_diff(commit.sha, max_lines=150)

            # Random topic focus for deeper understanding
            selected_topic = random.choice(RECENT_CHANGE_TOPICS)

            logger.info("recent_change_quiz_focus", topic=selected_topic, commit=commit.sha[:7])

            context = f"""
최근 커밋 정보:

커밋: {commit.sha[:7]}
작성자: {commit.author}
날짜: {commit.date}
메시지: {commit.message}

변경된 파일:
{chr(10).join(f"- {f}" for f in files_changed[:10])}

[실제 변경 내용 (diff)]
{diff_content}

[퀴즈 주제]
{selected_topic}

[요청사항]
위 커밋의 변경 내용을 분석하여 "{selected_topic}"에 관한 퀴즈를 만들어주세요.

주의사항:
- 단순히 "어떤 파일이 변경되었나요?" 같은 피상적인 문제는 피해주세요.
- 변경 내용을 이해해야만 풀 수 있는 문제를 만들어주세요.
- 이 변경이 프로젝트의 동작, 정책, 설계에 어떤 의미가 있는지 묻는 문제여야 합니다.
- 팀원이 이 커밋으로 프로젝트 이해도를 높일 수 있는 교육적 문제를 만들어주세요.
- **필수**: 문제 텍스트 시작 부분에 반드시 커밋 정보를 포함해주세요.
  형식: "커밋 {{해시}} ({{커밋 메시지}})에 대한 질문입니다."
  예시: "커밋 abc1234 (feat: 로그인 기능 추가)에 대한 질문입니다. 이 변경에서..."
"""

            generated = claude_client.generate_quiz(
                code_context=context,
                quiz_type=QuizType.RECENT_CHANGE.value,
                difficulty=difficulty,
            )

            if not generated:
                return None

            return self._create_quiz_from_generated(generated)
        except Exception as e:
            logger.error("failed_to_generate_recent_change_quiz", error=str(e))
            return None

    async def generate_quiz(
        self,
        quiz_type: Optional[str] = None,
        difficulty: str = "medium",
    ) -> Optional[Quiz]:
        """Generate a quiz of specified type or random type."""
        if quiz_type is None:
            quiz_type = random.choice([
                QuizType.CODEBASE.value,
                QuizType.LIBRARY.value,
                QuizType.RECENT_CHANGE.value,
            ])

        logger.info("generating_quiz", quiz_type=quiz_type, difficulty=difficulty)

        if quiz_type == QuizType.CODEBASE.value:
            return await self.generate_codebase_quiz(difficulty)
        elif quiz_type == QuizType.LIBRARY.value:
            return await self.generate_library_quiz(difficulty)
        elif quiz_type == QuizType.RECENT_CHANGE.value:
            return await self.generate_recent_change_quiz(difficulty)
        else:
            logger.warning("unsupported_quiz_type", quiz_type=quiz_type)
            return None

    def _format_deps(self, deps: dict) -> str:
        """Format dependencies for context."""
        if not deps:
            return "None"
        return "\n".join(f"- {name}: {version}" for name, version in list(deps.items())[:15])

    def _create_quiz_from_generated(self, generated: GeneratedQuiz) -> Quiz:
        """Create Quiz model from generated data."""
        quiz = Quiz(
            type=generated.type,
            difficulty=generated.difficulty,
            question=generated.question,
            options=generated.options,
            answer=generated.answer,
            explanation=generated.explanation,
            source_file=generated.source_file,
        )

        # Save to database
        db = get_db()
        try:
            repo = QuizRepository(db)
            quiz = repo.create(quiz)

            # Also save to JSON file
            self._export_quiz_to_file(quiz)

            return quiz
        finally:
            db.close()

    def _export_quiz_to_file(self, quiz: Quiz) -> None:
        """Export quiz to JSON file."""
        try:
            QUIZ_EXPORT_DIR.mkdir(exist_ok=True)

            filename = f"quiz_{quiz.id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = QUIZ_EXPORT_DIR / filename

            quiz_data = {
                "id": quiz.id,
                "type": quiz.type,
                "difficulty": quiz.difficulty,
                "question": quiz.question,
                "options": quiz.options,
                "answer": quiz.answer,
                "explanation": quiz.explanation,
                "source_file": quiz.source_file,
                "created_at": quiz.created_at.isoformat() if quiz.created_at else None,
            }

            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(quiz_data, f, ensure_ascii=False, indent=2)

            logger.info("quiz_exported_to_file", filepath=str(filepath))
        except Exception as e:
            logger.warning("failed_to_export_quiz", error=str(e))


# Singleton instance
quiz_generator = QuizGenerator()
