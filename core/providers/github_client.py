"""
GitHub API client for repository data extraction.
Logic-only, no Qt. Thread-safe.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from logger import log

DEFAULT_GITHUB_API = "https://api.github.com"


@dataclass(frozen=True)
class GitHubError(Exception):
    message: str
    status_code: Optional[int] = None
    detail: Optional[str] = None

    def __str__(self) -> str:
        bits = [self.message]
        if self.status_code is not None:
            bits.append(f"(status={self.status_code})")
        if self.detail:
            bits.append(self.detail)
        return " ".join(bits)


def _auth_headers(token: str = "") -> Dict[str, str]:
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    tok = (token or "").strip()
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    return headers


def _parse_json_response(resp) -> Any:
    try:
        return resp.json()
    except Exception:
        text = getattr(resp, "text", "") or ""
        raise GitHubError("Failed to parse JSON.", status_code=getattr(resp, "status_code", None), detail=text[:500])


def _raise_for_status(resp) -> None:
    if 200 <= int(resp.status_code) < 300:
        return
    status = int(resp.status_code)
    detail = None
    try:
        data = _parse_json_response(resp)
        if isinstance(data, dict) and "message" in data:
            detail = str(data.get("message") or "")
    except Exception:
        pass
    if not detail:
        detail = (getattr(resp, "text", "") or "")[:500]
    msgs = {
        401: "Authentication failed.",
        403: "Access denied or rate limit exceeded.",
        404: "Repository not found.",
        400: f"Bad request: {detail}",
    }
    raise GitHubError(msgs.get(status, "GitHub API request failed."), status_code=status, detail=detail)


def parse_github_url(url: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse a GitHub URL to extract owner and repo name. Returns (owner, repo) or (None, None)."""
    url = (url or "").strip()
    if not url:
        return None, None
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^github\.com/', '', url)
    url = re.sub(r'\.git$', '', url)
    url = url.rstrip('/')
    parts = url.split('/')
    if len(parts) >= 2:
        owner, repo = parts[0].strip(), parts[1].strip()
        if owner and repo:
            return owner, repo
    return None, None


def get_repo_info(owner: str, repo: str, token: str = "", base_url: str = DEFAULT_GITHUB_API, timeout_seconds: float = 30.0) -> Dict[str, Any]:
    """Fetch repository metadata from GitHub API."""
    owner, repo = (owner or "").strip(), (repo or "").strip()
    if not owner or not repo:
        raise GitHubError("Owner and repo are required.")
    import requests
    url = f"{base_url}/repos/{owner}/{repo}"
    try:
        resp = requests.get(url, headers=_auth_headers(token), timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise GitHubError(f"GitHub API request failed: {exc}") from exc
    _raise_for_status(resp)
    data = _parse_json_response(resp)
    if not isinstance(data, dict):
        raise GitHubError("Unexpected response.", status_code=int(resp.status_code))
    return data


def get_readme(owner: str, repo: str, token: str = "", base_url: str = DEFAULT_GITHUB_API, timeout_seconds: float = 30.0) -> str:
    """Fetch README content (markdown) from GitHub API."""
    owner, repo = (owner or "").strip(), (repo or "").strip()
    if not owner or not repo:
        raise GitHubError("Owner and repo are required.")
    import requests
    url = f"{base_url}/repos/{owner}/{repo}/readme"
    headers = _auth_headers(token)
    headers["Accept"] = "application/vnd.github.raw+json"
    try:
        resp = requests.get(url, headers=headers, timeout=float(timeout_seconds))
    except requests.RequestException as exc:
        raise GitHubError(f"GitHub API request failed: {exc}") from exc
    _raise_for_status(resp)
    return resp.text


def get_repo_data_from_url(repo_url: str, token: str = "", base_url: str = DEFAULT_GITHUB_API, timeout_seconds: float = 30.0) -> Dict[str, Any]:
    """Convenience: parse URL and fetch all repo data. Returns {repo_info, readme, owner, repo}."""
    owner, repo = parse_github_url(repo_url)
    if not owner or not repo:
        raise GitHubError(f"Could not parse GitHub URL: {repo_url}", detail="Expected: github.com/owner/repo")
    repo_info = get_repo_info(owner, repo, token, base_url, timeout_seconds)
    readme = ""
    try:
        readme = get_readme(owner, repo, token, base_url, timeout_seconds)
    except GitHubError as e:
        if e.status_code == 404:
            log.warning("README not found for %s/%s", owner, repo)
        else:
            raise
    return {"repo_info": repo_info, "readme": readme, "owner": owner, "repo": repo}
