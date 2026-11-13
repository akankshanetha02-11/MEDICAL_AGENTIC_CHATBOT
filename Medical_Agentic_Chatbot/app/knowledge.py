
from functools import lru_cache

import certifi
import os
from pinecone import Pinecone, ServerlessSpec
from openai import OpenAI
from sentence_transformers import SentenceTransformer

from app.config import settings


# SSL certificate configuration
os.environ["SSL_CERT_FILE"] = certifi.where()


# Embedding dimension: MiniLM-L6-v2 = 384
EMBEDDING_DIM = 384


@lru_cache()
def clients():

    if not settings.openrouter_api_key:
        raise ValueError("OpenRouter API key is missing.")

    if not settings.pinecone_api_key:
        raise ValueError("Pinecone API key is missing.")

    ai = OpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url
    )

    pc = Pinecone(
        api_key=settings.pinecone_api_key
    )

    return ai, pc


# Load local embedding model
@lru_cache()
def embedding_model():

    return SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2"
    )


def ensure_index():

    _, pc = clients()

    if not pc.has_index(settings.pinecone_index):

        pc.create_index(
            name=settings.pinecone_index,
            dimension=EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(
                cloud="aws",
                region="us-east-1"
            )
        )

    else:
        description = pc.describe_index(
            name=settings.pinecone_index
        )

        if description.dimension != EMBEDDING_DIM:
            raise ValueError(
                f"Index dimension is {description.dimension}, "
                f"but embedding model requires {EMBEDDING_DIM}. "
                "Create a separate Pinecone index for this model."
            )

    return pc.Index(settings.pinecone_index)


# Generate embeddings locally
def embed(texts):

    model = embedding_model()

    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        convert_to_numpy=True
    )

    return vectors.tolist()


# Search knowledge base
def search_kb(query, top_k=5):

    index = ensure_index()

    vector = embed([query])[0]

    result = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True
    )

    return [
        {
            "page": m.metadata.get("page"),
            "text": m.metadata.get("text", ""),
            "score": round(m.score, 3),
            "source": "Gale Encyclopedia (2002)"
        }
        for m in result.matches
        if m.score >= 0.30
    ]
