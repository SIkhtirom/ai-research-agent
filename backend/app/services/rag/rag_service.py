"""RAG pipeline: retrieve relevant chunks, synthesise an answer, and cite sources.

Context isolation: by default the assistant only reasons about the CURRENT
session's documents. When the user explicitly asks for a comparison (e.g.
"bandingkan dengan jurnal sebelumnya") retrieval is widened to every session so
previous work can be pulled back in. Citation markers/source lists are only
emitted when the user explicitly asks for citations.
"""

from typing import Any

from langchain_core.documents import Document
from sqlalchemy.orm import Session

from ...core.config import Settings, settings
from ...core.embeddings import get_embedding_provider
from ...core.llm import get_llm
from ...db.crud import DocumentRepository, QueryLogRepository
from ...db.vector_store import VectorStore, get_vector_store

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
    "sitasi",
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
        limit = top_k or self.__settings.top_k_chunks
        compare_mode, want_citations, execute_mode = self.__detect_intent(query)
        target_filter = self.__detect_target_file(db, query, session_id)

        # Broad requests (summarise/explain) need more context to be complete.
        if execute_mode:
            limit = max(limit, min(self.__settings.top_k_chunks * 2, 16))

        # Default: only the active session. Comparison: span every session. When
        # the user names a specific document, isolate retrieval to THAT document.
        retrieval_session_id = None if compare_mode else session_id

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
        response = self.__invoke_llm(prompt_messages)
        generated_response = response.content
        QueryLogRepository().create(
            db,
            session_id=session_id,
            prompt=query,
            generated_response=generated_response,
            citations=citations,
        )
        return {
            "generated_response": generated_response,
            "citations": citations if want_citations else [],
            "include_citations": want_citations,
            "comparison_mode": compare_mode,
        }

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

        When the user mentions a particular document (by its file name or URL),
        retrieval is isolated to that document so the answer is not contaminated
        by other files in the session. Returns None when no single file is named.
        """
        if session_id is None:
            return None
        try:
            sources = DocumentRepository().list_file_sources(db, session_id)
        except Exception:  # noqa: BLE001
            return None

        lowered = query.lower()
        matched: list[dict[str, object]] = []
        for source in sources:
            name = source.get("source_name")
            filename = source.get("filename")
            url = source.get("url")
            candidates = [candidate for candidate in (name, filename, url) if candidate]
            if any(str(candidate).lower() in lowered for candidate in candidates):
                matched.append(source)

        # Only isolate when exactly ONE distinct file is referenced. If several
        # are mentioned (e.g. a comparison), fall back to the full session so the
        # model can still separate outputs via context labelling.
        if len(matched) != 1:
            return None

        source = matched[0]
        if source.get("filename"):
            return {"filename": source["filename"]}
        if source.get("url"):
            return {"url": source["url"]}
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
                "The user explicitly wants citations. Ground each claim with the source "
                "number in brackets, for example [1], [2], and list every cited source."
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
        source_name = metadata.get("filename") or metadata.get("url") or "unknown source"
        source_type = metadata.get("source_type", "unknown")
        return f"(Source {source_type}: {source_name})"

    def __format_citation(
        self, index: int, metadata: dict[str, Any]
    ) -> dict[str, Any]:
        return {
            "index": index,
            "source_type": metadata.get("source_type"),
            "filename": metadata.get("filename"),
            "url": metadata.get("url"),
            "source_name": metadata.get("filename") or metadata.get("url"),
        }

    def __resolve_model_name(self, app_settings: Settings) -> str:
        return app_settings.openai_model
