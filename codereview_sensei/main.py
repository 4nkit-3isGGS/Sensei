import sys
import asyncio

# Reconfigure stdout/stderr to support UTF-8 emojis on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

from input_layer import GitHubInputLayer
from agents.orchestrator import OrchestratorAgent
from merger import ReviewMerger
from output_layer import GitHubOutputLayer

def main() -> None:
    print("Welcome to CodeReview Sensei")
    try:
        pr_url = input("Please enter a GitHub PR URL: ").strip()
        if not pr_url:
            print("❌ Error: PR URL cannot be empty.")
            return

        input_layer = GitHubInputLayer()
        pr_chunk = input_layer.fetch_pr(pr_url)

        print(f"\n  ✅ PR Fetched: \"{pr_chunk.pr_title}\" (#{pr_chunk.pr_number})")
        print(f"  📁 Repo: {pr_chunk.repo_name}")
        print(f"  🔍 Files changed: {pr_chunk.total_files_changed}\n")

        # Chunk files
        files = input_layer.chunk_by_file(pr_chunk)

        # Run Phase 2: Sub-Agents Layer
        print("\n🚀 Running Phase 2: Analyzing pull request with 4 parallel agents...")
        orchestrator = OrchestratorAgent()
        results = asyncio.run(orchestrator.run_all(files))

        # Run Phase 3: Merger and Formatter
        print("\n🚀 Running Phase 3: Merging, deduplicating, and formatting findings...")
        merger = ReviewMerger()
        github_md, ui_dict, ranked = merger.run(results, pr_chunk)

        print("\n====================== UI DICT SUMMARY =======================")
        import json
        print(json.dumps(ui_dict["summary"], indent=2))
        print("==============================================================")

        print("\n  ✅ Phase 3 complete. Report generated successfully.")

        # Run Phase 4: Output Layer
        post_choice = input("\nPost this review to GitHub? (yes/no): ").strip().lower()
        if post_choice in ["y", "yes"]:
            print("\n🚀 Running Phase 4: Posting review back to GitHub PR...")
            output = GitHubOutputLayer()
            res = output.run(pr_chunk, github_md, ranked)
            print("\n=================== POSTING RESULT SUMMARY ===================")
            print(f"  Overall Success: {res.get('overall_success', False)}")
            if "inline_comments" in res:
                ic = res["inline_comments"]
                print(f"  Inline Comments: {ic.get('total_posted', 0)}/{ic.get('total_attempted', 0)} posted")
                if ic.get("failed", 0) > 0:
                    print(f"  Failed Comments: {ic['failed']}")
                    for reason in ic.get("failed_reasons", []):
                        print(f"    - {reason}")
            print("==============================================================")
        else:
            print("\nReview saved locally — skipping GitHub post.")
            print("\n=================== GITHUB MARKDOWN OUTPUT ===================")
            print(github_md)
            print("==============================================================")

        print("\n  ✅ Phase 4 complete.")


    except Exception as e:
        print(f"\n❌ Error: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
