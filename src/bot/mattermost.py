"""Mattermost bot handler for quiz interactions."""

from datetime import datetime
from typing import Optional

import structlog
from mattermostdriver import Driver

from src.config import settings
from src.db.database import get_db
from src.db.models import Quiz, QuizSession, SessionStatus, UserResponse
from src.db.repository import (
    QuizRepository,
    QuizSessionRepository,
    UserRepository,
    UserResponseRepository,
)

logger = structlog.get_logger()

# Emoji to answer mapping
EMOJI_ANSWERS = {
    "one": "1",
    "two": "2",
    "three": "3",
    "four": "4",
    "1️⃣": "1",
    "2️⃣": "2",
    "3️⃣": "3",
    "4️⃣": "4",
}

DIFFICULTY_STARS = {
    "easy": "⭐",
    "medium": "⭐⭐",
    "hard": "⭐⭐⭐",
}


class MattermostBot:
    """Mattermost bot for quiz interactions."""

    def __init__(self):
        self.driver = Driver({
            "url": settings.mattermost_url.rstrip("/"),
            "token": settings.mattermost_token,
            "scheme": "https",
            "port": 443,
        })
        self.channel_id = settings.mattermost_channel_id
        self._connected = False

    def connect(self) -> None:
        """Connect to Mattermost."""
        if not self._connected:
            self.driver.login()
            self._connected = True
            logger.info("connected_to_mattermost")

    def disconnect(self) -> None:
        """Disconnect from Mattermost."""
        if self._connected:
            self.driver.logout()
            self._connected = False
            logger.info("disconnected_from_mattermost")

    def post_quiz(self, quiz: Quiz, session: QuizSession) -> Optional[str]:
        """Post a quiz to the channel and return post ID."""
        self.connect()

        difficulty_display = DIFFICULTY_STARS.get(quiz.difficulty, "⭐⭐")
        message = f"""📚 **Daily Quiz #{session.id}** | 난이도: {difficulty_display} ({quiz.difficulty})
━━━━━━━━━━━━━━━━━━━━━━━━━

❓ {quiz.question}

1️⃣ {quiz.options.get("1", "")}
2️⃣ {quiz.options.get("2", "")}
3️⃣ {quiz.options.get("3", "")}
4️⃣ {quiz.options.get("4", "")}

⏰ 오후 4시까지 리액션으로 답변해주세요!
━━━━━━━━━━━━━━━━━━━━━━━━━"""

        try:
            response = self.driver.posts.create_post({
                "channel_id": self.channel_id,
                "message": message,
            })
            post_id = response.get("id")

            # Add reaction options to the post
            for emoji in ["one", "two", "three", "four"]:
                try:
                    self.driver.reactions.create_reaction({
                        "user_id": self.driver.users.get_user("me")["id"],
                        "post_id": post_id,
                        "emoji_name": emoji,
                    })
                except Exception as e:
                    logger.warning("failed_to_add_reaction", emoji=emoji, error=str(e))

            logger.info("posted_quiz", post_id=post_id, quiz_id=quiz.id)
            return post_id
        except Exception as e:
            logger.error("failed_to_post_quiz", error=str(e))
            return None

    def post_results(self, session: QuizSession, quiz: Quiz, responses: list[UserResponse]) -> None:
        """Post quiz results to the channel."""
        self.connect()

        correct_responses = [r for r in responses if r.is_correct]
        total_responses = len(responses)
        correct_count = len(correct_responses)
        accuracy = (correct_count / total_responses * 100) if total_responses > 0 else 0

        # Get usernames for correct responders
        db = get_db()
        try:
            user_repo = UserRepository(db)
            correct_users = []
            for r in correct_responses:
                user = db.get(user_repo.db.get(r.user_id).__class__, r.user_id)
                if user:
                    correct_users.append(f"@{user.username} ({quiz.points}점)")
        finally:
            db.close()

        winners_text = ", ".join(correct_users) if correct_users else "없음"

        message = f"""✅ **Daily Quiz #{session.id} 정답 발표!**
━━━━━━━━━━━━━━━━━━━━━━━━━

정답: {self._get_answer_emoji(quiz.answer)} {quiz.options.get(quiz.answer, "")}

📖 **해설:**
{quiz.explanation}
{f"참고: {quiz.source_file}" if quiz.source_file else ""}

🏆 **정답자:** {winners_text}
📊 **정답률:** {accuracy:.0f}% ({correct_count}/{total_responses}명)
━━━━━━━━━━━━━━━━━━━━━━━━━"""

        try:
            self.driver.posts.create_post({
                "channel_id": self.channel_id,
                "message": message,
            })
            logger.info("posted_results", session_id=session.id)
        except Exception as e:
            logger.error("failed_to_post_results", error=str(e))

    def post_leaderboard(self, limit: int = 5) -> None:
        """Post current leaderboard to the channel."""
        self.connect()

        db = get_db()
        try:
            user_repo = UserRepository(db)
            top_users = user_repo.get_leaderboard(limit=limit)

            if not top_users:
                return

            leaderboard_lines = []
            medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
            for i, user in enumerate(top_users):
                medal = medals[i] if i < len(medals) else f"{i+1}."
                leaderboard_lines.append(
                    f"{medal} @{user.username} - {user.total_points}점 (🔥 {user.current_streak}일)"
                )

            message = f"""🏆 **이번 주 리더보드**
━━━━━━━━━━━━━━━━━━━━━━━━━

{chr(10).join(leaderboard_lines)}

━━━━━━━━━━━━━━━━━━━━━━━━━"""

            self.driver.posts.create_post({
                "channel_id": self.channel_id,
                "message": message,
            })
        finally:
            db.close()

    def get_reactions(self, post_id: str) -> dict[str, list[str]]:
        """Get reactions on a post. Returns {emoji: [user_ids]}."""
        self.connect()

        try:
            reactions = self.driver.reactions.get_reactions(post_id)
            result: dict[str, list[str]] = {}
            for reaction in reactions:
                emoji = reaction.get("emoji_name", "")
                user_id = reaction.get("user_id", "")
                if emoji and user_id:
                    if emoji not in result:
                        result[emoji] = []
                    result[emoji].append(user_id)
            return result
        except Exception as e:
            logger.error("failed_to_get_reactions", post_id=post_id, error=str(e))
            return {}

    def get_user_info(self, user_id: str) -> Optional[dict]:
        """Get user information."""
        self.connect()
        try:
            return self.driver.users.get_user(user_id)
        except Exception as e:
            logger.error("failed_to_get_user_info", user_id=user_id, error=str(e))
            return None

    def _get_answer_emoji(self, answer: str) -> str:
        """Convert answer number to emoji."""
        return {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣"}.get(answer, answer)


# Singleton instance
mattermost_bot = MattermostBot()
