import os
import asyncio
import gradio as gr
from config import GITHUB_TOKEN
from models import PRChunk, ReviewFinding
from input_layer import GitHubInputLayer
from agents.orchestrator import OrchestratorAgent
from merger import ReviewMerger
from output_layer import GitHubOutputLayer

# Initialize Layers
input_layer = GitHubInputLayer()
merger = ReviewMerger()
output_layer = GitHubOutputLayer()

def format_severity_color(severity: str) -> str:
    return {
        "critical": "#ff4444",
        "high": "#ff8800",
        "medium": "#ffcc00",
        "low": "#00cc66"
    }.get(severity.lower(), "#a6adc8")

def build_summary_html(summary: dict) -> str:
    if not summary:
        return ""
    risk = summary["overall_risk"]
    risk_colors = {"HIGH RISK": "#ff4444", "MEDIUM RISK": "#ff8800", "LOW RISK": "#ffcc00", "LOOKS GOOD": "#00cc66"}
    risk_color = risk_colors.get(risk, "#8b949e")
    
    file_info = ""
    if summary.get("most_problematic_file"):
        file_info = f'<div style="color:#8b949e; font-size:13px; text-align:right;">📁 Most issues: <code style="background:#0d1117; padding:4px 8px; border-radius:4px; border:1px solid #30363d; color:#58a6ff;">{summary["most_problematic_file"]}</code></div>'
        
    html = f"""
    <div style="background:#161b22; border: 1px solid #30363d; border-radius:12px; padding:24px; font-family:'Inter', sans-serif; color:#cdd6f4;">
        <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:24px; flex-wrap:wrap; gap:12px;">
            <div>
                <div style="font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; font-weight:600;">Status & Risk Level</div>
                <div style="background:{risk_color}1a; color:{risk_color}; border: 1px solid {risk_color}; border-radius:8px; padding:6px 14px; display:inline-block; font-weight:700; font-size:13px; text-transform:uppercase; letter-spacing:0.5px; box-shadow: 0 0 10px {risk_color}1a;">
                    {risk}
                </div>
            </div>
            {file_info}
        </div>
        
        <div style="display:grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap:12px; margin-bottom:24px;">
    """
    
    metrics = [
        ("Total", summary["total"], "#58a6ff"),
        ("Critical", summary["critical"], "#ff4444"),
        ("High", summary["high"], "#ff8800"),
        ("Medium", summary["medium"], "#ffcc00"),
        ("Low", summary["low"], "#00cc66")
    ]
    for label, count, color in metrics:
        html += f"""
            <div class="metric-card" style="background:#0d1117; border: 1px solid #30363d; border-radius:8px; padding:16px; text-align:center; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
                <div style="font-size:28px; font-weight:700; color:{color};">{count}</div>
                <div style="font-size:12px; color:#8b949e; margin-top:4px; font-weight:500;">{label}</div>
            </div>
        """
        
    html += """
        </div>
        <div style="border-top:1px solid #30363d; padding-top:20px;">
            <div style="font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; margin-bottom:12px; font-weight:600;">Agent Breakdown</div>
            <div style="display:flex; flex-wrap:wrap; gap:20px; font-size:13px;">
    """
    for agent, count in summary["by_agent"].items():
        icon = {"Bug Hunter": "🐛", "Security Auditor": "🔒", "Style Reviewer": "✨", "Style Learner": "🧠"}.get(agent, "🤖")
        html += f"""
            <div style="display:flex; align-items:center; gap:6px; background:#0d1117; border: 1px solid #30363d; border-radius:6px; padding:6px 12px;">
                <span>{icon}</span>
                <span style="color:#8b949e;">{agent}:</span>
                <span style="font-weight:600; color:#58a6ff;">{count}</span>
            </div>
        """
    html += "</div></div></div>"
    return html

def build_findings_html(findings: list, agent_filter: str = None) -> str:
    if not findings:
        return "<div style='text-align:center; padding:30px; color:#8b949e; background:#161b22; border:1px solid #30363d; border-radius:10px; font-family:sans-serif;'>No findings found.</div>"
    
    filtered = findings
    if agent_filter:
        filtered = [f for f in findings if f["agent"] == agent_filter]
        if not filtered:
            return f"<div style='text-align:center; padding:30px; color:#8b949e; background:#161b22; border:1px solid #30363d; border-radius:10px; font-family:sans-serif;'>No findings from {agent_filter}.</div>"
            
    html = '<div style="font-family:\'Inter\', sans-serif; max-height: 550px; overflow-y: auto; padding-right: 4px;">'
    for f in filtered:
        col = format_severity_color(f["severity"])
        emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(f["severity"].lower(), "⚪")
        line_str = f" · Line <b>{f['line_number']}</b>" if f["line_number"] is not None else ""
        conf_percent = int(f["confidence"] * 100)
        
        html += f"""
        <div class="finding-card" style="background:#161b22; border: 1px solid #30363d; border-left: 4px solid {col}; border-radius:10px; padding:20px; margin-bottom:16px; position:relative;">
            <div style="display:flex; justify-content:space-between; align-items:flex-start; margin-bottom:14px; gap:12px;">
                <div style="display:flex; align-items:center; gap:8px; flex-wrap:wrap;">
                    <span style="background:{col}1a; color:{col}; border: 1px solid {col}; border-radius:6px; padding:3px 10px; font-size:11px; font-weight:700; text-transform:uppercase; letter-spacing:0.5px;">
                        {emoji} {f['severity'].upper()}
                    </span>
                    <span style="color:#8b949e; font-size:12px;">in <code>{f['filename']}</code>{line_str}</span>
                </div>
                <span style="color:#a371f7; background:#a371f712; border: 1px solid #a371f722; padding:3px 8px; border-radius:6px; font-size:11px; font-weight:600;">{f['agent']}</span>
            </div>
            
            <div style="color:#cdd6f4; font-size:14px; line-height:1.5; margin-bottom:16px;">{f['issue']}</div>
            
            <div style="background:#0d1117; border: 1px solid #30363d; border-radius:8px; padding:12px 16px; font-size:13px; color:#a6e3a1; line-height:1.5;">
                <div style="font-size:10px; color:#8b949e; text-transform:uppercase; letter-spacing:1px; margin-bottom:6px; font-weight:600;">Suggested Fix</div>
                <div style="font-family:'JetBrains Mono', monospace; white-space: pre-wrap;">💡 {f['suggestion']}</div>
            </div>
            
            <div style="display:flex; align-items:center; gap:8px; margin-top:16px; font-size:11px; color:#8b949e;">
                <span>Confidence:</span>
                <div style="width:100px; background:#30363d; height:6px; border-radius:3px; overflow:hidden; display:inline-block; vertical-align:middle;">
                    <div style="width:{conf_percent}%; background:{col}; height:100%;"></div>
                </div>
                <span style="font-weight:600; color:{col};">{conf_percent}%</span>
            </div>
        </div>
        """
    html += "</div>"
    return html

async def review_pr(pr_url: str):
    pr_url = pr_url.strip()
    if not pr_url:
        yield ("❌ Error: PR URL cannot be empty.", "", *[""]*5, "", None, "", None, None)
        return
        
    log = "🔄 Fetching PR from GitHub...\n"
    yield (log, "", *[""]*5, "", None, "", None, None)
    
    try:
        pr_chunk = input_layer.fetch_pr(pr_url)
        log += f"✅ PR fetched: \"{pr_chunk.pr_title}\" (#{pr_chunk.pr_number}) — {pr_chunk.total_files_changed} files changed\n\n"
        log += "🤖 Dispatching sub-agents in parallel...\n"
        log += "  ⚙️  Bug Hunter       → running\n"
        log += "  ⚙️  Security Auditor → running\n"
        log += "  ⚙️  Style Reviewer   → running\n"
        log += "  ⚙️  Style Learner    → running\n"
        yield (log, "", *[""]*5, "", None, "", None, None)
        
        orchestrator = OrchestratorAgent()
        results = await orchestrator.run_all(pr_chunk.files)
        
        log += f"\n  ✅ Bug Hunter       → {len(results['bug_hunter'])} findings\n"
        log += f"  ✅ Security Auditor → {len(results['security_auditor'])} findings\n"
        log += f"  ✅ Style Reviewer   → {len(results['style_reviewer'])} findings\n"
        log += f"  ✅ Style Learner    → {len(results['style_learner'])} findings\n\n"
        log += "🔄 Merging and deduplicating findings...\n"
        yield (log, "", *[""]*5, "", None, "", None, None)
        
        github_md, ui_dict, ranked = merger.run(results, pr_chunk)
        log += f"✅ Merger complete — {len(ranked)} findings after dedup\n\n"
        log += "📋 Review ready."
        
        summary_html = build_summary_html(ui_dict["summary"])
        all_h = build_findings_html(ui_dict["findings"])
        bh_h = build_findings_html(ui_dict["findings"], "Bug Hunter")
        sa_h = build_findings_html(ui_dict["findings"], "Security Auditor")
        sr_h = build_findings_html(ui_dict["findings"], "Style Reviewer")
        sl_h = build_findings_html(ui_dict["findings"], "Style Learner")
        
        yield (log, summary_html, all_h, bh_h, sa_h, sr_h, sl_h, github_md, pr_chunk, github_md, ranked, ui_dict)
        
    except Exception as e:
        log += f"\n❌ Error: {str(e)}"
        yield (log, "", *[""]*5, "", None, "", None, None)

def post_to_github(pr_chunk, github_md, findings):
    if not pr_chunk or not github_md:
        return "❌ Error: No review data found. Please run the PR review first."
    
    try:
        output_layer = GitHubOutputLayer()
        res = output_layer.run(pr_chunk, github_md, findings or [])
        if res.get("overall_success", False):
            url = res.get("review_post", {}).get("review_url", "")
            return f"✅ Review posted successfully! View at: {url}"
        else:
            err = res.get("token_check", {}).get("error") or res.get("review_post", {}).get("error") or "Unknown error"
            return f"❌ Failed to post: {err}"
    except Exception as e:
        return f"❌ Failed to post: {str(e)}"

def clear_all():
    return ("", "", *[""]*5, "", None, "", None, None, "")

css_code = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

.gradio-container {
    font-family: 'Inter', -apple-system, sans-serif !important;
}

.metric-card {
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}
.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(88, 166, 255, 0.15) !important;
    border-color: #58a6ff !important;
}

.finding-card {
    transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}
.finding-card:hover {
    transform: translateX(4px);
    background-color: #1f242c !important;
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2) !important;
}

#status-log textarea {
    font-family: 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    background-color: #05070a !important;
    border-left: 4px solid #a371f7 !important;
}
"""

with gr.Blocks(
    title="CodeReview Sensei",
    theme=gr.themes.Soft(primary_hue="purple", secondary_hue="blue", neutral_hue="slate"),
    css=css_code,
    js="() => document.body.classList.add('dark')"
) as demo:
    gr.HTML("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h1 style="color: #f5c2e7; margin-bottom: 0;">🤖 CodeReview Sensei</h1>
        <h3 style="color: #cdd6f4; margin-top: 5px; font-weight: normal;">AI-Powered Multi-Agent Pull Request Reviewer</h3>
        <hr style="border-color: #313244; margin: 20px 0;">
    </div>
    """)
    
    with gr.Row():
        url_input = gr.Textbox(
            label="GitHub PR URL",
            placeholder="https://github.com/owner/repo/pull/123",
            scale=4
        )
        review_btn = gr.Button("🔍 Review PR", variant="primary", scale=1)
        
    status_log = gr.Textbox(
        label="Live Agent Status Log",
        lines=8,
        interactive=False,
        elem_id="status-log"
    )
    
    gr.HTML("<h3>📊 Review Summary</h3>")
    summary_output = gr.HTML(value="<div style='text-align:center; padding:20px; color:#a6adc8; background:#1e1e2e; border-radius:12px;'>Summary will be generated once review is run.</div>")
    
    gr.HTML("<h3>🔍 Review Findings</h3>")
    with gr.Tabs():
        with gr.Tab("🔍 All"):
            tab_all = gr.HTML(value="<div style='text-align:center; padding:20px; color:#a6adc8; background:#1e1e2e; border-radius:10px;'>Run the review to view findings.</div>")
        with gr.Tab("🐛 Bug Hunter"):
            tab_bh = gr.HTML(value="<div style='text-align:center; padding:20px; color:#a6adc8; background:#1e1e2e; border-radius:10px;'>No findings.</div>")
        with gr.Tab("🔒 Security Auditor"):
            tab_sa = gr.HTML(value="<div style='text-align:center; padding:20px; color:#a6adc8; background:#1e1e2e; border-radius:10px;'>No findings.</div>")
        with gr.Tab("✨ Style Reviewer"):
            tab_sr = gr.HTML(value="<div style='text-align:center; padding:20px; color:#a6adc8; background:#1e1e2e; border-radius:10px;'>No findings.</div>")
        with gr.Tab("🧠 Style Learner"):
            tab_sl = gr.HTML(value="<div style='text-align:center; padding:20px; color:#a6adc8; background:#1e1e2e; border-radius:10px;'>No findings.</div>")
            
    gr.HTML("<h3>📄 GitHub Comment Body Preview</h3>")
    github_preview = gr.Markdown(value="Markdown preview will be displayed here.")
    
    with gr.Row():
        post_btn = gr.Button("📤 Post to GitHub", variant="primary")
        clear_btn = gr.Button("🗑️ Clear", variant="secondary")
        
    post_status = gr.Textbox(label="Post Status", interactive=False, placeholder="Status of posting to GitHub...")
    
    state_pr_chunk = gr.State()
    state_github_markdown = gr.State()
    state_ranked_findings = gr.State()
    state_ui_dict = gr.State()
    
    review_btn.click(
        fn=review_pr,
        inputs=[url_input],
        outputs=[
            status_log, summary_output, tab_all, tab_bh, tab_sa, tab_sr, tab_sl,
            github_preview, state_pr_chunk, state_github_markdown, state_ranked_findings, state_ui_dict
        ]
    )
    
    post_btn.click(
        fn=post_to_github,
        inputs=[state_pr_chunk, state_github_markdown, state_ranked_findings],
        outputs=[post_status]
    )
    
    clear_btn.click(
        fn=clear_all,
        outputs=[
            status_log, summary_output, tab_all, tab_bh, tab_sa, tab_sr, tab_sl,
            github_preview, state_pr_chunk, state_github_markdown, state_ranked_findings, state_ui_dict, post_status
        ]
    )

if __name__ == "__main__":
    is_hf_space = os.getenv("SPACE_ID") is not None
    demo.launch(
        share=not is_hf_space,
        debug=True,
        show_error=True
    )
