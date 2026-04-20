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
- **Text Extraction and Indexing**: Extract text from PDFs and build an in-memory searchable index.
- **Conversational Interface**: Query the PDF content using natural language, with conversation history maintained for each session.
- **Session Management**: Each PDF upload creates an in-memory session with automatic expiration and bounded cache size.
- **Rate Limiting**: Upload and chat endpoints are rate-limited per IP address.
- **Upload Guardrails**: PDF uploads are limited to 20 MB and validated before processing.
- **CORS Support**: Configured to allow cross-origin requests, making it compatible with web frontends.

## Tech Stack
- **FastAPI**: For building the API endpoints.
- **LangChain**: For document loading, text splitting, and vector store indexing.
- **Google Generative AI**: For embeddings (`gemini-embedding-001`) and language model (`gemini-2.5-flash-lite`).
- **PyPDFLoader**: For extracting text from PDF files.
- **cachetools**: For the in-memory LRU session store.
- **slowapi**: For request rate limiting.
- **Pydantic**: For request validation and data modeling.
- **Python**: Core programming language.

## Prerequisites
- Python 3.8+
- A Google API key for Google Generative AI (set as `GEMINI_API_KEY` in a `.env` file).
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
   ```

5. Run the FastAPI server:
   ```bash
   uvicorn app:app --reload
   ```

   The server will run at `http://localhost:8000`.

## Usage
### 1. Upload a PDF
- **Endpoint**: `POST /upload-pdf/`
- **Request**: Upload a PDF file using a multipart form-data request.
- **Limits**: Maximum upload size is 20 MB. Uploads are limited to `3/hour` per IP.
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
- **Limits**: Chat requests are limited to `30/minute` per IP.
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
- **Response**: Confirms the server is running and returns the current active session count.
- **Example**:
  ```bash
  curl http://localhost:8000/
  ```
  **Response**:
  ```json
  {
    "message": "Server is running",
    "active_sessions": 1
  }
  ```

## Project Structure
```
app.py                # FastAPI application code
main.py               # Minimal local entry file
requirements.txt      # Python dependencies
.env                  # Environment variables (not tracked in git)
README.md             # Project documentation
```

## Dependencies
Install the required packages using:
```bash
pip install fastapi uvicorn python-multipart python-dotenv langchain langchain-community langchain-google-genai pypdf cachetools slowapi
```

## Notes
- **Session Management**: Session data is stored in an in-memory `LRUCache` with a maximum of 50 active sessions.
- **Session Expiry**: Sessions expire after 1 hour and a background cleanup task sweeps expired sessions every 15 minutes.
- **Conversation Memory**: Each session keeps the latest 5 turns using `ConversationBufferWindowMemory`.
- **Temporary Files**: Uploaded PDFs are written to `/tmp/<session_id>.pdf` during processing and removed afterward.
- **CORS**: The API allows all origins (`*`) for simplicity. In production, restrict `allow_origins` to your frontend domain (e.g., `https://chatwithpdf-aliraza.netlify.app`).
- **Request Context**: Chat requests prepend prior conversation history to the current query before sending it to the model.

## Error Handling
- **Invalid PDF**: Returns a 400 error if the uploaded file is not a valid PDF or does not contain valid PDF content.
- **File Too Large**: Returns a 413 error if the uploaded file exceeds 20 MB.
- **Session Not Found**: Returns a 404 error if the `session_id` provided in the `/chat/` endpoint does not exist.
- **Session Expired**: Returns a 410 error if the session is older than 1 hour.
- **Rate Limit Exceeded**: Returns a rate-limit error when upload or chat thresholds are exceeded.

## Future Improvements
- Implement user authentication to secure sessions.
- Support multiple file uploads per session.
- Enhance error messages with more details.

## License
This project is licensed under the MIT License.
