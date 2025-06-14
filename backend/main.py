from fastapi import FastAPI, File, UploadFile, Form, Depends
from fastapi.middleware.cors import CORSMiddleware
import shutil
import os
from dotenv import load_dotenv
import google.generativeai as genai
from auth import router as auth_router
from fastapi import Query
from db import lifespan, get_db
from processing import extract_text, split_into_chunks, get_top_chunks, ask_llm

load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = FastAPI(lifespan=lifespan)
app.include_router(auth_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/upload/")
async def upload_pdf(file: UploadFile = File(...), db=Depends(get_db)):
    file_path = os.path.join(UPLOAD_FOLDER, file.filename)
    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)
    await db.uploads.insert_one({"filename": file.filename})
    return {"filename": file.filename}

@app.post("/ask/")
async def ask_question(
    filename: str = Form(...),
    query: str = Form(...),
    username: str = Form(...),  # NEW
    db=Depends(get_db)
):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    text = extract_text(file_path)
    chunks = split_into_chunks(text)
    top_chunks = get_top_chunks(chunks, query)
    context = "\n".join(top_chunks)
    answer = ask_llm(context, query)
    await db.questions.insert_one({
        "filename": filename,
        "query": query,
        "answer": answer,
        "username": username  # NEW
    })
    return {"answer": answer}

@app.get("/history/")
async def get_history(
    username: str = Query(...),
    db=Depends(get_db)
):
    # Fetch all questions for this user, most recent first
    cursor = db.questions.find({"username": username}).sort("_id", -1)
    history = []
    async for doc in cursor:
        history.append({
            "filename": doc.get("filename"),
            "question": doc.get("query"),
            "answer": doc.get("answer"),
            "timestamp": str(doc.get("_id"))  # You can add proper timestamps if you want
        })
    return {"history": history}