"""Orchestrates document ingestion: parse, chunk, embed, and persist to the vector store."""

from dataclasses import replace
from pathlib import Path
from typing import Any

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from ...core.config import Settings, settings
from ...core.embeddings import get_embedding_provider
from ...db.crud import DocumentRepository
from ...db.vector_store import VectorStore, get_vector_store
from .parsers.parser_factory import get_parser, detect_source_type
from .parsers.base_parser import ExtractedDocument
from .security import ContentScanner


class IngestionService:
    def __init__(
        self,
        app_settings: Settings = settings,
        vector_store: VectorStore | None = None,
        embedding_provider: Any | None = None,
        text_scanner: ContentScanner | None = None,
    ):
        self.__settings = app_settings
        self.__embedding_provider = embedding_provider or get_embedding_provider(
            provider=app_settings.embedding_provider,
            api_key=app_settings.openai_api_key or app_settings.google_api_key,
        )
        self.__vector_store = vector_store or get_vector_store()
        self.__text_scanner = text_scanner or ContentScanner()

    def ingest(
        self,
        db: Session,
        source: Path | str,
        session_id: int,
        source_type: str | None = None,
        source_name: str | None = None,
        text_scanner: ContentScanner | None = None,
        pre_extracted: ExtractedDocument | None = None,
    ) -> list[str]:
        """Parse, scan, chunk, embed, persist to SQLite, and return stored ids.

        ``pre_extracted`` may be supplied when the caller already parsed and
        scanned the source (e.g. to validate before creating a session); when
        absent the source is parsed and scanned here instead.
        """
        detected_source_type = source_type or detect_source_type(source)
        extracted_document = pre_extracted or self.__extract(source)
        scanner = text_scanner or self.__text_scanner
        scanner.inspect(extracted_document.content_text)
        if source_name and extracted_document.metadata:
            extracted_document = replace(
                extracted_document,
                metadata={**extracted_document.metadata, "filename": source_name},
            )
        documents = self.__chunk(extracted_document)
        metadata_hooks = self.__build_metadata_hooks(extracted_document, documents, detected_source_type)
        vector_ids = self.__vector_store.add_documents(
            documents,
            self.__embedding_provider,
            metadata_hooks,
            session_id=session_id,
        )
        return self.__persist_to_database(
            db, session_id, detected_source_type, extracted_document, documents, vector_ids
        )

    def extract_and_scan(
        self,
        source: Path | str,
        text_scanner: ContentScanner | None = None,
    ) -> ExtractedDocument:
        """Parse and run content inspection WITHOUT touching any session/database.

        Raises :class:`app.services.ingestion.security.ValidationError` when the
        extracted text triggers the content scanner, so callers can reject the
        upload before a session is created or any state is recorded.
        """
        extracted = self.__extract(source)
        scanner = text_scanner or self.__text_scanner
        scanner.inspect(extracted.content_text)
        return extracted

    def __extract(self, source: Path | str) -> ExtractedDocument:
        parser = get_parser(source)
        return parser.parse(source)

    def __build_splitter(self) -> RecursiveCharacterTextSplitter:
        # Smaller chunks with a modest overlap give even, page-spanning coverage
        # so sections at the start and middle of a document are indexed as well
        # as reference-heavy tail text.
        return RecursiveCharacterTextSplitter(
            chunk_size=self.__settings.chunk_size,
            chunk_overlap=self.__settings.chunk_overlap,
            separators=[
                "\n\n",
                "\n",
                ". ",
                "! ",
                "? ",
                "; ",
                ": ",
                ", ",
                " ",
                "",
            ],
        )

    def __chunk(self, extracted_document: ExtractedDocument) -> list[Document]:
        splitter = self.__build_splitter()

        # Page-aware chunking: process each page independently so no page is
        # dropped, ordering is preserved, and each chunk is tagged with the page
        # it came from. This keeps introduction/body pages indexed evenly.
        if extracted_document.pages:
            documents: list[Document] = []
            for page_index, page_text in enumerate(
                extracted_document.pages, start=1
            ):
                if not page_text.strip():
                    continue
                for chunk_text in splitter.split_text(page_text):
                    documents.append(
                        Document(
                            page_content=chunk_text,
                            metadata={"page_number": page_index},
                        )
                    )
            if documents:
                return documents

        # Fallback for parsers that only expose the whole text.
        chunk_texts = splitter.split_text(extracted_document.content_text)
        return [Document(page_content=chunk_text) for chunk_text in chunk_texts]

    def __persist_to_database(
        self,
        db: Session,
        session_id: int,
        source_type: str,
        extracted_document: ExtractedDocument,
        documents: list[Document],
        vector_ids: list[str],
    ) -> list[str]:
        repository = DocumentRepository()
        stored_document_ids = []
        for chunk, vector_id in zip(documents, vector_ids):
            chunk_metadata = {
                **extracted_document.metadata,
                **chunk.metadata,
                "chunk_index": len(stored_document_ids),
            }
            document = repository.create(
                db,
                session_id=session_id,
                source_type=source_type,
                content_text=chunk.page_content,
                doc_metadata=chunk_metadata,
                vector_id=vector_id,
            )
            stored_document_ids.append(str(document.id))
        return stored_document_ids

    def __build_metadata_hooks(
        self,
        extracted_document: ExtractedDocument,
        documents: list[Document],
        source_type: str,
    ) -> list[dict[str, Any]]:
        base_metadata = {"source_type": source_type, **extracted_document.metadata}
        return [
            {**base_metadata, **document.metadata} for document in documents
        ]
