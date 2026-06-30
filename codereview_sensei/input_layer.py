import re
from github import Github, GithubException, UnknownObjectException
from config import GITHUB_TOKEN
from models import PRFile, PRChunk

class GitHubInputLayer:
    def parse_pr_url(self, pr_url: str) -> tuple[str, str, int]:
        """Parses PR URL of formats: pull/123 or pull/123/files."""
        pattern = r"https?://github\.com/([^/]+)/([^/]+)/pull/(\d+)"
        match = re.match(pattern, pr_url)
        if not match:
            raise ValueError(f"Invalid GitHub PR URL format: {pr_url}")
        owner, repo, pr_num = match.groups()
        return owner, f"{owner}/{repo}", int(pr_num)

    def _get_client(self) -> Github:
        """Returns initialized Github client."""
        return Github(GITHUB_TOKEN) if GITHUB_TOKEN else Github()

    def _extract_files(self, pr) -> list[PRFile]:
        """Extracts valid non-binary, non-empty files from the PR."""
        files = []
        for file in pr.get_files():
            if not file.patch:
                continue
            # Skip common binary/asset/lock files
            ignored_exts = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".lock"}
            if any(file.filename.endswith(ext) for ext in ignored_exts):
                continue
            files.append(
                PRFile(
                    filename=file.filename,
                    status=file.status,
                    patch=file.patch,
                    additions=file.additions,
                    deletions=file.deletions,
                )
            )
        return files

    def fetch_pr(self, pr_url: str) -> PRChunk:
        """Fetches and parses PR metadata and files."""
        owner, repo_name, pr_number = self.parse_pr_url(pr_url)
        g = self._get_client()
        try:
            repo = g.get_repo(repo_name)
            pr = repo.get_pull(pr_number)
            files = self._extract_files(pr)
            return PRChunk(
                pr_url=pr_url,
                pr_title=pr.title,
                pr_number=pr_number,
                repo_name=repo_name,
                files=files,
                total_files_changed=len(files),
            )
        except UnknownObjectException as e:
            msg = f"PR #{pr_number} or Repo '{repo_name}' not found."
            if not GITHUB_TOKEN:
                msg += " Ensure GITHUB_TOKEN is set in your .env if it is private."
            raise RuntimeError(msg) from e
        except GithubException as e:
            status_code = getattr(e, "status", None)
            if status_code == 401:
                raise RuntimeError("Invalid GITHUB_TOKEN provided. Please check your credentials.") from e
            elif status_code == 403:
                raise RuntimeError("API rate limit exceeded or access forbidden. Check token permissions.") from e
            err_msg = e.data.get("message", str(e)) if hasattr(e, "data") and e.data else str(e)
            raise RuntimeError(f"GitHub API Error: {err_msg}") from e

    def chunk_by_file(self, pr_chunk: PRChunk) -> list[PRFile]:
        """Returns the list of files and prints a summary."""
        filenames = [f.filename for f in pr_chunk.files]
        print(f"Found {len(pr_chunk.files)} files changed: {filenames}")
        return pr_chunk.files
