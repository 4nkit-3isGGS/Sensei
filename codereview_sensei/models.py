from pydantic import BaseModel

class PRFile(BaseModel):
    filename: str
    status: str        # "added" | "modified" | "deleted"
    patch: str         # the raw diff/patch text
    additions: int
    deletions: int

class PRChunk(BaseModel):
    pr_url: str
    pr_title: str
    pr_number: int
    repo_name: str
    files: list[PRFile]
    total_files_changed: int

class ReviewFinding(BaseModel):
    agent_name: str
    filename: str
    line_number: int | None
    severity: str
    issue: str
    suggestion: str
    confidence: float

class ReviewSummary(BaseModel):
    total_findings: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    findings_by_agent: dict[str, int]
    most_problematic_file: str
    overall_risk: str


