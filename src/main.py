"""Main entry point for Daily Quiz bot."""

import argparse
import asyncio
import signal
import sys
import time
from typing import Optional

import structlog

from src.db.database import init_db
from src.quiz.generator import quiz_generator
from src.quiz.session import session_manager
from src.scheduler.jobs import quiz_scheduler

# Configure structlog
structlog.configure(
    processors=[
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer(colors=True),
    ],
    wrapper_class=structlog.make_filtering_bound_logger(20),  # INFO level
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


def handle_shutdown(signum, frame) -> None:
    """Handle shutdown signals gracefully."""
    logger.info("shutdown_signal_received", signal=signum)
    quiz_scheduler.stop()
    mattermost_bot.disconnect()
    sys.exit(0)


async def manual_quiz(
    quiz_type: Optional[str] = None,
    difficulty: str = "medium",
) -> None:
    """Manually trigger a quiz."""
    logger.info("manual_quiz_triggered", quiz_type=quiz_type, difficulty=difficulty)
    session = await session_manager.start_quiz(quiz_type=quiz_type, difficulty=difficulty)
    if session:
        logger.info("quiz_published", session_id=session.id)
    else:
        logger.error("failed_to_publish_quiz")


def manual_grade() -> None:
    """Manually grade active sessions."""
    logger.info("manual_grade_triggered")
    session_manager.grade_active_sessions()
    logger.info("grading_completed")


async def generate_only(
    quiz_type: Optional[str] = None,
    difficulty: str = "medium",
    count: int = 1,
) -> None:
    """Generate quizzes without creating sessions (test mode)."""
    from src.db.models import Quiz

    for i in range(count):
        if count > 1:
            print(f"\n[{i+1}/{count}]")

        quiz = await quiz_generator.generate_quiz(quiz_type=quiz_type, difficulty=difficulty)
        if quiz:
            _print_quiz(quiz)
        else:
            print("❌ 퀴즈 생성 실패")


def _print_quiz(quiz) -> None:
    """Print quiz to console."""
    difficulty_stars = {"easy": "⭐", "medium": "⭐⭐", "hard": "⭐⭐⭐"}
    print("\n" + "=" * 60)
    print(f"📚 Quiz #{quiz.id} | Type: {quiz.type} | 난이도: {difficulty_stars.get(quiz.difficulty, '⭐⭐')}")
    print("=" * 60)
    print(f"\n❓ {quiz.question}\n")
    for key, value in quiz.options.items():
        emoji = {"1": "1️⃣", "2": "2️⃣", "3": "3️⃣", "4": "4️⃣"}.get(key, key)
        print(f"  {emoji} {value}")
    print("\n" + "-" * 60)
    print(f"✅ 정답: {quiz.answer}")
    print(f"\n📖 해설:\n{quiz.explanation}")
    if quiz.source_file:
        print(f"\n📁 참고: {quiz.source_file}")
    print("=" * 60)


def run_server() -> None:
    """Run the bot server with scheduler."""
    logger.info("starting_daily_quiz_bot")

    # Initialize database
    init_db()
    logger.info("database_initialized")

    # Setup signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Connect to Mattermost
    try:
        mattermost_bot.connect()
    except Exception as e:
        logger.error("failed_to_connect_mattermost", error=str(e))
        sys.exit(1)

    # Start scheduler
    quiz_scheduler.start()

    logger.info("bot_running", message="Press Ctrl+C to stop")

    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handle_shutdown(signal.SIGINT, None)


def main() -> None:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Daily Quiz Bot for Mattermost")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Server command
    subparsers.add_parser("serve", help="Run the bot server with scheduler")

    # Quiz command
    quiz_parser = subparsers.add_parser("quiz", help="Manually trigger a quiz")
    quiz_parser.add_argument(
        "--type",
        choices=["codebase", "library", "recent_change"],
        default=None,
        help="Quiz type (random if not specified)",
    )
    quiz_parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="Quiz difficulty",
    )

    # Generate command (test only, no session)
    gen_parser = subparsers.add_parser("generate", help="Generate quiz without session (test mode)")
    gen_parser.add_argument(
        "--type",
        choices=["codebase", "library", "recent_change"],
        default=None,
        help="Quiz type (random if not specified)",
    )
    gen_parser.add_argument(
        "--difficulty",
        choices=["easy", "medium", "hard"],
        default="medium",
        help="Quiz difficulty",
    )
    gen_parser.add_argument(
        "-n",
        type=int,
        default=1,
        help="Number of quizzes to generate",
    )

    # Grade command
    subparsers.add_parser("grade", help="Grade active quiz sessions")

    # Leaderboard command
    subparsers.add_parser("leaderboard", help="Post current leaderboard")

    # Init command
    subparsers.add_parser("init", help="Initialize database")

    args = parser.parse_args()

    if args.command == "serve":
        run_server()
    elif args.command == "quiz":
        init_db()
        asyncio.run(manual_quiz(quiz_type=args.type, difficulty=args.difficulty))
    elif args.command == "generate":
        init_db()
        asyncio.run(generate_only(quiz_type=args.type, difficulty=args.difficulty, count=args.n))
    elif args.command == "grade":
        init_db()
        manual_grade()
    elif args.command == "leaderboard":
        init_db()
        from src.bot.mattermost import mattermost_bot
        mattermost_bot.post_leaderboard()
    elif args.command == "init":
        init_db()
        logger.info("database_initialized")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
