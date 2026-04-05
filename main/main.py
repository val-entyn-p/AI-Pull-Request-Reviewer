from fastapi import FastAPI
from pydantic import BaseModel
from dotenv import load_dotenv
import os

load_dotenv()

app = FastAPI()

class ReviewRequest(BaseModel):
    code: str
    
@app.get("/")
def roo():
    return {"status": "AI Code Reviewer is running"}

@app.post("/review")
def review_code(request: ReviewRequest):
    return {
        "recieve_code": request.code,
        "message": "hello_world"
    }