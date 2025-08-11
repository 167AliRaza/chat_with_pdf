from langchain_community.document_loaders import PyPDFLoader
from langchain.indexes import VectorstoreIndexCreator
from langchain.text_splitter import CharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from langchain.memory import ConversationBufferMemory
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import shutil, os, uuid
from dotenv import load_dotenv
class ChatRequest(BaseModel):
    session_id: str
    query: str

load_dotenv()

llm = GoogleGenerativeAI(
    model="gemini-1.5-flash", 
    google_api_key=os.getenv("GEMINI_API_KEY")
)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # You can restrict to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for all users
user_sessions = {}  # { session_id: { "store": index, "memory": ConversationBufferMemory } }

def is_valid_pdf(file_path: str) -> bool:
    try:
        with open(file_path, 'rb') as f:
            return f.read(4) == b'%PDF'
    except:
        return False


@app.get("/")
async def root():
    return {"message": "Server is running"}

@app.post("/upload-pdf/")
async def upload_pdf(file: UploadFile = File(...)):
    # Create a unique session for this user
    session_id = str(uuid.uuid4())

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="File must be a PDF")

    temp_file_path = os.path.join("/tmp", file.filename)
    with open(temp_file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    if not is_valid_pdf(temp_file_path):
        os.remove(temp_file_path)
        raise HTTPException(status_code=400, detail="Invalid PDF file")

    loader = PyPDFLoader(temp_file_path)
    embedding = GoogleGenerativeAIEmbeddings(
        model="models/embedding-001", 
        google_api_key=os.getenv("GEMINI_API_KEY")
    )
    text_splitter = CharacterTextSplitter(chunk_size=500, chunk_overlap=100)

    index_creator = VectorstoreIndexCreator(
        embedding=embedding, 
        text_splitter=text_splitter
    )
    store = index_creator.from_loaders([loader])

    os.remove(temp_file_path)  # cleanup

    # Save store & memory for this session
    user_sessions[session_id] = {
        "store": store,
        "memory": ConversationBufferMemory(max_turns=5)
    }

    return JSONResponse(content={
        "message": "PDF uploaded and indexed successfully",
        "session_id": session_id
    })

@app.post("/chat/")
async def chat_with_pdf(request: ChatRequest):
    session_id = request.session_id
    query = request.query

    # Check if session exists
    if session_id not in user_sessions:
        raise HTTPException(status_code=404, detail="Session not found. Please upload a PDF first.")

    store = user_sessions[session_id]["store"]
    memory = user_sessions[session_id]["memory"]

    response = store.query(query, llm=llm, memory=memory)
    return {"response": response}