from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from github import Github
from typing import List, Optional
from google import genai
from google.genai import types
import os
import json
import re
import time

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

github_client = Github(os.getenv("GITHUB_API_KEY"))

DATABASE_URL = "sqlite:///./reviews.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class ReviewRecord(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, index=True)
    pr_url = Column(String, index=True)
    summary = Column(Text)
    overall_severity = Column(String)
    approve = Column(Boolean)
    bugs_count = Column(Integer)
    style_issues_count = Column(Integer)
    suggestions_count = Column(Integer)
    full_review = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

Base.metadata.create_all(bind=engine)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "https://*.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    
def save_review(pr_url: str, review: ReviewResult):
    db = SessionLocal()
    try:
        record = ReviewRecord(
            pr_url=pr_url,
            summary=review.summary,
            overall_severity=review.overall_severity,
            approve=review.approve,
            bugs_count=len(review.bugs),
            style_issues_count=len(review.style_issues),
            suggestions_count=len(review.suggestions),
            full_review=json.dumps(review.model_dump())
        )
        db.add(record)
        db.commit()
        print(f"Saved review for {pr_url} to database")
    except Exception as e:
        print(f"Failed to save review: {e}")
        db.rollback()
    finally:
        db.close()
        
def get_pr_author_info(pr_url: str) -> dict:
    parts = pr_url.strip("/").split("/")
    owner = parts[-4]
    repo_name = parts[-3]
    pr_number = int(parts[-1])

    repo = github_client.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(pr_number)
    author = pr.user

    try:
        commits = repo.get_commits(author=author.login)
        commit_count = commits.totalCount
    except:
        commit_count = 0

    try:
        from github import Github
        g = Github(os.getenv("GITHUB_API_KEY"))
        issues = g.search_issues(
            f"repo:{owner}/{repo_name} is:pr author:{author.login}"
        )
        pr_count = issues.totalCount
    except:
        pr_count = 0

    account_age_days = (datetime.utcnow() - author.created_at.replace(tzinfo=None)).days
    account_age_years = round(account_age_days / 365, 1)

    is_maintainer = False
    try:
        permission = repo.get_collaborator_permission(author.login)
        is_maintainer = permission in ["admin", "write"]
    except:
        is_maintainer = False

    if is_maintainer:
        trust_level = "maintainer"
    elif commit_count > 10:
        trust_level = "contributor"
    elif commit_count > 0:
        trust_level = "occasional"
    else:
        trust_level = "first-timer"

    return {
        "username": author.login,
        "avatar_url": author.avatar_url,
        "profile_url": author.html_url,
        "name": author.name or author.login,
        "bio": author.bio or "",
        "account_age_years": account_age_years,
        "public_repos": author.public_repos,
        "followers": author.followers,
        "commit_count_to_repo": commit_count,
        "pr_count_to_repo": pr_count,
        "pr_title": pr.title,
        "pr_state": pr.state,
        "pr_commits": pr.commits,
        "pr_changed_files": pr.changed_files,
        "pr_additions": pr.additions,
        "pr_deletions": pr.deletions,
        "trust_level": trust_level
    }
    
def extract_pr_diff(pr_url: str):
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

    is_large_pr = pr.additions + pr.deletions > 500 or pr.changed_files > 10

    files = pr.get_files()
    for file in files:
        diff_text += f"File: {file.filename}\n"
        diff_text += f"Changes: +{file.additions} additions, -{file.deletions} deletions\n"

        if file.patch and not is_large_pr:
            patch_preview = file.patch[:300]
            if len(file.patch) > 300:
                patch_preview += "\n... [file diff truncated]"
            diff_text += f"Diff preview:\n{patch_preview}\n"

        diff_text += "\n---\n\n"

        if len(diff_text) > 3000:
            diff_text += "\n[Additional files truncated]"
            break

    return diff_text, is_large_pr

def build_review_prompt(diff: str, is_large_pr: bool = False) -> str:
    if is_large_pr:
        return f"""Analyze this large GitHub PR and return ONLY this JSON, no markdown, no code blocks:
{{"summary":"one short sentence max 50 words","bugs":[],"style_issues":[],"suggestions":[{{"file":"general","description":"one suggestion max 50 words"}}],"overall_severity":"low|medium|high|critical","approve":true}}

Keep every string field under 50 words. Return raw JSON only.

PR Info:
{diff}"""

    return f"""You are a code reviewer. Analyze this GitHub PR diff and return ONLY a JSON object, no markdown, no code blocks.

JSON structure:
{{"summary":"one sentence summary","bugs":[{{"file":"filename","line":null,"description":"bug description","severity":"low|medium|high|critical"}}],"style_issues":[{{"file":"filename","description":"issue"}}],"suggestions":[{{"file":"filename","description":"suggestion"}}],"overall_severity":"low|medium|high|critical","approve":true}}

Rules:
- Return ONLY raw JSON, nothing else
- Empty arrays [] if nothing found
- Filenames as plain text, no markdown links
- Keep all descriptions under 100 characters

PR Diff:
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
    response = client.models.generate_content(
    model="gemini-2.0-flash",
    contents=prompt,
    config=types.GenerateContentConfig(
        max_output_tokens=8192,
        temperature=0.1
    )
)
    return {"review": response.text}

@app.post("/review-pr")
def review_pr(request: PRReviewRequest):
    try:
        diff, is_large_pr = extract_pr_diff(request.pr_url)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch PR from GitHub. Error: {str(e)}"
        )

    prompt = build_review_prompt(diff, is_large_pr)

    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=8192,
                    temperature=0.1
                )
            )
            break
        except Exception as e:
            error_str = str(e)
            if "429" in error_str or "quota" in error_str.lower():
                if attempt < max_retries - 1:
                    wait_time = 60 * (attempt + 1)
                    print(f"Rate limited. Waiting {wait_time}s before retry {attempt + 2}/{max_retries}...")
                    time.sleep(wait_time)
                else:
                    raise HTTPException(
                        status_code=429,
                        detail="Gemini API rate limit reached. Please wait a few minutes and try again."
                    )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"Gemini API error: {error_str}"
                )

    if response.text.count('{') != response.text.count('}'):
        print("Response truncated, retrying with smaller diff...")
        diff = diff[:1000] + "\n[Diff truncated for retry]"
        prompt = build_review_prompt(diff, is_large_pr)
        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    max_output_tokens=8192,
                    temperature=0.1
                )
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Retry failed: {str(e)}")

    review = parse_review_response(response.text)
    save_review(request.pr_url, review)

    return {
        "pr_url": request.pr_url,
        "review": review.model_dump()
    }

@app.get("/stats")
def get_stats():
    db = SessionLocal()
    try:
        total_reviews = db.query(ReviewRecord).count()
        total_bugs = db.query(ReviewRecord).with_entities(
            ReviewRecord.bugs_count
        ).all()
        bugs_sum = sum(r.bugs_count for r in total_bugs)
        
        recent = db.query(ReviewRecord).order_by(
            ReviewRecord.created_at.desc()
        ).limit(10).all()
        
        return {
            "total_reviews": total_reviews,
            "total_bugs_found": bugs_sum,
            "recent_reviews": [
                {
                    "pr_url": r.pr_url,
                    "overall_severity": r.overall_severity,
                    "approve": r.approve,
                    "bugs_count": r.bugs_count,
                    "created_at": r.created_at.isoformat()
                }
                for r in recent
            ]
        }
    finally:
        db.close()
        
@app.get("/pr-author")
def get_pr_author(pr_url: str):
    try:
        author_info = get_pr_author_info(pr_url)
        return author_info
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Could not fetch PR author info. Error: {str(e)}"
        )