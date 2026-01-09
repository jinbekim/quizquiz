"""Claude Code CLI integration for quiz generation."""

import json
import subprocess
from dataclasses import dataclass
from typing import Optional

import structlog

from src.config import settings

logger = structlog.get_logger()


@dataclass
class GeneratedQuiz:
    """Generated quiz data from Claude Code."""

    type: str
    difficulty: str
    question: str
    options: dict[str, str]
    answer: str
    explanation: str
    source_file: Optional[str] = None


QUIZ_GENERATION_PROMPT = """당신은 개발팀을 위한 퀴즈 생성기입니다. 주어진 코드 컨텍스트를 바탕으로 퀴즈 문제를 생성하세요.

컨텍스트:
{code_context}

퀴즈 유형: {quiz_type}
난이도: {difficulty}

요구사항:
1. 4지선다 객관식 문제 1개 생성
2. 실무에서 유용한 지식을 테스트하는 문제
3. 명확한 해설 포함
4. 한국어로 작성

중요: 반드시 아래 JSON 형식으로만 응답하세요. 다른 텍스트 없이 JSON만 출력하세요.

{{"type":"{quiz_type}","difficulty":"{difficulty}","question":"질문 내용","options":{{"1":"선택지1","2":"선택지2","3":"선택지3","4":"선택지4"}},"answer":"정답번호","explanation":"해설","source_file":"관련파일경로"}}"""


class ClaudeCodeClient:
    """Client for interacting with Claude Code CLI."""

    def __init__(self, cli_path: Optional[str] = None):
        self.cli_path = cli_path or settings.claude_code_path

    def generate_quiz(
        self,
        code_context: str,
        quiz_type: str = "codebase",
        difficulty: str = "medium",
    ) -> Optional[GeneratedQuiz]:
        """Generate a quiz question using Claude Code CLI."""
        prompt = QUIZ_GENERATION_PROMPT.format(
            code_context=code_context,
            quiz_type=quiz_type,
            difficulty=difficulty,
        )

        try:
            result = self._run_claude(prompt)
            if not result:
                return None

            # Parse JSON response
            quiz_data = self._parse_json_response(result)
            if not quiz_data:
                return None

            return GeneratedQuiz(
                type=quiz_data.get("type", quiz_type),
                difficulty=quiz_data.get("difficulty", difficulty),
                question=quiz_data["question"],
                options=quiz_data["options"],
                answer=quiz_data["answer"],
                explanation=quiz_data["explanation"],
                source_file=quiz_data.get("source_file"),
            )
        except Exception as e:
            logger.error("failed_to_generate_quiz", error=str(e))
            return None

    def _run_claude(self, prompt: str) -> Optional[str]:
        """Run Claude Code CLI with the given prompt."""
        try:
            result = subprocess.run(
                [
                    self.cli_path,
                    "-p",
                    prompt,
                    "--output-format",
                    "json",
                ],
                capture_output=True,
                text=True,
                timeout=180,  # 3 minute timeout
            )

            if result.returncode != 0:
                logger.error(
                    "claude_cli_error",
                    stderr=result.stderr,
                    returncode=result.returncode,
                )
                return None

            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            logger.error("claude_cli_timeout")
            return None
        except FileNotFoundError:
            logger.error("claude_cli_not_found", path=self.cli_path)
            return None

    def _parse_json_response(self, response: str) -> Optional[dict]:
        """Parse JSON from Claude's response."""
        try:
            # First, try to parse as Claude CLI JSON output format
            outer = json.loads(response)
            if isinstance(outer, dict) and "result" in outer:
                response = outer["result"]
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code block
        if "```json" in response:
            start = response.find("```json") + 7
            end = response.find("```", start)
            if end > start:
                try:
                    return json.loads(response[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try to extract from ``` block without json tag
        if "```" in response:
            start = response.find("```") + 3
            # Skip language tag if present
            newline = response.find("\n", start)
            if newline > start:
                start = newline + 1
            end = response.find("```", start)
            if end > start:
                try:
                    return json.loads(response[start:end].strip())
                except json.JSONDecodeError:
                    pass

        # Try to find JSON object in the response
        start = response.find("{")
        end = response.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                return json.loads(response[start:end])
            except json.JSONDecodeError:
                pass

        logger.error("failed_to_parse_json", response=response[:500])
        return None


# Singleton instance
claude_client = ClaudeCodeClient()
