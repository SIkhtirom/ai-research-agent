"""Embedding provider resolution.

The default provider is a fully local, CPU-only SentenceTransformer model
(``all-MiniLM-L6-v2``) so no external embedding API is required. OpenAI-compatible
and legacy Gemini adapters remain available as alternatives.
"""

from typing import Any

from langchain_core.embeddings import Embeddings
from langchain_openai import OpenAIEmbeddings

from app.core.config import settings

_DEFAULT_LOCAL_MODEL = "all-MiniLM-L6-v2"


class LocalSentenceTransformerEmbeddings(Embeddings):
    """Local, CPU-based embeddings via the sentence-transformers library."""

    def __init__(self, model_name: str = _DEFAULT_LOCAL_MODEL):
        self.__model_name = model_name
        self.__model: Any | None = None

    def __get_model(self):
        if self.__model is None:
            from sentence_transformers import SentenceTransformer

            self.__model = SentenceTransformer(self.__model_name or _DEFAULT_LOCAL_MODEL)
        return self.__model

    @staticmethod
    def __to_vector(values: Any) -> list[float]:
        return [float(v) for v in values]

    def embed_query(self, text: str) -> list[float]:
        model = self.__get_model()
        return self.__to_vector(model.encode(text).tolist())

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        model = self.__get_model()
        encoded = model.encode(texts)
        return [self.__to_vector(v) for v in encoded]


class GoogleGenaiEmbeddingsAdapter(Embeddings):
    """Legacy embedding adapter implemented over the official ``google.genai`` SDK."""

    def __init__(self, model: str, api_key: str | None = None):
        self.__model = model
        self.__api_key = api_key
        self.__client: Any | None = None

    def __get_client(self):
        if self.__client is None:
            from google import genai

            if not self.__api_key:
                raise ValueError(
                    "GOOGLE_API_KEY is required to create Gemini embeddings."
                )
            self.__client = genai.Client(api_key=self.__api_key)
        return self.__client

    @staticmethod
    def __clean_model(model: str) -> str:
        cleaned = model.removeprefix("models/")
        return cleaned.removeprefix("models:")

    @staticmethod
    def __to_vector(embedding: Any) -> list[float]:
        values = getattr(embedding, "values", None)
        if values is None:
            raise RuntimeError(
                "Unexpected embedding response shape from Google GenAI SDK."
            )
        return list(values)

    def embed_query(self, text: str) -> list[float]:
        client = self.__get_client()
        response = client.models.embed_content(
            model=self.__clean_model(self.__model),
            contents=text,
        )
        return self.__to_vector(response.embeddings)

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        client = self.__get_client()
        embeddings = []
        for text in texts:
            response = client.models.embed_content(
                model=self.__clean_model(self.__model),
                contents=text,
            )
            embeddings.append(self.__to_vector(response.embeddings))
        return embeddings


def get_embedding_provider(provider: str = "local", api_key: str | None = None) -> Embeddings:
    """Create the embedding instance for the requested provider."""
    if provider == "local":
        return LocalSentenceTransformerEmbeddings(
            model_name=settings.local_embedding_model
        )
    if provider == "gemini":
        return GoogleGenaiEmbeddingsAdapter(model="text-embedding-004", api_key=api_key)
    if provider == "openai":
        return OpenAIEmbeddings(
            model=settings.openai_embedding_model,
            api_key=api_key or settings.openai_api_key,
            base_url=settings.openai_base_url,
        )
    raise ValueError(f"Unknown embedding provider: {provider}")
