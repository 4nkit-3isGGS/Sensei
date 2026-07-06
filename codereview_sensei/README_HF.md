---
title: CodeReview Sensei
emoji: 🤖
colorFrom: purple
colorTo: blue
sdk: gradio
sdk_version: 5.34.2
app_file: app.py
pinned: false
license: mit
---

# 🤖 CodeReview Sensei

AI-Powered Multi-Agent Pull Request Reviewer built with Gradio and Google Gemini.

## Setup

This Space requires the following **Secrets** to be configured in the Space settings:

| Secret Name | Description |
|---|---|
| `GITHUB_TOKEN` | GitHub Personal Access Token with repo access |
| `GEMINI_API_KEY` | Google Gemini API Key |

## How to Use

1. Paste a GitHub Pull Request URL
2. Click "Review PR"
3. View the AI-generated code review findings
4. Optionally post the review as a comment on the PR
