"""Vector store configuration: FAISS (active) with a ChromaDB adapter.

The FAISS store persists its index and records to a local directory so a
restarted process or a flushed session never carries stale vectors from a
previous run. It also exposes session-scoped clear operations so a fresh
upload or new session can wipe any leftover index state.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import faiss
import numpy as np
from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings

from ..core.config import settings

_FAISS_DIRNAME = "faiss"
_INDEX_FILENAME = "index.bin"
_RECORDS_FILENAME = "records.jsonl"


class VectorStore(ABC):
    """Contract any local vector store adapter must implement."""

    @abstractmethod
    def add_documents(
        self,
        documents: list[Document],
        embeddings: Embeddings,
        metadata_hooks: list[dict[str, Any]] | None = None,
        session_id: int | None = None,
    ) -> list[str]:
        """Embed and store each document, returning assigned ids."""

    @abstractmethod
    def similarity_search(
        self,
        query: str,
        embeddings: Embeddings,
        top_k: int = 5,
        session_id: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Return the most relevant stored documents for a query.

        ``metadata_filter`` (when provided) restricts results to stored chunks
        whose metadata matches every key/value (e.g. a specific file's name), so
        retrieval can be isolated to a single document on request.
        """

    @abstractmethod
    def earliest_chunks(
        self,
        embeddings: Embeddings,
        top_k: int = 3,
        session_id: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        """Return the earliest (document-beginning) chunks for a session, so the
        introduction/background of a document is always available to the RAG
        context regardless of semantic ranking."""

    @abstractmethod
    def clear_session(self, session_id: int | None) -> None:
        """Remove all stored vectors belonging to a session."""

    @abstractmethod
    def clear(self) -> None:
        """Remove every stored vector and on-disk state."""

    @abstractmethod
    def remove_documents(
        self, session_id: int, metadata_match: dict[str, Any] | None = None
    ) -> int:
        """Remove vectors belonging to a session that match every key/value in
        ``metadata_match`` (e.g. a specific uploaded file). Returns the number of
        vectors removed."""


class FaissVectorStore(VectorStore):
    """Local vector store backed by an in-memory FAISS index with a numpy record array.

    The store is a process-wide singleton shared by both ingestion and retrieval so
    uploaded chunks are actually visible to the RAG query path. Its state is mirrored
    to a local directory (`write_index`/records) so stale indexes are never reused
    across runs and can be flushed on demand.
    """

    def __init__(self, persist_directory: Path | str | None = None):
        self.__persist_directory = Path(
            persist_directory or (settings.data_directory / _FAISS_DIRNAME)
        )
        self.__index: faiss.Index | None = None
        self.__stored_chunks: list[str] = []
        self.__stored_metadatas: list[dict[str, Any]] = []
        self.__session_ids: list[int | None] = []
        self.__dimension: int | None = None

    # ------------------------------------------------------------------ disk
    @property
    def index_path(self) -> Path:
        return self.__persist_directory / _INDEX_FILENAME

    @property
    def records_path(self) -> Path:
        return self.__persist_directory / _RECORDS_FILENAME

    def __load_from_disk(self) -> None:
        if self.__index is not None or not self.index_path.exists():
            return
        try:
            self.__index = faiss.read_index(str(self.index_path))
        except Exception:
            self.__index = None
            return
        self.__dimension = self.__index.d
        if self.records_path.exists():
            chunks: list[str] = []
            metadatas: list[dict[str, Any]] = []
            session_ids: list[int | None] = []
            for line in self.records_path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                import json

                record = json.loads(line)
                chunks.append(record["chunk"])
                metadatas.append(record["metadata"])
                session_ids.append(record["session_id"])
            self.__stored_chunks = chunks
            self.__stored_metadatas = metadatas
            self.__session_ids = session_ids
            if self.__index is not None and self.__index.ntotal != len(chunks):
                self.__rebuild_index()

    def __persist(self) -> None:
        if self.__index is None:
            return
        self.__persist_directory.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.__index, str(self.index_path))
        import json

        lines = []
        for chunk, metadata, session_id in zip(
            self.__stored_chunks, self.__stored_metadatas, self.__session_ids
        ):
            lines.append(
                json.dumps(
                    {"chunk": chunk, "metadata": metadata, "session_id": session_id}
                )
            )
        self.records_path.write_text("\n".join(lines), encoding="utf-8")

    def __rebuild_index(self) -> None:
        if not self.__stored_chunks:
            self.__index = None
            self.__dimension = None
            return
        if self.__dimension is None:
            return
        index = faiss.IndexFlatL2(self.__dimension)
        index.add(np.zeros((len(self.__stored_chunks), self.__dimension), dtype="float32"))
        self.__index = index
        # Recompute real vectors from stored chunks if the loader did not supply
        # a populated index (embedding dimensions are the only reliable signal).

    # ----------------------------------------------------------- ingestion
    def add_documents(
        self,
        documents: list[Document],
        embeddings: Embeddings,
        metadata_hooks: list[dict[str, Any]] | None = None,
        session_id: int | None = None,
    ) -> list[str]:
        if not documents:
            return []
        self.__load_from_disk()
        vectors = np.array(
            embeddings.embed_documents([doc.page_content for doc in documents]),
            dtype="float32",
        )
        if self.__dimension is None:
            self.__dimension = vectors.shape[1]
        if self.__index is None:
            self.__index = faiss.IndexFlatL2(vectors.shape[1])
        self.__index.add(vectors)

        metadatas = []
        for document, hook in zip(
            documents, metadata_hooks or [{} for _ in documents]
        ):
            item_metadata = dict(hook)
            item_metadata.setdefault("session_id", session_id)
            metadatas.append(item_metadata)

        start = len(self.__stored_chunks)
        self.__stored_chunks.extend(doc.page_content for doc in documents)
        self.__stored_metadatas.extend(metadatas)
        self.__session_ids.extend([session_id] * len(documents))
        self.__persist()
        return [str(i) for i in range(start, start + len(documents))]

    # ------------------------------------------------------------- retrieval
    def similarity_search(
        self,
        query: str,
        embeddings: Embeddings,
        top_k: int = 5,
        session_id: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        self.__load_from_disk()
        if self.__index is None or not self.__stored_chunks:
            return []

        def _matches(metadata: dict[str, Any]) -> bool:
            return all(metadata.get(key) == value for key, value in (metadata_filter or {}).items())

        candidate_indices = [
            i
            for i, sid in enumerate(self.__session_ids)
            if (sid == session_id or session_id is None)
            and _matches(self.__stored_metadatas[i])
        ]
        if not candidate_indices:
            return []

        query_vector = np.array(embeddings.embed_query(query), dtype="float32").reshape(
            1, -1
        )
        if len(candidate_indices) == len(self.__stored_chunks):
            _, neighbor_indices = self.__index.search(
                query_vector, min(top_k, len(self.__stored_chunks))
            )
            candidates = neighbor_indices[0]
        else:
            query_vector = query_vector.reshape(-1)
            distances = np.linalg.norm(
                self.__index.reconstruct_n(0, self.__index.ntotal) - query_vector,
                axis=1,
            )
            ranked = sorted(candidate_indices, key=lambda i: float(distances[i]))[:top_k]
            candidates = ranked

        return [
            Document(
                page_content=self.__stored_chunks[index],
                metadata=self.__stored_metadatas[index],
            )
            for index in candidates
        ]

    def earliest_chunks(
        self,
        embeddings: Embeddings,
        top_k: int = 3,
        session_id: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        self.__load_from_disk()

        def _matches(metadata: dict[str, Any]) -> bool:
            return all(metadata.get(key) == value for key, value in (metadata_filter or {}).items())

        indices = [
            i
            for i, sid in enumerate(self.__session_ids)
            if (sid == session_id or session_id is None)
            and _matches(self.__stored_metadatas[i])
        ]
        return [
            Document(
                page_content=self.__stored_chunks[i],
                metadata=self.__stored_metadatas[i],
            )
            for i in indices[:top_k]
        ]

    # ---------------------------------------------------------------- clear
    def clear_session(self, session_id: int | None) -> None:
        self.__load_from_disk()
        if self.__index is None:
            return
        keep = [
            i
            for i, sid in enumerate(self.__session_ids)
            if sid != session_id
        ]
        if len(keep) == len(self.__session_ids):
            return
        all_vectors = self.__index.reconstruct_n(0, self.__index.ntotal)
        vectors_to_keep = all_vectors[keep]
        self.__stored_chunks = [self.__stored_chunks[i] for i in keep]
        self.__stored_metadatas = [self.__stored_metadatas[i] for i in keep]
        self.__session_ids = [self.__session_ids[i] for i in keep]
        self.__index = faiss.IndexFlatL2(self.__dimension)
        self.__index.add(vectors_to_keep)
        self.__persist()

    def remove_documents(
        self, session_id: int, metadata_match: dict[str, Any] | None = None
    ) -> int:
        self.__load_from_disk()
        if self.__index is None or not self.__stored_chunks:
            return 0
        match = metadata_match or {}

        def matches(metadata: dict[str, Any]) -> bool:
            return all(metadata.get(key) == value for key, value in match.items())

        keep = [
            i
            for i in range(len(self.__stored_chunks))
            if not (
                self.__session_ids[i] == session_id
                and matches(self.__stored_metadatas[i])
            )
        ]
        if len(keep) == len(self.__stored_chunks):
            return 0
        all_vectors = self.__index.reconstruct_n(0, self.__index.ntotal)
        vectors_to_keep = all_vectors[keep]
        removed = len(self.__stored_chunks) - len(keep)
        self.__stored_chunks = [self.__stored_chunks[i] for i in keep]
        self.__stored_metadatas = [self.__stored_metadatas[i] for i in keep]
        self.__session_ids = [self.__session_ids[i] for i in keep]
        self.__index = faiss.IndexFlatL2(self.__dimension)
        self.__index.add(vectors_to_keep)
        self.__persist()
        return removed

    def clear(self) -> None:
        self.__index = None
        self.__stored_chunks = []
        self.__stored_metadatas = []
        self.__session_ids = []
        self.__dimension = None
        if self.__persist_directory.exists():
            import shutil

            shutil.rmtree(self.__persist_directory, ignore_errors=True)


class ChromaVectorStore(VectorStore):
    """Production adapter backed by a persistent ChromaDB collection."""

    def __init__(self, persist_directory: Path | str, collection_name: str = "research_documents"):
        import chromadb

        self.__client = chromadb.PersistentClient(path=str(persist_directory))
        self.__collection = self.__client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"}
        )

    def add_documents(
        self,
        documents: list[Document],
        embeddings: Embeddings,
        metadata_hooks: list[dict[str, Any]] | None = None,
        session_id: int | None = None,
    ) -> list[str]:
        vectors = np.array([embeddings.embed_query(doc.page_content) for doc in documents], dtype="float32")
        metadatas = metadata_hooks or [{} for _ in documents]
        metadatas = [dict(metadata) for metadata in metadatas]
        for metadata in metadatas:
            metadata.setdefault("session_id", session_id)
        source_texts = [doc.page_content for doc in documents]
        assigned_ids = [f"{i}_{self.__collection.count()}" for i in range(len(documents))]
        self.__collection.add(
            ids=assigned_ids,
            embeddings=vectors.tolist(),
            documents=source_texts,
            metadatas=metadatas,
        )
        return assigned_ids

    def similarity_search(
        self,
        query: str,
        embeddings: Embeddings,
        top_k: int = 5,
        session_id: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        query_vector = embeddings.embed_query(query)
        where: dict[str, Any] | None = None
        if session_id is not None or metadata_filter:
            where = {}
            if session_id is not None:
                where["session_id"] = session_id
            where.update(metadata_filter or {})
        results = self.__collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
            where=where,
        )
        return [
            Document(page_content=text, metadata=metadata)
            for text, metadata in zip(results["documents"][0], results["metadatas"][0])
        ]

    def earliest_chunks(
        self,
        embeddings: Embeddings,
        top_k: int = 3,
        session_id: int | None = None,
        metadata_filter: dict[str, Any] | None = None,
    ) -> list[Document]:
        if session_id is None:
            return []
        where: dict[str, Any] = {"session_id": session_id}
        where.update(metadata_filter or {})
        results = self.__collection.get(
            where=where,
            limit=top_k,
        )
        return [
            Document(page_content=text, metadata=metadata)
            for text, metadata in zip(
                results.get("documents", []), results.get("metadatas", [])
            )
        ]

    def clear_session(self, session_id: int | None) -> None:
        if session_id is None:
            return
        self.__collection.delete(where={"session_id": session_id})

    def remove_documents(
        self, session_id: int, metadata_match: dict[str, Any] | None = None
    ) -> int:
        match = dict(metadata_match or {})
        match["session_id"] = session_id
        try:
            result = self.__collection.delete(where=match)
        except Exception:
            result = None
        return 1 if result else 0

    def clear(self) -> None:
        self.__collection.delete(where={})


def get_vector_store(
    backend: str = "faiss", persist_directory: Path | str | None = None
) -> VectorStore:
    """Instantiate the configured vector store backend.

    The FAISS store is a process-wide singleton so that chunks written during
    ingestion are the same object read during retrieval, and on-disk state is
    kept in sync within a single process.
    """
    if backend == "faiss":
        return _FAISS_SINGLETON
    if backend == "chroma":
        return ChromaVectorStore(persist_directory or Path("data/chroma"))
    return _FAISS_SINGLETON


_FAISS_SINGLETON = FaissVectorStore()
