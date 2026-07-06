import json
import google.generativeai as genai
from config import GEMINI_API_KEY
from models import PRFile, ReviewFinding

class StyleReviewerAgent:
    def __init__(self) -> None:
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={"response_mime_type": "application/json"}
        )
        self.system_prompt = (
            "You are a code style and quality reviewer.\n"
            "Look ONLY for:\n"
            "- Poor naming (variables, functions, classes)\n"
            "- Missing or inadequate docstrings and comments\n"
            "- Overly complex functions (do one thing principle)\n"
            "- Dead code, unused imports, redundant logic\n"
            "- Functions that are too long (over 30 lines)\n"
            "Do NOT comment on bugs or security issues.\n"
            "Be constructive — suggest specific improvements."
        )

    def _build_prompt(self, files: list[PRFile]) -> str:
        """Constructs the prompt containing the file diffs."""
        files_text = ""
        for f in files:
            files_text += f"\nFile: {f.filename}\nStatus: {f.status}\nPatch:\n{f.patch}\n"
            
        return f"""SYSTEM: {self.system_prompt}

USER:
You are reviewing a GitHub Pull Request.

PR contains {len(files)} changed files.

For each file below, review the diff and return findings.

Return a JSON array of findings with this exact schema:
[
  {{
    "filename": "src/auth.py",
    "line_number": 42,
    "severity": "critical",
    "issue": "describe the issue clearly",
    "suggestion": "concrete fix",
    "confidence": 0.95
  }}
]

If you find no issues, return an empty array: []
Do NOT return anything except valid JSON.

--- FILES ---
{files_text}"""

    def _parse_findings(self, data: list) -> list[ReviewFinding]:
        """Parses the JSON data into a list of ReviewFinding models."""
        findings = []
        for item in data:
            findings.append(
                ReviewFinding(
                    agent_name="Style Reviewer",
                    filename=item.get("filename", ""),
                    line_number=item.get("line_number"),
                    severity=item.get("severity", "medium"),
                    issue=item.get("issue", ""),
                    suggestion=item.get("suggestion", ""),
                    confidence=float(item.get("confidence", 0.5))
                )
            )
        return findings

    def review(self, files: list[PRFile]) -> list[ReviewFinding]:
        """Reviews the list of PR files."""
        if not files:
            return []
        prompt = self._build_prompt(files)
        try:
            response = self.model.generate_content(prompt)
            data = json.loads(response.text)
            return self._parse_findings(data)
        except Exception as e:
            print(f"Error in Style Reviewer: {e}")
            return []
