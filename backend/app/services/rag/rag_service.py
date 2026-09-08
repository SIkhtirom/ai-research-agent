"""RAG pipeline: retrieve relevant chunks, synthesise an answer, and cite sources.

Context isolation: by default the assistant only reasons about the CURRENT
session's documents. When the user explicitly asks for a comparison (e.g.
"bandingkan dengan jurnal sebelumnya") retrieval is widened to every session so
previous work can be pulled back in. Citation markers/source lists are only
emitted when the user explicitly asks for citations.
"""

import logging
import re
import time
from typing import Any

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from ...core.config import Settings, settings
from ...core.embeddings import get_embedding_provider
from ...core.llm import get_llm
from ...db.crud import DocumentRepository, QueryLogRepository
from ...db.vector_store import VectorStore, get_vector_store

logger = logging.getLogger(__name__)

_FALLBACK_NO_CONTEXT = (
    "Mohon maaf, informasi mengenai hal tersebut tidak ditemukan dalam dokumen "
    "sumber yang Anda unggah. Silakan ajukan pertanyaan yang relevan dengan "
    "konteks dokumen yang tersedia."
)

# "jurnal ke-5", "jurnal 5", "dokumen ke 5" -> 5
_SOURCE_ORDINAL_RE = re.compile(
    r"\b(jurnal|dokumen|sumber)\s*(?:ke\s*[-]?\s*(\d+)|(\d+))\b",
    re.IGNORECASE,
)

_COMPARE_KEYWORDS = (
    "bandingkan",
    "bandingkan dengan",
    "perbandingan",
    "compare",
    "comparison",
    "compare with",
    "contrast",
    "beda",
    "bedanya",
    "perbedaan",
    "ulasan dengan",
)

_CITATION_KEYWORDS = (
    "kutipan",
    "kutip",
    "sitasi",
    "citation",
    "citations",
    "reference",
    "references",
    "referensi",
    "sumber yang",
    "sumbernya",
    "source",
    "cite",
    "daftar pustaka",
    "bibliografi",
    "bibliography",
    "pustaka",
    "apa7",
    "apa 7",
    "apa style",
    "pengertian",
    "definisi",
    "arti dari",
    "apa itu",
    "apa yang dimaksud",
    "menurut",
)

# General action requests the assistant must EXECUTE directly, without asking
# clarifying/technical questions (e.g. "which format is your file?").
_EXECUTE_KEYWORDS = (
    "rangkum",
    "ringkas",
    "rangku",
    "ringkes",
    "jelaskan",
    "jelasin",
    "deskripsikan",
    "deskripsi",
    "terangkan",
    "uraikan",
    "bahas",
    "analisis",
    "analisa",
    "simplify",
    "summarize",
    "summarise",
    "summary",
    "explain",
    "describe",
    "overview",
    "review",
    "break down",
    "buatkan rangkuman",
    "buatkan ringkasan",
    "bantu saya memahami",
    "tolong jelaskan",
    "beri tahu saya tentang",
)


class RAGService:
    def __init__(
        self,
        app_settings: Settings = settings,
        vector_store: VectorStore | None = None,
        llm: Any | None = None,
        embedding_provider: Any | None = None,
    ):
        self.__settings = app_settings
        self.__vector_store = vector_store or get_vector_store()
        self.__llm = llm or get_llm(
            provider=app_settings.llm_provider,
            model_name=self.__resolve_model_name(app_settings),
            api_key=app_settings.openai_api_key or app_settings.google_api_key,
        )
        self.__embedding_provider = embedding_provider or get_embedding_provider(
            provider=app_settings.embedding_provider,
            api_key=app_settings.openai_api_key or app_settings.google_api_key,
        )

    def generate_answer(
        self, db: Session, query: str, session_id: int, top_k: int | None = None
    ) -> dict[str, Any]:
        """Retrieve context, ask the LLM, and return the answer (with citation metadata).

        Returns a dict with keys: generated_response, citations, include_citations,
        comparison_mode.
        """
        _, prompt_messages, _, citations, want_citations, compare_mode = self.__prepare(
            db, query, session_id, top_k
        )
        if not prompt_messages:
            generated_response = _FALLBACK_NO_CONTEXT
            QueryLogRepository().create(
                db,
                session_id=session_id,
                prompt=query,
                generated_response=generated_response,
                citations=[],
            )
            logger.info(
                "rag fallback session=%s chunks=0 comparison_mode=%s",
                session_id,
                compare_mode,
            )
            return {
                "generated_response": generated_response,
                "citations": [],
                "include_citations": False,
                "comparison_mode": compare_mode,
            }
        start = time.perf_counter()
        response = self.__invoke_llm(prompt_messages)
        llm_ms = (time.perf_counter() - start) * 1000
        generated_response = getattr(response, "content", "") or ""
        QueryLogRepository().create(
            db,
            session_id=session_id,
            prompt=query,
            generated_response=generated_response,
            citations=citations,
        )
        logger.info(
            "rag answer session=%s include_citations=%s comparison_mode=%s llm_ms=%.1f",
            session_id, want_citations, compare_mode, llm_ms,
        )
        return {
            "generated_response": generated_response,
            "citations": citations if want_citations else [],
            "include_citations": want_citations,
            "comparison_mode": compare_mode,
        }

    def stream_answer(
        self,
        db: Session,
        query: str,
        session_id: int,
        top_k: int | None = None,
    ):
        """Stream a RAG answer token-by-token for SSE consumption.

        Yields dicts serialised as SSE events: a leading metadata event
        (session_id / citations / comparison_mode / chunks), one {delta} event
        per text chunk, and a final {done: True} event. Falls back to a single
        non-streamed invoke when the provider does not support streaming.
        """
        retrieval_ms, prompt_messages, merged, citations, want_citations, compare_mode = (
            self.__prepare(db, query, session_id, top_k)
        )
        if not prompt_messages:
            yield {
                "session_id": session_id,
                "citations": [],
                "include_citations": False,
                "comparison_mode": compare_mode,
                "chunks": 0,
            }
            yield {"delta": _FALLBACK_NO_CONTEXT}
            QueryLogRepository().create(
                db,
                session_id=session_id,
                prompt=query,
                generated_response=_FALLBACK_NO_CONTEXT,
                citations=[],
            )
            logger.info(
                "rag stream fallback session=%s chunks=0 comparison_mode=%s",
                session_id,
                compare_mode,
            )
            yield {"done": True}
            return
        yield {
            "session_id": session_id,
            "citations": citations if want_citations else [],
            "include_citations": want_citations,
            "comparison_mode": compare_mode,
            "chunks": len(merged),
        }

        collected: list[str] = []
        first_token_ms: float | None = None
        start = time.perf_counter()
        try:
            for chunk in self.__llm.stream(prompt_messages):
                text = getattr(chunk, "content", None)
                if not isinstance(text, str) or not text:
                    continue
                if first_token_ms is None:
                    first_token_ms = (time.perf_counter() - start) * 1000
                collected.append(text)
                yield {"delta": text}
        except Exception as exc:  # provider refused streaming -> fall back once
            logger.warning("RAG LLM stream unavailable; falling back to invoke: %s", exc)
            response = self.__invoke_llm(prompt_messages)
            text = getattr(response, "content", "") or ""
            collected = [text]
            yield {"delta": text}
        llm_ms = (time.perf_counter() - start) * 1000

        generated_response = "".join(collected)
        QueryLogRepository().create(
            db,
            session_id=session_id,
            prompt=query,
            generated_response=generated_response,
            citations=citations,
        )
        logger.info(
            "rag stream session=%s chunks=%d retrieval_ms=%.1f first_token_ms=%.1f llm_ms=%.1f total_ms=%.1f",
            session_id,
            len(merged),
            retrieval_ms,
            first_token_ms or 0.0,
            llm_ms,
            retrieval_ms + llm_ms,
        )
        yield {"done": True}

    def __prepare(
        self,
        db: Session,
        query: str,
        session_id: int,
        top_k: int | None = None,
    ) -> tuple[float, list[dict[str, str]], list[Document], list[dict[str, Any]], bool, bool]:
        """Run intent detection + RAG retrieval and build the LLM prompt.

        Returns (retrieval_ms, prompt_messages, retrieved_documents, citations,
        want_citations, compare_mode).
        """
        limit = top_k or self.__settings.top_k_chunks
        compare_mode, want_citations, execute_mode = self.__detect_intent(query)
        target_filter = self.__detect_target_file(db, query, session_id)

        # Broad requests (summarise/explain) need more context to be complete.
        if execute_mode:
            limit = max(limit, min(self.__settings.top_k_chunks * 2, 16))

        # Default: only the active session. Comparison: span every session. When
        # the user names a specific document, isolate retrieval to THAT document.
        retrieval_session_id = None if compare_mode else session_id

        start = time.perf_counter()
        relevant_documents = self.__vector_store.similarity_search(
            query,
            self.__embedding_provider,
            top_k=limit,
            session_id=retrieval_session_id,
            metadata_filter=target_filter,
        )
        # Hybrid retrieval: always pull the earliest (introduction/background)
        # chunks so a document's opening sections reach the LLM context.
        early_documents = self.__vector_store.earliest_chunks(
            self.__embedding_provider,
            top_k=max(2, limit // 2),
            session_id=retrieval_session_id,
            metadata_filter=target_filter,
        )
        merged = self.__dedupe([*relevant_documents, *early_documents])

        if not merged:
            logger.info(
                "rag no-context session=%s top_k=%d chunks=0 retrieval_ms=%.1f",
                session_id,
                limit,
                (time.perf_counter() - start) * 1000,
            )
            return None

        context_block, citations = self.__build_context(merged, want_citations)
        system_prompt = self.__build_system_prompt(
            compare_mode, want_citations, execute_mode, target_filter is not None
        )
        prompt_messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": f"Question:\n{query}\n\nContext:\n{context_block}",
            },
        ]
        retrieval_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "rag retrieve session=%s top_k=%d chunks=%d retrieval_ms=%.1f",
            session_id, limit, len(merged), retrieval_ms,
        )
        return (
            retrieval_ms,
            prompt_messages,
            merged,
            citations,
            want_citations,
            compare_mode,
        )

    # ------------------------------------------------------------- intent
    def __detect_intent(self, query: str) -> tuple[bool, bool, bool]:
        normalized = query.lower()
        compare = any(keyword in normalized for keyword in _COMPARE_KEYWORDS)
        citations = any(keyword in normalized for keyword in _CITATION_KEYWORDS)
        execute = any(keyword in normalized for keyword in _EXECUTE_KEYWORDS)
        return compare, citations, execute

    def __detect_target_file(
        self, db: Session, query: str, session_id: int
    ) -> dict[str, object] | None:
        """Return a metadata filter when the query names one specific uploaded file.

        Matches on the source file name, its stored label (``Jurnal 3``), its
        ordinal number (e.g. ``jurnal ke-5``), or any listed author name. Returning
        None means no single document was referenced, so retrieval stays scoped to
        the whole session.
        """
        if session_id is None:
            return None
        try:
            sources = DocumentRepository().list_file_sources(db, session_id)
        except Exception:  # noqa: BLE001
            return None

        lowered = query.lower()
        ordinal_match = _SOURCE_ORDINAL_RE.search(lowered)
        ordinal_number = int(ordinal_match.group(2) or ordinal_match.group(3)) if ordinal_match else None

        matched: list[dict[str, object]] = []
        for source in sources:
            candidates = [
                source.get("source_name"),
                source.get("filename"),
                source.get("url"),
                source.get("document_label"),
            ]
            candidates = [str(candidate) for candidate in candidates if candidate]
            name_hit = any(candidate.lower() in lowered for candidate in candidates)
            number_hit = (
                ordinal_number is not None
                and source.get("document_number") == ordinal_number
            )
            authors = source.get("authors")
            author_list = (
                [str(a).lower() for a in authors]
                if isinstance(authors, list)
                else ([str(authors).lower()] if authors else [])
            )
            author_hit = any(author and author in lowered for author in author_list)
            if name_hit or number_hit or author_hit:
                matched.append(source)

        if len(matched) > 1:
            # Resolve to a single target when exactly one ordinal/number matched.
            numbered = [s for s in matched if s.get("document_number") == ordinal_number]
            if ordinal_number is not None and len(numbered) == 1:
                matched = numbered
            else:
                return None
        if len(matched) != 1:
            return None

        source = matched[0]
        if source.get("filename"):
            return {"filename": source["filename"]}
        if source.get("url"):
            return {"url": source["url"]}
        if source.get("document_number") is not None:
            return {"document_number": source["document_number"]}
        return None

    def __build_system_prompt(
        self,
        compare_mode: bool,
        want_citations: bool,
        execute_mode: bool,
        single_file: bool,
    ) -> str:
        lines = [
            "You are a precise research assistant. Answer the user's question using ONLY "
            "the context provided below. Never invent information that is not present in "
            "the context. If the context is insufficient, say so clearly.",
            "LOCKED FALLBACK RULE: If the question canNOT be answered from the provided "
            "context (the information is missing, unrelated, or off-topic), respond with "
            "EXACTLY this single sentence and nothing more: \"" + _FALLBACK_NO_CONTEXT + "\". "
            "Do not add explanations, greetings, or any other text around it.",
        ]
        # Always keep information attributed to its source document; each chunk is
        # prefixed with a source label so you can tell which file it came from.
        lines.append(
            "The context chunks are labelled with their source document. Unless the "
            "user explicitly asks you to compare or combine documents, answer "
            "SEPARATELY for each relevant document and keep their information "
            "distinct. Do not merge facts from different files into a single answer "
            "unless the question asks for that."
        )
        if single_file:
            lines.append(
                "The user is asking about ONE specific document. Base your answer "
                "only on chunks belonging to that document and clearly state which "
                "document you are covering."
            )
        if execute_mode:
            lines.append(
                "The user is asking you to summarise, explain, or describe the uploaded "
                "material. DIRECTLY produce that summary, explanation, or description "
                "from the context right now. Do NOT reply with clarifying or technical "
                "questions (such as asking about file formats like PDF, DOCX, PPTX, TXT, "
                "or URL). Infer the user's intent from their words and give an instant, "
                "organised result (e.g. with short headings or bullets where helpful)."
            )
        if compare_mode:
            lines.append(
                "The user explicitly wants a comparison. Contrast the documents "
                "separately first, then summarise the differences/commonalities."
            )
        if want_citations:
            lines.append(
                "The user explicitly wants citations. Ground each statement with "
                "its source using BOTH a narrative in-text citation and a bracketed "
                "chunk number, for example: \"Menurut Ganesa Heru Sandi & Yulia "
                "Fatma (2023), [1]\" or \"... (Sandi, 2023) [1]\". When several "
                "works cover the same point cite them together, e.g. \"Menurut "
                "Penulis A & Penulis B (2023) dan Penulis C dkk. (2021), ...\". "
                "Prefer to reference JURNAL documents by their label (e.g. \"Jurnal "
                "3\", \"Jurnal ke-5\") so a user can match them by name or ordinal "
                "number, and name authors by their last name (e.g. \"Herlina "
                "Tarigan\"). End the answer with a \"Referensi\" list formatted in "
                "APA 7th edition style using the bibliographic metadata attached to "
                "each chunk: Penulis, A. B., & Penulis, C. D. (Tahun). Judul "
                "artikel. Nama Jurnal, Volume(Nomor), Halaman. DOI. When that "
                "metadata is missing, fall back to the chunk's filename or URL. "
                "Never invent author names, years, volumes, or page numbers that "
                "are not present in the metadata."
            )
        else:
            lines.append(
                "Answer in a natural, flowing way. Do NOT add citation numbers, "
                "square-bracket refs, or a source list unless the question asks for them."
            )
        return " ".join(lines)

    def __dedupe(self, documents: list[Document]) -> list[Document]:
        seen: set[str] = set()
        unique: list[Document] = []
        for document in documents:
            key = document.page_content
            if key in seen:
                continue
            seen.add(key)
            unique.append(document)
        return unique

    def __invoke_llm(self, prompt_messages: list[dict[str, str]]):
        import time

        max_attempts = 4
        base_backoff = 3.0
        for attempt in range(max_attempts):
            try:
                return self.__llm.invoke(prompt_messages)
            except Exception as exc:  # transient 429/5xx from the provider
                if attempt == max_attempts - 1:
                    raise
                time.sleep(base_backoff * (attempt + 1))

    def __build_context(
        self, documents: list[Document], want_citations: bool
    ) -> tuple[str, list[dict[str, Any]]]:
        # Always prefix each chunk with its source so the model can keep documents
        # apart even when the user does not want citation numbers.
        serialized_chunks = []
        citations = []
        for index, document in enumerate(documents, start=1):
            source_reference = self.__describe_source(document.metadata)
            if want_citations:
                serialized_chunks.append(f"[{index}] {document.page_content}\n{source_reference}")
                citations.append(self.__format_citation(index, document.metadata))
            else:
                serialized_chunks.append(f"{source_reference}\n{document.page_content}")
        return "\n\n".join(serialized_chunks), citations

    def __describe_source(self, metadata: dict[str, Any]) -> str:
        label = (
            metadata.get("document_label")
            or metadata.get("filename")
            or metadata.get("url")
            or "unknown source"
        )
        source_type = metadata.get("source_type", "unknown")
        details: list[str] = []
        authors = metadata.get("authors")
        if isinstance(authors, list) and authors:
            details.append(", ".join(str(author) for author in authors))
        elif authors:
            details.append(str(authors))
        year = metadata.get("publication_year")
        if year:
            details.append(str(year))
        journal = metadata.get("journal_name")
        if journal:
            details.append(str(journal))
        volume = metadata.get("volume")
        issue = metadata.get("issue")
        if volume:
            details.append(f"Vol. {volume}" + (f"({issue})" if issue else ""))
        suffix = f" — {', '.join(details)}" if details else ""
        return f"(Source {source_type}: {label}){suffix}"

    def __format_citation(
        self, index: int, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        citation = {
            "index": index,
            "source_type": metadata.get("source_type"),
            "filename": metadata.get("filename"),
            "url": metadata.get("url"),
            "source_name": metadata.get("filename") or metadata.get("url"),
            "document_label": metadata.get("document_label"),
            "document_number": metadata.get("document_number"),
        }
        for key in (
            "authors",
            "publication_year",
            "title",
            "journal_name",
            "volume",
            "issue",
            "pages",
            "doi",
        ):
            value = metadata.get(key)
            if value in (None, "", []):
                continue
            citation[key] = value
        return citation

    def __resolve_model_name(self, app_settings: Settings) -> str:
        return app_settings.openai_model
