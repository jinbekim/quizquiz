"""Quiz session management and grading."""

from datetime import datetime
from typing import Optional

import structlog

from src.config import settings
from src.db.database import get_db
from src.db.models import Quiz, QuizSession, SessionStatus
from src.db.repository import QuizRepository, QuizSessionRepository
from src.quiz.generator import quiz_generator

logger = structlog.get_logger()


def is_webhook_configured() -> bool:
    """Check if Mattermost webhook is configured."""
    return bool(settings.mattermost_webhook_url)


class QuizSessionManager:
    """Manager for quiz sessions."""

    def __init__(self):
        self._webhook = None

    @property
    def webhook(self):
        """Lazy load webhook client only when needed."""
        if self._webhook is None and is_webhook_configured():
            from src.bot.webhook import webhook
            self._webhook = webhook
        return self._webhook

    async def start_quiz(
        self,
        quiz_type: Optional[str] = None,
        difficulty: str = "medium",
    ) -> Optional[QuizSession]:
        """Generate a quiz and start a new session."""
        # Generate quiz
        quiz = await quiz_generator.generate_quiz(quiz_type=quiz_type, difficulty=difficulty)
        if not quiz:
            logger.error("failed_to_generate_quiz")
            return None

        # Print quiz to console for testing
        self._print_quiz(quiz)

        db = get_db()
        try:
            # Create session
            session_repo = QuizSessionRepository(db)
            session = QuizSession(
                quiz_id=quiz.id,
                channel_id="webhook" if is_webhook_configured() else "console",
                status=SessionStatus.ACTIVE.value,
            )
            session = session_repo.create(session)

            # Post quiz to Mattermost via webhook
            if self.webhook:
                self.webhook.post_quiz(quiz, session)
                logger.info("quiz_posted_to_mattermost", session_id=session.id)

            logger.info("quiz_session_started", session_id=session.id, quiz_id=quiz.id)
            return session
        finally:
            db.close()

    def _print_quiz(self, quiz: Quiz) -> None:
        """Print quiz to console for testing."""
        difficulty_stars = {"easy": "⭐", "medium": "⭐⭐", "hard": "⭐⭐⭐"}
        print("\n" + "=" * 60)
        print(f"📚 Quiz #{quiz.id} | 난이도: {difficulty_stars.get(quiz.difficulty, '⭐⭐')} ({quiz.difficulty})")
        print("=" * 60)
        print(f"\n❓ {quiz.question}\n")
        for key, value in quiz.options.items():
            emoji = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣"}.get(key, key)
            print(f"  {emoji} {value}")
        print("\n" + "-" * 60)
        print(f"✅ 정답: {quiz.answer}")
        print(f"\n📖 해설: {quiz.explanation}")
        if quiz.source_file:
            print(f"📁 참고: {quiz.source_file}")
        print("=" * 60 + "\n")

    def grade_session(self, session_id: int) -> None:
        """Grade a quiz session and post answer."""
        db = get_db()
        try:
            session_repo = QuizSessionRepository(db)
            quiz_repo = QuizRepository(db)

            # Get session
            session = db.get(QuizSession, session_id)
            if not session:
                logger.error("session_not_found", session_id=session_id)
                return

            if session.status != SessionStatus.ACTIVE.value:
                logger.warning("session_not_active", session_id=session_id)
                return

            # Get quiz
            quiz = quiz_repo.get_by_id(session.quiz_id)
            if not quiz:
                logger.error("quiz_not_found", quiz_id=session.quiz_id)
                return

            # Post answer via webhook
            if self.webhook:
                self.webhook.post_answer(quiz, session)
                logger.info("answer_posted_to_mattermost", session_id=session.id)

            # Mark session as completed
            session_repo.complete(session)
            logger.info("quiz_session_completed", session_id=session.id)
        finally:
            db.close()

    def grade_active_sessions(self) -> None:
        """Grade all active sessions (called by scheduler)."""
        db = get_db()
        try:
            from sqlalchemy import select
            stmt = select(QuizSession).where(QuizSession.status == SessionStatus.ACTIVE.value)
            active_sessions = list(db.execute(stmt).scalars().all())

            for session in active_sessions:
                try:
                    self.grade_session(session.id)
                except Exception as e:
                    logger.error("failed_to_grade_session", session_id=session.id, error=str(e))
        finally:
            db.close()


# Singleton instance
session_manager = QuizSessionManager()
