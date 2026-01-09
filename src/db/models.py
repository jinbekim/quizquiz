"""SQLAlchemy database models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""

    pass


class QuizType(str, Enum):
    """Quiz type enumeration."""

    CODEBASE = "codebase"
    RECENT_CHANGE = "recent_change"
    LIBRARY = "library"
    CODE_REVIEW = "code_review"
    GIT_HISTORY = "git_history"
    BEST_PRACTICE = "best_practice"


class Difficulty(str, Enum):
    """Quiz difficulty enumeration."""

    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class SessionStatus(str, Enum):
    """Quiz session status enumeration."""

    ACTIVE = "active"
    GRADING = "grading"
    COMPLETED = "completed"


class Quiz(Base):
    """Quiz question model."""

    __tablename__ = "quizzes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict] = mapped_column(JSON, nullable=False)  # {"1": "option1", "2": "option2", ...}
    answer: Mapped[str] = mapped_column(String(10), nullable=False)  # "1", "2", "3", or "4"
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    source_file: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sessions: Mapped[list["QuizSession"]] = relationship(back_populates="quiz")

    @property
    def points(self) -> int:
        """Get points for this quiz based on difficulty."""
        return {"easy": 10, "medium": 20, "hard": 30}.get(self.difficulty, 10)


class QuizSession(Base):
    """Quiz session model - represents a single quiz event."""

    __tablename__ = "quiz_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    quiz_id: Mapped[int] = mapped_column(ForeignKey("quizzes.id"), nullable=False)
    channel_id: Mapped[str] = mapped_column(String(100), nullable=False)
    post_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Mattermost post ID
    status: Mapped[str] = mapped_column(String(20), default=SessionStatus.ACTIVE.value)
    started_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    quiz: Mapped["Quiz"] = relationship(back_populates="sessions")
    responses: Mapped[list["UserResponse"]] = relationship(back_populates="session")


class UserResponse(Base):
    """User response to a quiz."""

    __tablename__ = "user_responses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(ForeignKey("quiz_sessions.id"), nullable=False)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False)  # Mattermost user ID
    answer: Mapped[str] = mapped_column(String(10), nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False)
    response_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # seconds
    points_earned: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    session: Mapped["QuizSession"] = relationship(back_populates="responses")


class User(Base):
    """User model for tracking scores and streaks."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(100), primary_key=True)  # Mattermost user ID
    username: Mapped[str] = mapped_column(String(100), nullable=False)
    total_points: Mapped[int] = mapped_column(Integer, default=0)
    current_streak: Mapped[int] = mapped_column(Integer, default=0)
    longest_streak: Mapped[int] = mapped_column(Integer, default=0)
    badges: Mapped[dict] = mapped_column(JSON, default=dict)
    last_participation: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class Repository(Base):
    """Repository model for tracking analyzed repositories."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # github/gitlab
    default_branch: Mapped[str] = mapped_column(String(100), default="main")
    last_analyzed: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
