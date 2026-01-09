"""Data access layer for database operations."""

from datetime import datetime
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from src.db.models import Quiz, QuizSession, SessionStatus, User, UserResponse


class QuizRepository:
    """Repository for Quiz operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, quiz: Quiz) -> Quiz:
        """Create a new quiz."""
        self.db.add(quiz)
        self.db.commit()
        self.db.refresh(quiz)
        return quiz

    def get_by_id(self, quiz_id: int) -> Optional[Quiz]:
        """Get quiz by ID."""
        return self.db.get(Quiz, quiz_id)

    def get_random_unused(self) -> Optional[Quiz]:
        """Get a random quiz that hasn't been used recently."""
        # For now, just get the oldest created quiz that hasn't been used in a session
        stmt = (
            select(Quiz)
            .outerjoin(QuizSession)
            .where(QuizSession.id.is_(None))
            .order_by(Quiz.created_at)
            .limit(1)
        )
        result = self.db.execute(stmt).scalar_one_or_none()
        return result


class QuizSessionRepository:
    """Repository for QuizSession operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, session: QuizSession) -> QuizSession:
        """Create a new quiz session."""
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def get_active(self, channel_id: str) -> Optional[QuizSession]:
        """Get active quiz session for a channel."""
        stmt = select(QuizSession).where(
            QuizSession.channel_id == channel_id,
            QuizSession.status == SessionStatus.ACTIVE.value,
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_post_id(self, post_id: str) -> Optional[QuizSession]:
        """Get quiz session by Mattermost post ID."""
        stmt = select(QuizSession).where(QuizSession.post_id == post_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def complete(self, session: QuizSession) -> QuizSession:
        """Mark session as completed."""
        session.status = SessionStatus.COMPLETED.value
        session.ended_at = datetime.now()
        self.db.commit()
        self.db.refresh(session)
        return session


class UserResponseRepository:
    """Repository for UserResponse operations."""

    def __init__(self, db: Session):
        self.db = db

    def create(self, response: UserResponse) -> UserResponse:
        """Create a new user response."""
        self.db.add(response)
        self.db.commit()
        self.db.refresh(response)
        return response

    def get_by_session(self, session_id: int) -> list[UserResponse]:
        """Get all responses for a session."""
        stmt = select(UserResponse).where(UserResponse.session_id == session_id)
        return list(self.db.execute(stmt).scalars().all())

    def user_already_responded(self, session_id: int, user_id: str) -> bool:
        """Check if user already responded to this session."""
        stmt = select(UserResponse).where(
            UserResponse.session_id == session_id,
            UserResponse.user_id == user_id,
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None


class UserRepository:
    """Repository for User operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_or_create(self, user_id: str, username: str) -> User:
        """Get user by ID or create if not exists."""
        user = self.db.get(User, user_id)
        if not user:
            user = User(id=user_id, username=username)
            self.db.add(user)
            self.db.commit()
            self.db.refresh(user)
        return user

    def add_points(self, user_id: str, points: int) -> User:
        """Add points to user."""
        user = self.db.get(User, user_id)
        if user:
            user.total_points += points
            user.last_participation = datetime.now()
            self.db.commit()
            self.db.refresh(user)
        return user

    def get_leaderboard(self, limit: int = 10) -> list[User]:
        """Get top users by total points."""
        stmt = select(User).order_by(desc(User.total_points)).limit(limit)
        return list(self.db.execute(stmt).scalars().all())

    def update_streak(self, user: User, participated_today: bool) -> User:
        """Update user streak based on participation."""
        if participated_today:
            user.current_streak += 1
            if user.current_streak > user.longest_streak:
                user.longest_streak = user.current_streak
        else:
            user.current_streak = 0
        self.db.commit()
        self.db.refresh(user)
        return user
