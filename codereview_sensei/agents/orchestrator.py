import asyncio
from models import PRFile
from agents.bug_hunter import BugHunterAgent
from agents.security_auditor import SecurityAuditorAgent
from agents.style_reviewer import StyleReviewerAgent
from agents.style_learner import StyleLearnerAgent

class OrchestratorAgent:
    def __init__(self) -> None:
        self.bug_hunter = BugHunterAgent()
        self.security_auditor = SecurityAuditorAgent()
        self.style_reviewer = StyleReviewerAgent()
        self.style_learner = StyleLearnerAgent()

    async def run_all(self, files: list[PRFile]) -> dict:
        """Executes all sub-agents in parallel using threads."""
        async def run_bh():
            res = await asyncio.to_thread(self.bug_hunter.review, files)
            print(f"✅ Bug Hunter complete — {len(res)} findings")
            return res

        async def run_sa():
            res = await asyncio.to_thread(self.security_auditor.review, files)
            print(f"✅ Security Auditor complete — {len(res)} findings")
            return res

        async def run_sr():
            res = await asyncio.to_thread(self.style_reviewer.review, files)
            print(f"✅ Style Reviewer complete — {len(res)} findings")
            return res

        async def run_sl():
            res = await asyncio.to_thread(self.style_learner.review, files)
            print(f"✅ Style Learner complete — {len(res)} findings")
            return res

        results = await asyncio.gather(run_bh(), run_sa(), run_sr(), run_sl())
        return {
            "bug_hunter": results[0],
            "security_auditor": results[1],
            "style_reviewer": results[2],
            "style_learner": results[3]
        }
