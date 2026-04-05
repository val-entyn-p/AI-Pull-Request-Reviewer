from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
from pathlib import Path
import google.generativeai as genai
import os

load_dotenv(dotenv_path=Path(__file__).resolve().parent.parent / ".env")

genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.5-flash")

app = FastAPI()

class ReviewRequest(BaseModel):
    code: str
    
@app.get("/")
def root():
    return {"status": "AI Code Reviewer is running"}

@app.post("/review")
def review_code(request: ReviewRequest):
    prompt = f"Review this code for bugs and issues:\n\n{request.code}"
    
    response = model.generate_content(prompt)
    
    return {
        "review": response.text
    }