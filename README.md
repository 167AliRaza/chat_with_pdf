---
title: Rag Application
emoji: 🐠
colorFrom: gray
colorTo: blue
sdk: docker
pinned: false
---

# PDF Chatbot API

This project is a FastAPI-based application that allows users to upload PDF files, extract their content, and interact with the content through a conversational interface powered by Google Generative AI. The application supports session-based interactions, where users can upload a PDF, receive a unique session ID, and then query the content of the PDF using natural language.

## Frontend
The frontend for this application is available at: [https://chatwithpdf-aliraza.netlify.app/](https://chatwithpdf-aliraza.netlify.app/)

## Features
- **PDF Upload**: Upload PDF files and validate their format.
- **Text Extraction and Indexing**: Extract text from PDFs and persist a FAISS index on disk for fast reuse.
- **Conversational Interface**: Query the PDF content using natural language, with conversation history maintained for each session.
- **Session Management**: Each PDF upload creates a unique session, with Redis storing only file/index references and chat history.
- **CORS Support**: Configured to allow cross-origin requests, making it compatible with web frontends.

## Tech Stack
- **FastAPI**: For building the API endpoints.
- **LangChain**: For document loading, text splitting, and vector store indexing.
- **Google Generative AI**: For embeddings (`embedding-001`) and language model (`gemini-1.5-flash`).
- **PyPDFLoader**: For extracting text from PDF files.
- **FAISS**: For persistent local vector index storage.
- **Redis**: For persistent session and chat history storage.
- **Pydantic**: For request validation and data modeling.
- **Python**: Core programming language.

## Prerequisites
- Python 3.8+
- A Google API key for Google Generative AI (set as `GEMINI_API_KEY` in a `.env` file).
- A running Redis instance.
- Required Python packages (listed in `requirements.txt`).

## Installation
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. Create a virtual environment and activate it:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root and add your Google API key:
   ```plaintext
   GEMINI_API_KEY=your-google-api-key
   REDIS_URL=redis://localhost:6379/0
   SESSION_TTL_SECONDS=86400
   SESSION_STORAGE_DIR=./storage/sessions
   ```

5. Run the FastAPI server:
   ```bash
   uvicorn main:app --reload
   ```

   The server will run at `http://localhost:8000`.

## Usage
### 1. Upload a PDF
- **Endpoint**: `POST /upload-pdf/`
- **Request**: Upload a PDF file using a multipart form-data request.
- **Response**: Returns a JSON object with a `session_id` and a success message.
- **Example**:
  ```bash
  curl -X POST "http://localhost:8000/upload-pdf/" -F "file=@/path/to/your/file.pdf"
  ```
  **Response**:
  ```json
  {
    "message": "PDF uploaded and indexed successfully",
    "session_id": "550e8400-e29b-41d4-a716-446655440000"
  }
  ```

### 2. Chat with the PDF
- **Endpoint**: `POST /chat/`
- **Request**: Send a JSON payload with `session_id` and `query`.
- **Response**: Returns the response to the query based on the PDF content.
- **Example**:
  ```bash
  curl -X POST "http://localhost:8000/chat/" -H "Content-Type: application/json" -d '{"session_id": "550e8400-e29b-41d4-a716-446655440000", "query": "What is the main topic of the PDF?"}'
  ```
  **Response**:
  ```json
  {
    "response": "The main topic of the PDF is..."
  }
  ```

### 3. Root Endpoint
- **Endpoint**: `GET /`
- **Response**: Confirms the server is running.
- **Example**:
  ```bash
  curl http://localhost:8000/
  ```
  **Response**:
  ```json
  {
    "message": "Server is running"
  }
  ```

## Project Structure
```
├── main.py                # FastAPI application code
├── requirements.txt       # Python dependencies
├── .env                   # Environment variables (not tracked in git)
├── README.md              # This file
├── app.py                 # FastAPI application code
└── temp dir               # Temporary storage for uploaded PDFs
```

## Dependencies
Install the required packages using:
```bash
pip install fastapi uvicorn python-multipart python-dotenv langchain langchain-community langchain-google-genai pypdf redis faiss-cpu
```

## Notes
- **Session Management**: Redis stores only the session metadata: `pdf_path`, `index_path`, and the latest 5 chat turns.
- **Persistent Index**: Each upload stores the original PDF and a FAISS index under `SESSION_STORAGE_DIR`.
- **Chat Performance**: The `/chat/` endpoint loads the saved FAISS index directly instead of rebuilding embeddings.
- **CORS**: The API allows all origins (`*`) for simplicity. In production, restrict `allow_origins` to your frontend domain (e.g., `https://chatwithpdf-aliraza.netlify.app`).
- **Session Expiry**: Redis keys expire automatically using `SESSION_TTL_SECONDS` (default: 86400 seconds).

## Error Handling
- **Invalid PDF**: Returns a 400 error if the uploaded file is not a valid PDF.
- **Session Not Found**: Returns a 404 error if the `session_id` provided in the `/chat/` endpoint does not exist.

## Future Improvements
- Implement user authentication to secure sessions.
- Support multiple file uploads per session.
- Add rate limiting to prevent abuse.
- Enhance error messages with more details.

## License
This project is licensed under the MIT License.
