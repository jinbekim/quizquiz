"""Scheduled jobs for quiz publishing and grading."""

import asyncio

import structlog
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from src.config import settings
from src.quiz.session import session_manager

logger = structlog.get_logger()


def _parse_cron(cron_expr: str) -> dict:
    """Parse cron expression to APScheduler trigger kwargs."""
    parts = cron_expr.split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_expr}")

    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


def publish_quiz_job() -> None:
    """Job to publish daily quiz."""
    logger.info("running_publish_quiz_job")
    try:
        # Run async function in sync context
        asyncio.run(session_manager.start_quiz())
    except Exception as e:
        logger.error("publish_quiz_job_failed", error=str(e))


def grade_quiz_job() -> None:
    """Job to grade active quiz sessions."""
    logger.info("running_grade_quiz_job")
    try:
        session_manager.grade_active_sessions()
    except Exception as e:
        logger.error("grade_quiz_job_failed", error=str(e))


class QuizScheduler:
    """Scheduler for quiz jobs."""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self._setup_jobs()

    def _setup_jobs(self) -> None:
        """Setup scheduled jobs."""
        # Quiz publishing job
        publish_trigger = CronTrigger(**_parse_cron(settings.quiz_publish_cron))
        self.scheduler.add_job(
            publish_quiz_job,
            trigger=publish_trigger,
            id="publish_quiz",
            name="Publish Daily Quiz",
            replace_existing=True,
        )

        # Quiz grading job
        grade_trigger = CronTrigger(**_parse_cron(settings.quiz_grading_cron))
        self.scheduler.add_job(
            grade_quiz_job,
            trigger=grade_trigger,
            id="grade_quiz",
            name="Grade Quiz Sessions",
            replace_existing=True,
        )

        logger.info(
            "scheduler_jobs_configured",
            publish_cron=settings.quiz_publish_cron,
            grade_cron=settings.quiz_grading_cron,
        )

    def start(self) -> None:
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("scheduler_started")

    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()
        logger.info("scheduler_stopped")


# Singleton instance
quiz_scheduler = QuizScheduler()
