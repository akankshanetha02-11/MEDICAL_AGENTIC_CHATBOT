
import base64
import os
import secrets
import tempfile

from pathlib import Path
from uuid import uuid4

from fastapi import (
    FastAPI,
    File,
    Header,
    HTTPException,
    UploadFile
)

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from openai import OpenAI
from faster_whisper import WhisperModel

from app.config import settings
from app.agent import graph


# --------------------------------------------------
# Application Setup
# --------------------------------------------------

ROOT = Path(__file__).resolve().parent.parent

app = FastAPI(
    title="MedGuide AI - OpenRouter API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins.split(","),
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Conversation-ID"
    ]
)

app.mount(
    "/static",
    StaticFiles(directory=ROOT / "static"),
    name="static"
)


# --------------------------------------------------
# Local Whisper - Free Speech to Text
# --------------------------------------------------

whisper_model = None


def get_whisper_model():

    global whisper_model

    if whisper_model is None:

        print(
            "Loading Local Whisper model...",
            flush=True
        )

        whisper_model = WhisperModel(
            "base",
            device="cpu",
            compute_type="int8"
        )

        print(
            "Local Whisper model loaded successfully.",
            flush=True
        )

    return whisper_model


# --------------------------------------------------
# OpenRouter Client
# --------------------------------------------------

def get_openrouter_client():

    if not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="OPENROUTER_API_KEY is missing in .env"
        )

    return OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        timeout=60,
        max_retries=1
    )


# --------------------------------------------------
# Chat Request Model
# --------------------------------------------------

class ChatRequest(BaseModel):

    message: str = Field(
        min_length=1,
        max_length=4000
    )

    history: list[dict[str, str]] = Field(
        default_factory=list,
        max_length=10
    )

    image_data: str | None = None


# --------------------------------------------------
# Authentication
# --------------------------------------------------

def auth(authorization: str | None):

    if (
        settings.api_token
        and not secrets.compare_digest(
            authorization or "",
            f"Bearer {settings.api_token}"
        )
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid API token"
        )


# --------------------------------------------------
# Image Analysis - OpenRouter Vision
# --------------------------------------------------

def inspect_image(data):

    if not data:
        return ""

    try:

        header, payload = data.split(",", 1)

        mime = header.split(";")[0].split(":")[1]

        raw = base64.b64decode(
            payload,
            validate=True
        )

        if (
            mime not in (
                "image/jpeg",
                "image/png",
                "image/webp"
            )
            or len(raw) > 5_000_000
        ):
            raise ValueError(
                "Only JPEG/PNG/WebP under 5MB supported"
            )

    except (ValueError, IndexError) as exc:

        raise HTTPException(
            status_code=400,
            detail=f"Invalid image: {exc}"
        )

    try:

        client = get_openrouter_client()

        result = client.chat.completions.create(
            model=settings.openrouter_vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Describe only objectively visible "
                                "medical-relevant features. "
                                "Do not diagnose or estimate severity. "
                                "If the image is unclear, say so."
                            )
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": data
                            }
                        }
                    ]
                }
            ],
            max_tokens=300
        )

        return (
            result.choices[0].message.content or ""
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "OpenRouter Vision Error:",
            repr(exc),
            flush=True
        )

        raise HTTPException(
            status_code=502,
            detail="Image analysis unavailable"
        )


# --------------------------------------------------
# Home Page
# --------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home():

    return (
        ROOT / "templates" / "index.html"
    ).read_text(encoding="utf-8")


# --------------------------------------------------
# Health Check
# --------------------------------------------------

@app.get("/api/health")
def health():

    return {
        "status": "ok",

        "configured": bool(
            settings.openrouter_api_key
            and settings.pinecone_api_key
        ),

        "provider": "OpenRouter",

        "tavily": bool(
            settings.tavily_api_key
        ),

        "speech": bool(
            settings.openrouter_api_key
            and settings.openrouter_speech_model
        ),

        "transcription": "Local Whisper (Free)"
    }


# --------------------------------------------------
# AI Chat - LangGraph + OpenRouter
# --------------------------------------------------

@app.post("/api/chat")
def chat(
    payload: ChatRequest,
    authorization: str | None = Header(default=None),
    conversation_id: str | None = Header(
        default=None,
        alias="X-Conversation-ID"
    )
):

    auth(authorization)

    if (
        not settings.openrouter_api_key
        or not settings.pinecone_api_key
    ):
        raise HTTPException(
            status_code=503,
            detail=(
                "Set OPENROUTER_API_KEY and "
                "PINECONE_API_KEY in .env"
            )
        )

    history = [
        item for item in payload.history
        if (
            item.get("role") in ("user", "assistant")
            and isinstance(item.get("content"), str)
        )
    ][:10]

    thread_id = conversation_id or str(uuid4())

    config = {
        "configurable": {
            "thread_id": thread_id
        }
    }

    try:

        observation = inspect_image(
            payload.image_data
        )

        state = graph.invoke(
            {
                "question": payload.message,
                "history": history,
                "image_description": observation,
                "kb": [],
                "web": [],
                "answer": "",
                "route": ""
            },
            config=config
        )

        return {
            "answer": state["answer"],

            "sources": [
                {
                    "type": "pdf",
                    "page": item["page"],
                    "score": item["score"]
                }
                for item in state["kb"]
            ] + [
                {
                    "type": "web",
                    "url": item["url"],
                    "title": item["title"]
                }
                for item in state["web"]
            ],

            "tools": (
                ["pinecone"]
                + (
                    ["tavily"]
                    if (
                        state["route"] == "web"
                        and settings.tavily_api_key
                    )
                    else []
                )
                + (
                    ["vision"]
                    if observation
                    else []
                )
            ),

            "conversation_id": thread_id
        }

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "Chat Error:",
            repr(exc),
            flush=True
        )

        raise HTTPException(
            status_code=502,
            detail="AI service failed. Check server logs."
        )


# --------------------------------------------------
# Voice to Text - Local Whisper (FREE)
# --------------------------------------------------

@app.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    authorization: str | None = Header(default=None)
):

    auth(authorization)

    data = await file.read(10_000_001)

    if len(data) > 10_000_000:

        raise HTTPException(
            status_code=413,
            detail="Audio exceeds 10 MB"
        )

    if not data:

        raise HTTPException(
            status_code=400,
            detail="Empty audio file"
        )

    suffix = Path(
        file.filename or "voice.webm"
    ).suffix

    if not suffix or len(suffix) > 10:
        suffix = ".webm"

    temp_path = None

    try:

        with tempfile.NamedTemporaryFile(
            delete=False,
            suffix=suffix
        ) as temp_audio:

            temp_audio.write(data)
            temp_path = temp_audio.name

        model = get_whisper_model()

        segments, info = model.transcribe(
            temp_path,
            vad_filter=True
        )

        transcript = " ".join(
            segment.text.strip()
            for segment in segments
        ).strip()

        return {
            "text": transcript,
            "language": info.language,
            "provider": "Local Whisper"
        }

    except Exception as exc:

        print(
            "Local Whisper Error:",
            repr(exc),
            flush=True
        )

        raise HTTPException(
            status_code=500,
            detail="Local speech transcription failed"
        )

    finally:

        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

        await file.close()


# --------------------------------------------------
# Text to Speech - OpenRouter
# --------------------------------------------------

@app.post("/api/speak")
def speak(
    payload: dict,
    authorization: str | None = Header(default=None)
):

    auth(authorization)

    text = str(
        payload.get("text", "")
    ).strip()[:3000]

    if not text:

        raise HTTPException(
            status_code=400,
            detail="Missing text"
        )

    try:

        client = get_openrouter_client()

        speech = client.audio.speech.create(
            model=settings.openrouter_speech_model,
            voice="ara",
            input=text,
            response_format="mp3"
        )

        return Response(
            content=speech.content,
            media_type="audio/mpeg"
        )

    except HTTPException:
        raise

    except Exception as exc:

        print(
            "OpenRouter Speech Error:",
            repr(exc),
            flush=True
        )

        raise HTTPException(
            status_code=502,
            detail="Speech synthesis failed"
        )

