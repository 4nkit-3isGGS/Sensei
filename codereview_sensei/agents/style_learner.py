import os
import json
import datetime
import google.generativeai as genai
from config import GEMINI_API_KEY
from models import PRFile, ReviewFinding

class StyleLearnerAgent:
    def __init__(self) -> None:
        genai.configure(api_key=GEMINI_API_KEY)
        self.model = genai.GenerativeModel("gemini-2.5-flash", generation_config={"response_mime_type": "application/json"})
        self.memory_path = os.path.join(os.path.dirname(__file__), "..", "memory", "team_style_memory.json")
        os.makedirs(os.path.dirname(self.memory_path), exist_ok=True)

    def _load_memory(self) -> dict:
        if os.path.exists(self.memory_path):
            try:
                with open(self.memory_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict) and "patterns" in data:
                        return data
            except Exception:
                pass
        return {"patterns": [], "last_updated": ""}

    def _save_memory(self, memory: dict) -> None:
        try:
            memory["last_updated"] = datetime.datetime.utcnow().isoformat()
            with open(self.memory_path, "w", encoding="utf-8") as f:
                json.dump(memory, f, indent=2)
        except Exception as e:
            print(f"Error saving style memory: {e}")

    def _update_patterns(self, memory: dict, new_patterns: list) -> None:
        patterns = memory.setdefault("patterns", [])
        for np in new_patterns:
            desc = np.get("description", "").strip()
            if not desc:
                continue
            matched = False
            for p in patterns:
                if p.get("description", "").strip().lower() == desc.lower():
                    p["occurrences"] = p.get("occurrences", 0) + 1
                    matched = True
                    break
            if not matched:
                patterns.append({
                    "id": f"p{len(patterns) + 1:03d}",
                    "description": desc,
                    "example": np.get("example", ""),
                    "language": np.get("language", "python"),
                    "occurrences": 1
                })

    def _build_prompt(self, files: list[PRFile], patterns_str: str) -> str:
        files_text = "".join(f"\nFile: {f.filename}\nPatch:\n{f.patch}\n" for f in files)
        return f"""SYSTEM: You are a team style consistency agent. Review deviations from memory and find new patterns.
USER: KNOWN TEAM PATTERNS:\n{patterns_str}\nFILES:\n{files_text}
Response schema:
{{
  "findings": [
    {{
      "filename": "src/auth.py",
      "line_number": 42,
      "severity": "medium",
      "issue": "deviation from pattern",
      "suggestion": "concrete fix alignment",
      "confidence": 0.90
    }}
  ],
  "new_patterns": [
    {{
      "description": "observed consistent pattern",
      "example": "example of pattern code",
      "language": "python"
    }}
  ]
}}"""

    def _parse_findings(self, data: dict) -> list[ReviewFinding]:
        return [
            ReviewFinding(
                agent_name="Style Learner",
                filename=item.get("filename", ""),
                line_number=item.get("line_number"),
                severity=item.get("severity", "medium"),
                issue=item.get("issue", ""),
                suggestion=item.get("suggestion", ""),
                confidence=float(item.get("confidence", 0.5))
            )
            for item in data.get("findings", [])
        ]

    def review(self, files: list[PRFile]) -> list[ReviewFinding]:
        if not files:
            return []
        mem = self._load_memory()
        prompt = self._build_prompt(files, json.dumps(mem.get("patterns", []), indent=2))
        try:
            res = self.model.generate_content(prompt)
            data = json.loads(res.text)
            self._update_patterns(mem, data.get("new_patterns", []))
            self._save_memory(mem)
            return self._parse_findings(data)
        except Exception as e:
            print(f"Error in Style Learner: {e}")
            return []
