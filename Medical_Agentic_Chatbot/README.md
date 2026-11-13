# MedGuide AI

A medical education chatbot built with FastAPI, LangGraph, OpenRouter, Pinecone, and a local PDF knowledge base. It lets users ask medical questions, upload images, speak to the app, and receive answers with source-aware context and uncertainty-aware guidance.

This project is designed for educational use and is not a substitute for professional medical advice. It includes a safety-first prompt layer and emergency guidance for urgent symptoms.

## Features

- Medical Q&A chat interface with conversation memory
- PDF knowledge-base retrieval using Pinecone vector search
- Optional web search for current clinical guidance via Tavily
- Image inspection support for medical-relevant image analysis
- Local speech-to-text transcription using Faster Whisper
- Text-to-speech response generation via OpenRouter
- Browser-based frontend served from FastAPI
- Persistent chat memory via SQLite checkpointing

## Tech Stack

- Python 3.10+
- FastAPI
- Uvicorn
- LangGraph
- LangChain OpenAI client
- OpenRouter API
- Pinecone vector database
- Tavily search API
- PyMuPDF for PDF parsing
- SentenceTransformers for embeddings
- Faster Whisper for local transcription
- SQLite for memory checkpoints

## Project Structure

```text
Medical_Agentic_Chatbot/
├── app/
│   ├── __init__.py
│   ├── agent.py          # LangGraph workflow and medical response logic
│   ├── config.py         # Application settings and environment config
│   ├── knowledge.py      # Pinecone indexing and semantic search
│   └── main.py           # FastAPI app and API routes
├── data/
│   └── Medical_book.pdf  # Source medical PDF used for grounding
├── static/
│   ├── app.js
│   └── style.css
├── templates/
│   └── index.html
├── .env                  # Local environment variables (not committed)
├── ingest.py             # Ingests PDF content into Pinecone
├── medical_memory.db     # SQLite checkpoint database
├── requirements.txt
├── test.py               # Simple graph smoke test
└── README.md
```

## Prerequisites

Before running the app, make sure you have:

- Python 3.10 or newer
- pip installed
- Access to OpenRouter API keys
- A Pinecone account and API key
- Optional: Tavily API key for external web search
- A PDF source document in `data/Medical_book.pdf`

## Environment Setup

Create a `.env` file in the project root with the following variables:

```env
OPENROUTER_API_KEY=your_openrouter_api_key
PINECONE_API_KEY=your_pinecone_api_key
TAVILY_API_KEY=your_tavily_api_key
API_TOKEN=optional_api_token_for_frontend_access
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
PINECONE_INDEX=medical-agent
ALLOWED_ORIGINS=http://localhost:8010,http://127.0.0.1:8010
```

If you do not want to use API token authentication, leave `API_TOKEN` blank.

## Install Dependencies

```bash
pip install -r requirements.txt
pip install faster-whisper sentence-transformers
```

The application imports `faster_whisper` and `sentence-transformers` at runtime, so they should be installed explicitly even though they are not always listed in the project requirements file.

## Build the Knowledge Base

The app relies on a Pinecone vector index populated from the PDF. Run the ingestion script:

```bash
python ingest.py --pdf data/Medical_book.pdf
```

This will split the PDF into chunks, generate embeddings, and upsert them into Pinecone.

## Run the Application

Start the server:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
```

Then open the app in a browser:

```text
http://localhost:8010
```

## Usage

- Ask a medical question in the chat box
- Optionally attach an image for visual context
- Use the microphone for voice input
- Listen to the response audio output using the speaker button
- The app will return an answer along with source references when available

## API Endpoints

### Health check

```http
GET /api/health
```

### Chat

```http
POST /api/chat
```

Request body:

```json
{
  "message": "What are common causes of headaches?",
  "history": [
    {"role": "user", "content": "I have a headache"},
    {"role": "assistant", "content": "What else are you noticing?"}
  ],
  "image_data": "optional_base64_image"
}
```

### Speech to text

```http
POST /api/transcribe
```

Upload an audio file to transcribe it into text.

### Text to speech

```http
POST /api/speak
```

Send a JSON payload such as:

```json
{
  "text": "This is the answer to read aloud."
}
```

## Safety and Medical Disclaimer

This app is intended for medical education and informational support only. It is not a clinician, diagnosis tool, or emergency system. The system prompt explicitly instructs the assistant to:

- avoid definitive diagnoses
- emphasize uncertainty when the evidence is limited
- suggest clinical evaluation when appropriate
- recommend emergency services for urgent symptoms

For severe symptoms such as chest pain, breathing difficulty, severe bleeding, stroke symptoms, unconsciousness, or suicidal intent, seek emergency help immediately.

## Smoke Test

You can run a quick test of the graph pipeline:

```bash
python test.py
```

## Notes

- The embedded knowledge source is a historical PDF (Gale medical reference, A-B section) and should be treated as educational context, not current clinical guidance for time-sensitive issues.
- The app prefers current medical guidance when questions require up-to-date information and uses web search when relevant.
- Pinecone and API configuration must be valid for the app to answer questions successfully.

## License

This project does not currently include a specific license file. If you plan to distribute or reuse it, add an appropriate license before publication.
