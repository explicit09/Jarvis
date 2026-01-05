"""GitHub integration tools (read-only) using GitHub REST API v3."""

from __future__ import annotations

import base64
import logging
from typing import Optional

import httpx
from livekit.agents import llm

from jarvis.audit import append_event
from jarvis.config import config

logger = logging.getLogger(__name__)


def _is_allowed_repo(full_name: str, confirm: bool) -> tuple[bool, str]:
    full_name = full_name.strip()
    if not full_name or "/" not in full_name:
        return False, "Repo must be in the form 'owner/name'."

    allowed_repos = {r.lower() for r in config.github.allowed_repos}
    allowed_owners = {o.lower() for o in config.github.allowed_owners}

    owner = full_name.split("/", 1)[0].lower()

    if allowed_repos and full_name.lower() in allowed_repos:
        return True, ""
    if allowed_owners and owner in allowed_owners:
        return True, ""

    if config.safety.require_confirmation and not confirm:
        return (
            False,
            "Confirmation required for GitHub access outside allowlist. Re-run with confirm=true.",
        )

    return True, ""


def _ensure_token() -> Optional[str]:
    token = config.github.token
    if not token:
        return None
    return token


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "JARVIS",
    }


async def _get(url: str, token: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
        response = await client.get(url, headers=_headers(token), params=params)
        response.raise_for_status()
        return response.json()


@llm.function_tool
async def github_list_repos(limit: int = 30) -> str:
    """List the authenticated user's repositories."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    append_event({"type": "github", "action": "list_repos"})

    limit = max(1, min(100, limit))
    data = await _get("https://api.github.com/user/repos", token, params={"per_page": str(limit)})
    if not data:
        return "No repos found."

    lines = []
    for repo in data:
        full_name = repo.get("full_name", "")
        private = repo.get("private", False)
        stars = repo.get("stargazers_count", 0)
        lines.append(f"{full_name} ({'private' if private else 'public'}) ⭐ {stars}")
    return "Repos:\n" + "\n".join(lines)


@llm.function_tool
async def github_get_repo(repo: str, confirm: bool = False) -> str:
    """Get repo metadata (stars, forks, description, default branch)."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    allowed, message = _is_allowed_repo(repo, confirm)
    if not allowed:
        return message

    append_event({"type": "github", "action": "get_repo", "repo": repo})

    data = await _get(f"https://api.github.com/repos/{repo}", token)
    return (
        f"{data.get('full_name')}\n"
        f"Description: {data.get('description') or ''}\n"
        f"Default branch: {data.get('default_branch')}\n"
        f"Stars: {data.get('stargazers_count')}  Forks: {data.get('forks_count')}\n"
        f"Private: {data.get('private')}"
    )


@llm.function_tool
async def github_list_files(
    repo: str,
    path: str = "",
    ref: str = "",
    limit: int = 100,
    confirm: bool = False,
) -> str:
    """List files in a repository path."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    allowed, message = _is_allowed_repo(repo, confirm)
    if not allowed:
        return message

    append_event({"type": "github", "action": "list_files", "repo": repo, "path": path})

    limit = max(1, min(500, limit))
    url = f"https://api.github.com/repos/{repo}/contents/{path.lstrip('/')}"
    params = {"ref": ref} if ref.strip() else None
    data = await _get(url, token, params=params)

    if isinstance(data, dict) and data.get("type") == "file":
        return f"{path} is a file."

    if not isinstance(data, list):
        return "Unexpected response from GitHub."

    entries = data[:limit]
    lines = []
    for item in entries:
        name = item.get("name", "")
        kind = item.get("type", "")
        lines.append(f"{name}{'/' if kind == 'dir' else ''}")
    return "Files:\n" + "\n".join(lines)


@llm.function_tool
async def github_read_file(
    repo: str,
    path: str,
    ref: str = "",
    max_chars: int = 4000,
    confirm: bool = False,
) -> str:
    """Read a file from a GitHub repository."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    allowed, message = _is_allowed_repo(repo, confirm)
    if not allowed:
        return message

    append_event({"type": "github", "action": "read_file", "repo": repo, "path": path})

    url = f"https://api.github.com/repos/{repo}/contents/{path.lstrip('/')}"
    params = {"ref": ref} if ref.strip() else None
    data = await _get(url, token, params=params)
    if data.get("type") != "file":
        return "Path is not a file."

    content = data.get("content", "")
    encoding = data.get("encoding", "")
    if encoding != "base64":
        return "Unsupported file encoding from GitHub."

    raw = base64.b64decode(content.encode("utf-8"))
    text = raw.decode("utf-8", errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + "\n... [truncated]"
    return text


@llm.function_tool
async def github_search_code(
    query: str,
    limit: int = 10,
    confirm: bool = False,
) -> str:
    """Search code across GitHub (uses GitHub Search API)."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    if config.safety.require_confirmation and not confirm:
        return "Confirmation required for GitHub code search. Re-run with confirm=true."

    append_event({"type": "github", "action": "search_code"})

    limit = max(1, min(50, limit))
    params = {"q": query, "per_page": str(limit)}
    data = await _get("https://api.github.com/search/code", token, params=params)
    items = data.get("items", [])
    if not items:
        return "No matches found."

    lines = []
    for item in items:
        repo = item.get("repository", {}).get("full_name", "")
        path = item.get("path", "")
        html_url = item.get("html_url", "")
        lines.append(f"{repo}:{path}\n{html_url}")
    return "Matches:\n" + "\n".join(lines)


@llm.function_tool
async def github_list_issues(
    repo: str,
    state: str = "open",
    limit: int = 10,
    confirm: bool = False,
) -> str:
    """List issues for a repository."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    allowed, message = _is_allowed_repo(repo, confirm)
    if not allowed:
        return message

    append_event({"type": "github", "action": "list_issues", "repo": repo})

    state = state.strip().lower() or "open"
    if state not in {"open", "closed", "all"}:
        state = "open"
    limit = max(1, min(50, limit))

    params = {"state": state, "per_page": str(limit)}
    data = await _get(f"https://api.github.com/repos/{repo}/issues", token, params=params)
    if not data:
        return "No issues found."

    lines = []
    for issue in data:
        if issue.get("pull_request"):
            continue
        number = issue.get("number")
        title = issue.get("title", "")
        url = issue.get("html_url", "")
        lines.append(f"#{number} {title}\n{url}")
    return "Issues:\n" + "\n".join(lines) if lines else "No issues found."


@llm.function_tool
async def github_list_prs(
    repo: str,
    state: str = "open",
    limit: int = 10,
    confirm: bool = False,
) -> str:
    """List pull requests for a repository."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    allowed, message = _is_allowed_repo(repo, confirm)
    if not allowed:
        return message

    append_event({"type": "github", "action": "list_prs", "repo": repo})

    state = state.strip().lower() or "open"
    if state not in {"open", "closed", "all"}:
        state = "open"
    limit = max(1, min(50, limit))

    params = {"state": state, "per_page": str(limit)}
    data = await _get(f"https://api.github.com/repos/{repo}/pulls", token, params=params)
    if not data:
        return "No pull requests found."

    lines = []
    for pr in data:
        number = pr.get("number")
        title = pr.get("title", "")
        url = pr.get("html_url", "")
        lines.append(f"#{number} {title}\n{url}")
    return "PRs:\n" + "\n".join(lines)


@llm.function_tool
async def github_get_commit_history(
    repo: str,
    branch: str = "",
    limit: int = 10,
    confirm: bool = False,
) -> str:
    """Get recent commits for a repo/branch."""
    token = _ensure_token()
    if not token:
        return "GITHUB_TOKEN not configured."

    allowed, message = _is_allowed_repo(repo, confirm)
    if not allowed:
        return message

    append_event({"type": "github", "action": "commit_history", "repo": repo})

    limit = max(1, min(50, limit))
    params = {"per_page": str(limit)}
    if branch.strip():
        params["sha"] = branch.strip()

    data = await _get(f"https://api.github.com/repos/{repo}/commits", token, params=params)
    if not data:
        return "No commits found."

    lines = []
    for item in data:
        sha = item.get("sha", "")[:7]
        message = item.get("commit", {}).get("message", "").splitlines()[0]
        url = item.get("html_url", "")
        lines.append(f"{sha} {message}\n{url}")
    return "Commits:\n" + "\n".join(lines)


def get_github_tools() -> list:
    """Get GitHub tools."""
    return [
        github_list_repos,
        github_get_repo,
        github_list_files,
        github_read_file,
        github_search_code,
        github_list_issues,
        github_list_prs,
        github_get_commit_history,
    ]
