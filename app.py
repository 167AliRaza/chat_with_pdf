import asyncio
import logging
import os
import time
import uuid
from contextlib import asynccontextmanager
from cachetools import LRUCache
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from langchain.indexes import VectorstoreIndexCreator
from langchain.memory import ConversationBufferWindowMemory
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pydantic import BaseModel
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

# Config & startup

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY environment variable is not set.")

MAX_FILE_SIZE_MB = 20
SESSION_TTL_SECONDS = 60 * 60
CLEANUP_INTERVAL_SECONDS = 15 * 60

# Rate limiter

def get_real_ip(request: Request) -> str:
    forwarded_for = request.headers.get("X-Forwarded-For")

    if forwarded_for:
        real_ip = forwarded_for.split(",")[0].strip()
        print(f"[IP DEBUG] From X-Forwarded-For header: {real_ip}")
        return real_ip

    fallback_ip = request.client.host
    print(f"[IP DEBUG] From fallback (request.client.host): {fallback_ip}")
    return fallback_ip


limiter = Limiter(key_func=get_real_ip)

llm = GoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    google_api_key=GEMINI_API_KEY,
)

embedding = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    google_api_key=GEMINI_API_KEY,
)

# Session store

user_sessions: LRUCache = LRUCache(maxsize=50)
session_lock = asyncio.Lock()

# Background cleanup

async def cleanup_expired_sessions() -> None:
    while True:
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
        now = time.time()

        async with session_lock:
            expired = [
                sid for sid, data in user_sessions.items()
                if now - data["created_at"] > SESSION_TTL_SECONDS
            ]
            for sid in expired:
                del user_sessions[sid]
                logger.info(f"Evicted expired session: {sid}")

        if expired:
            logger.info(
                f"Cleanup swept {len(expired)} expired session(s). "
                f"Active sessions: {len(user_sessions)}"
            )

# Lifespan

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(cleanup_expired_sessions())
    logger.info("Background session cleanup task started.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        logger.info("Background cleanup task stopped cleanly.")

# App

app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Schemas

class ChatRequest(BaseModel):
    session_id: str
    query: str

# Helpers

def is_valid_pdf(file_path: str) -> bool:
    try:
        with open(file_path, "rb") as f:
            return f.read(4) == b"%PDF"
    except OSError as e:
        logger.warning(f"Could not validate PDF at {file_path}: {e}")
        return False


async def get_session(session_id: str) -> dict:
    async with session_lock:
        session = user_sessions.get(session_id)

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Session not found. Please re-upload your PDF.",
        )

    if time.time() - session["created_at"] > SESSION_TTL_SECONDS:
        async with session_lock:
            user_sessions.pop(session_id, None)
        raise HTTPException(
            status_code=410,
            detail="Session expired after 1 hour. Please re-upload your PDF.",
        )

    return session

# Routes

@app.get("/")
async def root():
    return {
        "message": "Server is running",
        "active_sessions": len(user_sessions),
    }


@app.post("/upload-pdf/")
@limiter.limit("3/hour")          # 3 uploads per IP per hour
async def upload_pdf(request: Request, file: UploadFile = File(...)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF.")

    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {MAX_FILE_SIZE_MB} MB.",
        )

    session_id = str(uuid.uuid4())
    temp_file_path = f"/tmp/{session_id}.pdf"

    try:
        with open(temp_file_path, "wb") as buffer:
            buffer.write(contents)

        if not is_valid_pdf(temp_file_path):
            raise HTTPException(status_code=400, detail="Invalid PDF file content.")

        loader = PyPDFLoader(temp_file_path)
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=1000,
            chunk_overlap=200,
            add_start_index=True,
        )
        index_creator = VectorstoreIndexCreator(
            embedding=embedding,
            text_splitter=text_splitter,
        )
        store = index_creator.from_loaders([loader])

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process PDF for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process the PDF.")
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

    async with session_lock:
        user_sessions[session_id] = {
            "store": store,
            "memory": ConversationBufferWindowMemory(k=5),
            "created_at": time.time(),
        }

    logger.info(f"Session created: {session_id}")
    return JSONResponse(content={
        "message": "PDF uploaded and indexed successfully.",
        "session_id": session_id,
    })


@app.post("/chat/")
@limiter.limit("30/minute")       # 30 messages per IP per minute
async def chat_with_pdf(request: Request, request_body: ChatRequest):
    session = await get_session(request_body.session_id)
    store = session["store"]
    memory = session["memory"]

    history = memory.load_memory_variables({}).get("history", "")
    augmented_query = (
        f"Conversation so far:\n{history}\n\nUser question: {request_body.query}"
        if history
        else request_body.query
    )

    try:
        response = store.query(augmented_query, llm=llm)
    except Exception as e:
        logger.error(f"LLM query failed for session {request_body.session_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get a response from the model.")

    memory.save_context({"input": request_body.query}, {"output": response})

    return {"response": response}