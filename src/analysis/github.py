"""GitHub API integration for repository analysis."""

import base64
from dataclasses import dataclass
from typing import Optional

import httpx
import structlog

from src.config import settings

logger = structlog.get_logger()

GITHUB_API_BASE = "https://api.github.com"


@dataclass
class FileInfo:
    """Information about a file in the repository."""

    path: str
    name: str
    type: str  # "file" or "dir"
    size: int
    sha: str


@dataclass
class CommitInfo:
    """Information about a commit."""

    sha: str
    message: str
    author: str
    date: str
    files_changed: list[str]


@dataclass
class RepoStructure:
    """Repository structure information."""

    files: list[FileInfo]
    package_json: Optional[dict] = None


class GitHubClient:
    """Client for interacting with GitHub API."""

    def __init__(self, token: Optional[str] = None, repo: Optional[str] = None):
        self.token = token or settings.github_token
        self.repo = repo or settings.github_repo
        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github.v3+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def get_repo_tree(self, path: str = "", recursive: bool = True) -> list[FileInfo]:
        """Get repository file tree."""
        async with httpx.AsyncClient() as client:
            # Get default branch
            repo_url = f"{GITHUB_API_BASE}/repos/{self.repo}"
            resp = await client.get(repo_url, headers=self.headers)
            resp.raise_for_status()
            default_branch = resp.json().get("default_branch", "main")

            # Get tree
            tree_url = f"{GITHUB_API_BASE}/repos/{self.repo}/git/trees/{default_branch}"
            if recursive:
                tree_url += "?recursive=1"

            resp = await client.get(tree_url, headers=self.headers)
            resp.raise_for_status()
            data = resp.json()

            files = []
            for item in data.get("tree", []):
                if path and not item["path"].startswith(path):
                    continue
                files.append(
                    FileInfo(
                        path=item["path"],
                        name=item["path"].split("/")[-1],
                        type="dir" if item["type"] == "tree" else "file",
                        size=item.get("size", 0),
                        sha=item["sha"],
                    )
                )
            return files

    async def get_file_content(self, path: str) -> Optional[str]:
        """Get content of a file."""
        async with httpx.AsyncClient() as client:
            url = f"{GITHUB_API_BASE}/repos/{self.repo}/contents/{path}"
            resp = await client.get(url, headers=self.headers)

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            data = resp.json()

            if data.get("encoding") == "base64":
                content = base64.b64decode(data["content"]).decode("utf-8")
                return content
            return None

    async def get_recent_commits(self, limit: int = 10) -> list[CommitInfo]:
        """Get recent commits."""
        async with httpx.AsyncClient() as client:
            url = f"{GITHUB_API_BASE}/repos/{self.repo}/commits"
            resp = await client.get(
                url,
                headers=self.headers,
                params={"per_page": limit},
            )
            resp.raise_for_status()
            data = resp.json()

            commits = []
            for item in data:
                commit = item["commit"]
                commits.append(
                    CommitInfo(
                        sha=item["sha"],
                        message=commit["message"],
                        author=commit["author"]["name"],
                        date=commit["author"]["date"],
                        files_changed=[],  # Would need another API call per commit
                    )
                )
            return commits

    async def get_commit_details(self, sha: str) -> Optional[CommitInfo]:
        """Get details of a specific commit including changed files."""
        async with httpx.AsyncClient() as client:
            url = f"{GITHUB_API_BASE}/repos/{self.repo}/commits/{sha}"
            resp = await client.get(url, headers=self.headers)

            if resp.status_code == 404:
                return None

            resp.raise_for_status()
            data = resp.json()

            commit = data["commit"]
            files_changed = [f["filename"] for f in data.get("files", [])]

            return CommitInfo(
                sha=data["sha"],
                message=commit["message"],
                author=commit["author"]["name"],
                date=commit["author"]["date"],
                files_changed=files_changed,
            )

    async def get_package_json(self) -> Optional[dict]:
        """Get package.json content."""
        import json

        content = await self.get_file_content("package.json")
        if content:
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.error("failed_to_parse_package_json")
        return None

    async def get_repo_structure(self) -> RepoStructure:
        """Get complete repository structure."""
        files = await self.get_repo_tree(recursive=True)
        package_json = await self.get_package_json()
        return RepoStructure(files=files, package_json=package_json)

    async def get_source_files(self, extensions: Optional[list[str]] = None) -> list[FileInfo]:
        """Get source files filtered by extensions."""
        if extensions is None:
            extensions = [".ts", ".tsx", ".js", ".jsx"]

        all_files = await self.get_repo_tree(recursive=True)
        return [f for f in all_files if f.type == "file" and any(f.name.endswith(ext) for ext in extensions)]


# Singleton instance
github_client = GitHubClient()
