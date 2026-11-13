
import os
import certifi

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict


# --------------------------------------------------
# SSL Certificate Fix
# --------------------------------------------------

ssl_cert = os.environ.get("SSL_CERT_FILE")

if not ssl_cert or not os.path.exists(ssl_cert):
    os.environ["SSL_CERT_FILE"] = certifi.where()

load_dotenv()


# --------------------------------------------------
# Application Settings
# --------------------------------------------------

class Settings(BaseSettings):

    # OpenRouter API
    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # Other API Keys
    pinecone_api_key: str = ""
    tavily_api_key: str = ""

    # Pinecone Settings
    pinecone_index: str = "medical-agent"

    # OpenRouter Chat and Vision Models
    openrouter_chat_model: str = "openrouter/free"
    openrouter_vision_model: str = "google/gemini-2.5-flash"

    # OpenRouter Speech Models
    openrouter_speech_model: str = "x-ai/grok-voice-tts-1.0"
    openrouter_transcription_model: str = "openai/whisper-large-v3"

    # Embedding Model
    openrouter_embed_model: str = ""

    # API Authentication Token
    api_token: str = ""

    # Allowed Frontend Origins
    allowed_origins: str = (
        "http://localhost:8010,"
        "http://127.0.0.1:8010"
    )

    # Environment Configuration
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


# --------------------------------------------------
# Initialize Settings
# --------------------------------------------------

settings = Settings()

