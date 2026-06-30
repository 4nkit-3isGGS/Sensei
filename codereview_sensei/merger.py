import re
from models import PRChunk, ReviewFinding, ReviewSummary

class ReviewMerger:
    def _lines_overlap(self, l1: int | None, l2: int | None) -> bool:
        if l1 is None and l2 is None:
            return True
        if l1 is not None and l2 is not None:
            return abs(l1 - l2) <= 2
        return False

    def _keyword_similarity(self, desc1: str, desc2: str) -> float:
        def get_words(s: str) -> set[str]:
            words = re.findall(r"\w+", s.lower())
            stop = {"the", "a", "an", "is", "are", "in", "on", "to", "for", "of", "and", "or", "with", "by", "at", "from"}
            return {w for w in words if w not in stop}
        
        words1, words2 = get_words(desc1), get_words(desc2)
        if not words1 or not words2:
            return 0.0
        return len(words1.intersection(words2)) / len(words1.union(words2))

    def _select_better(self, f1: ReviewFinding, f2: ReviewFinding) -> ReviewFinding:
        sev_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        s1 = sev_map.get(f1.severity.lower(), 0)
        s2 = sev_map.get(f2.severity.lower(), 0)
        if s1 != s2:
            return f1 if s1 > s2 else f2
        if f1.confidence != f2.confidence:
            return f1 if f1.confidence > f2.confidence else f2
        agent_map = {"Bug Hunter": 4, "Security Auditor": 3, "Style Reviewer": 2, "Style Learner": 1}
        a1 = agent_map.get(f1.agent_name, 0)
        a2 = agent_map.get(f2.agent_name, 0)
        return f1 if a1 >= a2 else f2

    def deduplicate(self, all_findings: dict) -> list[ReviewFinding]:
        flattened = [f for lst in all_findings.values() for f in lst]
        kept: list[ReviewFinding] = []
        for f in flattened:
            dup_idx = -1
            for idx, existing in enumerate(kept):
                if (existing.filename == f.filename and 
                    self._lines_overlap(existing.line_number, f.line_number) and 
                    self._keyword_similarity(existing.issue, f.issue) >= 0.25):
                    dup_idx = idx
                    break
            if dup_idx != -1:
                kept[dup_idx] = self._select_better(kept[dup_idx], f)
            else:
                kept.append(f)
        return kept

    def rank(self, findings: list[ReviewFinding]) -> list[ReviewFinding]:
        sev_map = {"critical": 4, "high": 3, "medium": 2, "low": 1}
        agent_map = {"Bug Hunter": 4, "Security Auditor": 3, "Style Reviewer": 2, "Style Learner": 1}
        return sorted(findings, key=lambda f: (
            -sev_map.get(f.severity.lower(), 0),
            -f.confidence,
            -agent_map.get(f.agent_name, 0)
        ))

    def generate_summary(self, findings: list[ReviewFinding]) -> ReviewSummary:
        crit = sum(1 for f in findings if f.severity.lower() == "critical")
        high = sum(1 for f in findings if f.severity.lower() == "high")
        med = sum(1 for f in findings if f.severity.lower() == "medium")
        low = sum(1 for f in findings if f.severity.lower() == "low")
        
        by_agent = {"Bug Hunter": 0, "Security Auditor": 0, "Style Reviewer": 0, "Style Learner": 0}
        for f in findings:
            by_agent[f.agent_name] = by_agent.get(f.agent_name, 0) + 1
            
        file_counts = {}
        for f in findings:
            file_counts[f.filename] = file_counts.get(f.filename, 0) + 1
        most_prob = max(file_counts, key=file_counts.get) if file_counts else ""
        
        risk = "LOOKS GOOD" if not findings else ("HIGH RISK" if crit > 0 else ("MEDIUM RISK" if high > 0 else "LOW RISK"))
        return ReviewSummary(
            total_findings=len(findings), critical_count=crit, high_count=high,
            medium_count=med, low_count=low, findings_by_agent=by_agent,
            most_problematic_file=most_prob, overall_risk=risk
        )

    def format_for_github(self, findings: list[ReviewFinding], summary: ReviewSummary, pr_chunk: PRChunk) -> str:
        emojis = {"HIGH RISK": "🔴", "MEDIUM RISK": "🟠", "LOW RISK": "🟡", "LOOKS GOOD": "🟢"}
        risk_emoji = emojis.get(summary.overall_risk, "⚪")
        md = f"## 🤖 CodeReview Sensei Report\n\n"
        md += f"**PR:** {pr_chunk.pr_title} (#{pr_chunk.pr_number})\n"
        md += f"**Repo:** {pr_chunk.repo_name}\n"
        md += f"**Risk level:** {risk_emoji} {summary.overall_risk}\n\n---\n\n"
        md += f"### 📊 Summary\n| Metric | Count |\n|---|---|\n"
        md += f"| Total findings | {summary.total_findings} |\n"
        md += f"| 🔴 Critical | {summary.critical_count} |\n| 🟠 High | {summary.high_count} |\n"
        md += f"| 🟡 Medium | {summary.medium_count} |\n| 🟢 Low | {summary.low_count} |\n\n"
        if summary.most_problematic_file:
            md += f"**Most issues in:** `{summary.most_problematic_file}`\n\n"
        md += "**By agent:**\n"
        for ag, cnt in summary.findings_by_agent.items():
            icon = {"Bug Hunter": "🐛", "Security Auditor": "🔒", "Style Reviewer": "✨", "Style Learner": "🧠"}.get(ag, "🤖")
            md += f"- {icon} {ag}: {cnt}\n"
        md += "\n---\n\n### 🔍 Findings\n\n"
        if not findings:
            md += "No issues found — looks clean! ✅\n\n"
        else:
            sev_emojis = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
            for f in findings:
                emoji = sev_emojis.get(f.severity.lower(), "⚪")
                line_str = f"line {f.line_number}" if f.line_number else "Global"
                md += f"#### {emoji} [{f.severity.upper()}] {f.agent_name} — `{f.filename}` {line_str}\n"
                md += f"**Issue:** {f.issue}\n**Suggestion:** {f.suggestion}\n"
                md += f"**Confidence:** {int(f.confidence * 100)}%\n\n---\n\n"
        md += "*Generated by CodeReview Sensei — Kaggle × Google Gen AI Capstone*\n"
        return md

    def format_for_ui(self, findings: list[ReviewFinding], summary: ReviewSummary) -> dict:
        return {
            "summary": {
                "total": summary.total_findings,
                "critical": summary.critical_count,
                "high": summary.high_count,
                "medium": summary.medium_count,
                "low": summary.low_count,
                "overall_risk": summary.overall_risk,
                "most_problematic_file": summary.most_problematic_file,
                "by_agent": summary.findings_by_agent
            },
            "findings": [
                {
                    "agent": f.agent_name, "filename": f.filename, "line_number": f.line_number,
                    "severity": f.severity, "issue": f.issue, "suggestion": f.suggestion,
                    "confidence": f.confidence
                } for f in findings
            ]
        }

    def run(self, all_agent_findings: dict, pr_chunk: PRChunk) -> tuple[str, dict, list[ReviewFinding]]:
        print("🔄 Deduplicating findings...")
        before = sum(len(lst) for lst in all_agent_findings.values())
        deduped = self.deduplicate(all_agent_findings)
        print(f"📊 Total before dedup: {before}  |  After dedup: {len(deduped)}")
        print("🏆 Ranking by severity...")
        ranked = self.rank(deduped)
        summary = self.generate_summary(ranked)
        github_md = self.format_for_github(ranked, summary, pr_chunk)
        ui_dict = self.format_for_ui(ranked, summary)
        print(f"✅ Merger complete — {len(ranked)} findings ready")
        return github_md, ui_dict, ranked

