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
import time

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel(
    "gemini-2.5-flash",
    generation_config=genai.GenerationConfig(
        max_output_tokens=8192,
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

    print(f"Fetching: owner={owner}, repo={repo_name}, pr={pr_number}")

    repo = github_client.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(pr_number)

    diff_text = f"PR Title: {pr.title}\n"
    diff_text += f"PR Description: {pr.body or 'No description provided'}\n\n"
    diff_text += f"Files changed: {pr.changed_files}\n"
    diff_text += f"Total additions: {pr.additions}\n"
    diff_text += f"Total deletions: {pr.deletions}\n\n"

    files = pr.get_files()
    for file in files:
        diff_text += f"File: {file.filename}\n"
        diff_text += f"Changes: +{file.additions} additions, -{file.deletions} deletions\n"
        
        if file.patch:
            # Only take first 500 chars of each file's diff
            patch_preview = file.patch[:500]
            if len(file.patch) > 500:
                patch_preview += "\n... [file diff truncated]"
            diff_text += f"Diff preview:\n{patch_preview}\n"
        
        diff_text += "\n---\n\n"

        # Stop at 5000 chars total
        if len(diff_text) > 5000:
            diff_text += "\n[Additional files truncated]"
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
    response_text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', response_text)
    response_text = re.sub(r'\[([^\]]*)\]', r'\1', response_text)

    #Strip code blocks FIRST before anything else
    cleaned = response_text.strip()
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = cleaned.strip()

    cleaned = re.sub(r':\s*,', ': [],', cleaned)
    cleaned = re.sub(r':\s*\n\s*}', ': []\n}', cleaned)

    #Fix truncated JSON
    open_braces = cleaned.count('{')
    close_braces = cleaned.count('}')
    open_brackets = cleaned.count('[')
    close_brackets = cleaned.count(']')

    if open_braces != close_braces or open_brackets != close_brackets:
        print("WARNING: JSON appears truncated. Fixing...")

        lines = cleaned.split('\n')
        while lines:
            last_line = lines[-1].strip()
            if not any(last_line.endswith(c) for c in ['}', ']', '"', 'true', 'false', 'null']):
                lines.pop()
            else:
                break
        cleaned = '\n'.join(lines)

        cleaned = cleaned.rstrip().rstrip(',')

        while cleaned.count('[') > cleaned.count(']'):
            cleaned += ']'
        while cleaned.count('{') > cleaned.count('}'):
            cleaned += '}'

    try:
        data = json.loads(cleaned)

        if isinstance(data, str):
            print("WARNING: Double encoded JSON detected, parsing again...")
            data = json.loads(data)

        if not isinstance(data, dict):
            raise HTTPException(
                status_code=500,
                detail=f"Expected JSON object but got {type(data).__name__}. Raw response: {response_text[:200]}"
            )

        for field in ['bugs', 'style_issues', 'suggestions']:
            if isinstance(data.get(field), dict):
                data[field] = [data[field]]
            elif data.get(field) is None:
                data[field] = []

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
    
    try:
        diff = extract_pr_diff(request.pr_url)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch from GitHub. Make sure the URL is correct and the PR is public. Error: {str(e)}"
        )
        
    prompt = build_review_prompt(diff)
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = model.generate_content(prompt)
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                if attempt < max_retries -1:
                    wait_time = 60 * (attempt + +1)
                    print(f"rate limited. Waiting {wait_time} seconds before retry {attempt +2}/{max_retries}...")
                    time.sleept(wait_time)
                else:
                    raise HTTPException(
                        status_code=429,
                        detail="Gemini API rate limit reached. Please wait a few minutes and try again."
                    )
    if response.text.count("{") != response.text.count("}"):
        print("Response looks truncated, retrying with smaller diff...")
        diff = diff[:2000] + "\n[Diff truncated for retry]"
        promt = build_review_prompt(diff)
        try:
            response = model.generate_content(promt)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Retry failed: {str(e)}"
            )
    
    review = parse_review_response(response.text)
    return {
        "pr_url": request.pr_url,
        "review": review.model_dump()
    }