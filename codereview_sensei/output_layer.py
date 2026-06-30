import datetime
from github import Github, GithubException
from config import GITHUB_TOKEN
from models import PRChunk, ReviewFinding

class GitHubOutputLayer:
    def verify_token_permissions(self) -> dict:
        """Verifies the GitHub token validity and checks rate limit."""
        if not GITHUB_TOKEN:
            return {"valid": False, "error": "No GITHUB_TOKEN found in environment."}
        try:
            g = Github(GITHUB_TOKEN)
            user = g.get_user()
            rl = g.get_rate_limit().core
            return {
                "valid": True,
                "username": user.login,
                "rate_limit_remaining": rl.remaining,
                "rate_limit_reset": rl.reset.isoformat() + "Z" if rl.reset else ""
            }
        except GithubException as e:
            return {"valid": False, "error": str(e)}

    def format_inline_comment(self, finding: ReviewFinding) -> str:
        """Formats a single finding as a clean inline comment body."""
        emojis = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
        emoji = emojis.get(finding.severity.lower(), "⚪")
        conf_percent = int(finding.confidence * 100)
        return (
            f"**{emoji} {finding.severity.upper()} — {finding.agent_name}**\n\n"
            f"{finding.issue}\n\n"
            f"💡 **Suggestion:** {finding.suggestion}\n\n"
            f"*Confidence: {conf_percent}% | CodeReview Sensei*"
        )

    def post_review(self, pr_chunk: PRChunk, github_markdown: str, event: str = "COMMENT") -> dict:
        """Posts the main review summary markdown to the PR."""
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(pr_chunk.repo_name)
            pull = repo.get_pull(pr_chunk.pr_number)
            review = pull.create_review(body=github_markdown, event=event)
            return {
                "success": True,
                "review_id": review.id,
                "review_url": f"https://github.com/{pr_chunk.repo_name}/pull/{pr_chunk.pr_number}#pullrequestreview-{review.id}",
                "posted_at": datetime.datetime.utcnow().isoformat() + "Z"
            }
        except GithubException as e:
            msg = e.data.get("message", str(e)) if e.data else str(e)
            return {"success": False, "error": f"GitHub API Error: {msg}"}

    def post_inline_comments(self, pr_chunk: PRChunk, findings: list[ReviewFinding]) -> dict:
        """Posts individual inline comments on the PR diff."""
        try:
            g = Github(GITHUB_TOKEN)
            repo = g.get_repo(pr_chunk.repo_name)
            pull = repo.get_pull(pr_chunk.pr_number)
            commit_sha = pull.get_commits().reversed[0].sha
            commit = repo.get_commit(commit_sha)
        except GithubException as e:
            return {"success": False, "error": f"Initialization failed: {e}"}

        posted, failed, reasons = 0, 0, []
        attempted = [f for f in findings if f.line_number is not None]
        for f in attempted:
            try:
                pull.create_review_comment(
                    body=self.format_inline_comment(f),
                    commit=commit,
                    path=f.filename,
                    line=f.line_number
                )
                posted += 1
            except GithubException as e:
                failed += 1
                msg = e.data.get("message", str(e)) if e.data else str(e)
                reasons.append(f"Line {f.line_number} in {f.filename}: {msg}")

        return {
            "success": True,
            "total_attempted": len(attempted),
            "total_posted": posted,
            "failed": failed,
            "failed_reasons": reasons
        }

    def run(self, pr_chunk: PRChunk, github_markdown: str, findings: list[ReviewFinding]) -> dict:
        """Orchestrates the token check and postings."""
        token_check = self.verify_token_permissions()
        if not token_check["valid"]:
            print(f"❌ Token Verification Failed: {token_check.get('error')}")
            return {"overall_success": False, "token_check": token_check}
        print(f"✅ GitHub token verified — logged in as {token_check['username']}")

        if token_check.get("rate_limit_remaining", 5000) < 100:
            print("⚠️ Warning: GitHub rate limit is extremely low (< 100 remaining).")

        print("📝 Posting review summary to PR...")
        review_post = self.post_review(pr_chunk, github_markdown)
        if review_post["success"]:
            print(f"✅ Review posted: {review_post['review_url']}")
        else:
            print(f"❌ Failed to post review: {review_post.get('error')}")

        print("💬 Posting inline comments...")
        inline_comments = self.post_inline_comments(pr_chunk, findings)
        print(f"✅ {inline_comments['total_posted']}/{inline_comments['total_attempted']} inline comments posted")

        return {
            "token_check": token_check,
            "review_post": review_post,
            "inline_comments": inline_comments,
            "overall_success": review_post["success"]
        }
