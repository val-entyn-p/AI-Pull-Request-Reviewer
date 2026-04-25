from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from github import Github
from typing import List, Optional
import google.generativeai as genai
import os
import json
import re

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config=genai.GenerationConfig(
        max_output_tokens=4096,
        temperature=0.1
    )
)
github_client = Github(os.getenv("GITHUB_API_KEY"))

app = FastAPI()

class ReviewRequest(BaseModel):
    code: str
    
class PRReviewRequest(BaseModel):
    pr_url: str
    
class BugReport(BaseModel):
    file: str
    line: Optional[int] = None
    description: str
    severity: str
    
class StyleIssue(BaseModel):
    file: str
    description: str
    
class Suggestion(BaseModel):
    file: str
    description: str
    
class ReviewResult(BaseModel):
    summary: str
    bugs: List[BugReport]
    style_issues: List[StyleIssue]
    suggestions: List[Suggestion]
    overall_severity: str
    approve: bool
    
def extract_pr_diff(pr_url: str) -> str:
    parts = pr_url.strip("/").split("/")
    owner = parts[-4]
    repo_name = parts[-3]
    pr_number = int(parts[-1])

    print(f"Fetching: owner={owner}, repo={repo_name}, pr={pr_number}") # repo info

    repo = github_client.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(pr_number)

    diff_text = f"PR Title: {pr.title}\n"
    diff_text += f"PR Description: {pr.body}\n\n"

    files = pr.get_files()
    for file in files:
        diff_text += f"File: {file.filename}\n"
        diff_text += f"Changes: +{file.additions} additions, -{file.deletions} deletions\n"
        if file.patch:
            diff_text += f"Diff:\n{file.patch}\n"
        diff_text += "\n---\n\n"

        # Stop if diff is getting too large
        if len(diff_text) > 4000:
            diff_text += "\n[Diff truncated — too large for single review]"
            break

    return diff_text

def build_review_prompt(diff: str) -> str:
    return f"""You are an expert code reviewer. Analyze this GitHub pull request diff and return a structured review.

    IMPORTANT: Return ONLY a valid JSON object. No markdown, no explanation, no code blocks. Just raw JSON.

The JSON must follow this exact structure:
{{
  "summary": "2-3 sentence overview of what this PR does and its quality",
  "bugs": [
    {{
      "file": "filename where bug exists",
      "line": null or line number if identifiable,
      "description": "clear description of the bug",
      "severity": "low|medium|high|critical"
    }}
  ],
  "style_issues": [
    {{
      "file": "filename",
      "description": "description of the style issue"
    }}
  ],
  "suggestions": [
    {{
      "file": "filename",
      "description": "suggested improvement"
    }}
  ],
  "overall_severity": "low|medium|high|critical",
  "approve": true or false
}}

Rules:
- severity must be exactly one of: low, medium, high, critical
- overall_severity must be exactly one of: low, medium, high, critical
- approve should be true only if the PR is safe to merge as-is
- ALWAYS use empty arrays [] for bugs, style_issues, and suggestions if there are none. Never leave them blank or null.
- File names must be plain text only. Never use markdown links. Write exactly: tests/test_path.py
- Do NOT use markdown of any kind inside JSON string values
- No backticks, no bold, no hyperlinks inside any JSON value

CRITICAL: Your response must be pure JSON only.
- Write ALL filenames using underscores instead of dots. Example: tests/test_path_py instead of tests/test_path.py
- Do NOT use markdown of any kind inside JSON string values
- Do NOT convert filenames into hyperlinks
- ALWAYS use empty arrays [] never leave array fields blank

Pull Request Diff:
{diff}"""

def parse_review_response(response_text: str) -> ReviewResult:
    # Strip markdown links aggressively  
    response_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', response_text)
    response_text = re.sub(r'\[([^\]]*)\]', r'\1', response_text)
    
    # Fix empty array fields
    response_text = re.sub(r':\s*,', ': [],', response_text)
    response_text = re.sub(r':\s*\n\s*}', ': []\n}', response_text)

    cleaned = response_text.strip()

    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\n?', '', cleaned)
        cleaned = re.sub(r'\n?```$', '', cleaned)

    try:
        data = json.loads(cleaned)
        
        # Convert filenames back: test_path_py → test_path.py
        # Find the last underscore before a known extension and replace with dot
        def fix_filename(filename: str) -> str:
            for ext in ['_py', '_js', '_ts', '_go', '_java', '_rb', '_md', '_yml', '_yaml', '_json']:
                if filename.endswith(ext):
                    return filename[:-len(ext)] + ext.replace('_', '.')
            return filename

        for bug in data.get('bugs', []):
            bug['file'] = fix_filename(bug.get('file', ''))
        for issue in data.get('style_issues', []):
            issue['file'] = fix_filename(issue.get('file', ''))
        for suggestion in data.get('suggestions', []):
            suggestion['file'] = fix_filename(suggestion.get('file', ''))

        return ReviewResult(**data)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Gemini returned invalid JSON: {str(e)}. Raw response: {response_text[:200]}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Response validation failed: {str(e)}"
        )

@app.get("/")
def root():
    return {"status": "AI Code Reviewer is running"}

@app.post("/review")
def review_code(request: ReviewRequest):
    prompt = f"Review this code for bugs and issues:\n\n{request.code}"
    response = model.generate_content(prompt)
    return {"review": response.text}

@app.post("/review-pr")
def review_pr(request: PRReviewRequest):
    diff = extract_pr_diff(request.pr_url)
    prompt = build_review_prompt(diff)
    
    # First attempt
    response = model.generate_content(prompt)
    
    # If response looks truncated, try again with even smaller diff
    if len(response.text) < 200 or response.text.count('{') != response.text.count('}'):
        print("Response looks truncated, retrying with smaller diff...")
        diff = diff[:2000] + "\n[Diff truncated for retry]"
        prompt = build_review_prompt(diff)
        response = model.generate_content(prompt)
    
    review = parse_review_response(response.text)
    return {
        "pr_url": request.pr_url,
        "review": review.model_dump()
    }