"""Local repository analysis for quiz generation."""

import json
import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import structlog

from src.config import settings

logger = structlog.get_logger()


@dataclass
class FileInfo:
    """Information about a file in the repository."""

    path: str
    name: str
    size: int
    extension: str


@dataclass
class CommitInfo:
    """Information about a commit."""

    sha: str
    message: str
    author: str
    date: str
    files_changed: list[str]


@dataclass
class RepoContext:
    """Repository context for quiz generation."""

    name: str
    path: str
    structure: str
    package_json: Optional[dict] = None
    recent_commits: Optional[list[CommitInfo]] = None
    sample_files: Optional[list[str]] = None


class LocalRepoAnalyzer:
    """Analyzer for local repository."""

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = Path(repo_path or settings.target_repo_path).resolve()
        self.repo_name = settings.target_repo_name

    def git_pull(self) -> bool:
        """Pull latest changes from remote."""
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                logger.info("git_pull_success", output=result.stdout.strip())
                return True
            else:
                logger.warning("git_pull_failed", stderr=result.stderr)
                return False
        except Exception as e:
            logger.error("git_pull_error", error=str(e))
            return False

    def get_source_files(
        self,
        extensions: Optional[list[str]] = None,
        limit: int = 100,
    ) -> list[FileInfo]:
        """Get source files from repository."""
        if extensions is None:
            extensions = [".ts", ".tsx", ".vue", ".js", ".jsx"]

        files = []
        exclude_dirs = {"node_modules", ".git", "dist", "build", ".storybook", "coverage"}

        for root, dirs, filenames in os.walk(self.repo_path):
            # Skip excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]

            for filename in filenames:
                if any(filename.endswith(ext) for ext in extensions):
                    full_path = Path(root) / filename
                    rel_path = full_path.relative_to(self.repo_path)
                    files.append(
                        FileInfo(
                            path=str(rel_path),
                            name=filename,
                            size=full_path.stat().st_size,
                            extension=full_path.suffix,
                        )
                    )
                    if len(files) >= limit:
                        return files
        return files

    def get_directory_structure(self, max_depth: int = 3) -> str:
        """Get directory structure as string."""
        exclude_dirs = {"node_modules", ".git", "dist", "build", ".storybook", "coverage", "__pycache__"}
        lines = []

        def walk_dir(path: Path, prefix: str = "", depth: int = 0):
            if depth > max_depth:
                return

            try:
                entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name))
            except PermissionError:
                return

            dirs = [e for e in entries if e.is_dir() and e.name not in exclude_dirs]
            files = [e for e in entries if e.is_file()][:5]  # Limit files shown

            for i, d in enumerate(dirs):
                is_last = i == len(dirs) - 1 and not files
                connector = "└── " if is_last else "├── "
                lines.append(f"{prefix}{connector}{d.name}/")
                extension = "    " if is_last else "│   "
                walk_dir(d, prefix + extension, depth + 1)

        walk_dir(self.repo_path)
        return "\n".join(lines[:50])  # Limit output

    def get_package_json(self) -> Optional[dict]:
        """Get package.json content."""
        package_path = self.repo_path / "package.json"
        if package_path.exists():
            try:
                with open(package_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.error("failed_to_read_package_json", error=str(e))
        return None

    def get_recent_commits(self, limit: int = 10) -> list[CommitInfo]:
        """Get recent commits using git log."""
        try:
            result = subprocess.run(
                [
                    "git", "log",
                    f"-{limit}",
                    "--format=%H|%s|%an|%ad",
                    "--date=short",
                ],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode != 0:
                return []

            commits = []
            for line in result.stdout.strip().split("\n"):
                if not line:
                    continue
                parts = line.split("|", 3)
                if len(parts) >= 4:
                    commits.append(
                        CommitInfo(
                            sha=parts[0],
                            message=parts[1],
                            author=parts[2],
                            date=parts[3],
                            files_changed=[],
                        )
                    )
            return commits
        except Exception as e:
            logger.error("failed_to_get_commits", error=str(e))
            return []

    def get_commit_files(self, sha: str) -> list[str]:
        """Get files changed in a specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", "--name-only", "--format=", sha],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return [f for f in result.stdout.strip().split("\n") if f]
        except Exception:
            pass
        return []

    def get_commit_diff(self, sha: str, max_lines: int = 200) -> str:
        """Get diff content of a specific commit."""
        try:
            result = subprocess.run(
                ["git", "show", "--format=", "--patch", sha],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                diff_lines = result.stdout.strip().split("\n")
                if len(diff_lines) > max_lines:
                    truncated = "\n".join(diff_lines[:max_lines])
                    return f"{truncated}\n... (생략: 총 {len(diff_lines)}줄)"
                return result.stdout.strip()
        except Exception as e:
            logger.error("failed_to_get_commit_diff", sha=sha, error=str(e))
        return ""

    def read_file(self, rel_path: str) -> Optional[str]:
        """Read file content."""
        full_path = self.repo_path / rel_path
        if full_path.exists() and full_path.is_file():
            try:
                with open(full_path, encoding="utf-8") as f:
                    return f.read()
            except Exception as e:
                logger.error("failed_to_read_file", path=rel_path, error=str(e))
        return None

    def get_repo_context(self) -> RepoContext:
        """Get complete repository context for quiz generation."""
        return RepoContext(
            name=self.repo_name,
            path=str(self.repo_path),
            structure=self.get_directory_structure(),
            package_json=self.get_package_json(),
            recent_commits=self.get_recent_commits(5),
            sample_files=[f.path for f in self.get_source_files(limit=20)],
        )


# Singleton instance
local_repo = LocalRepoAnalyzer()
