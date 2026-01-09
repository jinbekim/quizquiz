"""Mattermost Incoming Webhook integration."""

from typing import Optional

import httpx
import structlog

from src.config import settings
from src.db.models import Quiz, QuizSession

logger = structlog.get_logger()

DIFFICULTY_STARS = {
    "easy": "⭐",
    "medium": "⭐⭐",
    "hard": "⭐⭐⭐",
}


class MattermostWebhook:
    """Mattermost webhook client for posting messages."""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or settings.mattermost_webhook_url

    def post_quiz(self, quiz: Quiz, session: QuizSession) -> bool:
        """Post quiz to channel via webhook."""
        if not self.webhook_url:
            logger.warning("webhook_url_not_configured")
            return False

        difficulty_display = DIFFICULTY_STARS.get(quiz.difficulty, "⭐⭐")

        message = f"""### 📚 Daily Quiz #{session.id} | 난이도: {difficulty_display} ({quiz.difficulty})
---

**❓ {quiz.question}**

1️⃣ {quiz.options.get("1", "")}
2️⃣ {quiz.options.get("2", "")}
3️⃣ {quiz.options.get("3", "")}
4️⃣ {quiz.options.get("4", "")}

---
⏰ **오후 4시**에 정답이 공개됩니다!
✋ 이 메시지에 **이모지 반응**으로 답변해주세요! (1️⃣ 2️⃣ 3️⃣ 4️⃣)"""

        return self._send_message(message)

    def post_answer(self, quiz: Quiz, session: QuizSession) -> bool:
        """Post answer to channel via webhook."""
        if not self.webhook_url:
            return False

        answer_emoji = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣"}.get(quiz.answer, quiz.answer)

        message = f"""### ✅ Daily Quiz #{session.id} 정답 발표!
---

**정답: {answer_emoji} {quiz.options.get(quiz.answer, "")}**

📖 **해설:**
{quiz.explanation}

{f"📁 참고: `{quiz.source_file}`" if quiz.source_file else ""}
---
🎯 다음 퀴즈도 기대해주세요!"""

        return self._send_message(message)

    def _send_message(self, text: str, props: Optional[dict] = None) -> bool:
        """Send message via webhook."""
        payload = {"text": text}
        if props:
            payload["props"] = props

        try:
            response = httpx.post(
                self.webhook_url,
                json=payload,
                timeout=10,
            )
            if response.status_code == 200:
                logger.info("webhook_message_sent")
                return True
            else:
                logger.error(
                    "webhook_send_failed",
                    status_code=response.status_code,
                    response=response.text,
                )
                return False
        except Exception as e:
            logger.error("webhook_error", error=str(e))
            return False


# Singleton instance
webhook = MattermostWebhook()
