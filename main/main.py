from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
from github import Github
import google.generativeai as genai
import os

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")
github_client = Github(os.getenv("GITHUB_API_KEY"))

app = FastAPI()

class ReviewRequest(BaseModel):
    code: str
    
class PRReviewRequest(BaseModel):
    pr_url: str
    
def extract_pr_diff(pr_url: str) -> str:
    
    parts = pr_url.strip("/").split("/")
    owner = parts[-4]
    repo_name = parts[-3]
    pr_number = int(parts[-1])
    
    repo = github_client.get_repo(f"{owner}/{repo_name}")
    pr = repo.get_pull(pr_number)
    
    diff_text = f"PR Title: {pr.title}\n"
    diff_text += f"PR Description: {pr.body}\n\n"
    
    files = pr.get_files()
    for file in files:
        diff_text += f"file: {file.filename}\n"
        diff_text += f"Changes: +{file.additions} additions, - {file.deletions} deletions\n"
        if file.patch:
            diff_text += f"Diff:\n{file.patch}\n"
        diff_text += "\n---\n\n"
        
    return diff_text

@app.get("/")
def root():
    return {"status": "AI Code Reviewer is running"}

@app.post("/review-pr")
def review_pr(request: PRReviewRequest):
    
    diff = extract_pr_diff(request.pr_url)
    
    prompt = f"Review This GitHub pull request for bugs, issues, and improvements:\n\n{diff}"
    response = model.generate_content(prompt)
    
    return {
        "pr_url": request.pr_url,
        "review": response.text
    }