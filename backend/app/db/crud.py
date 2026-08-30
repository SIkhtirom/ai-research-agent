"""Basic repository with Create and Read operations for the relational models."""

from sqlalchemy.orm import Session

from ..models import Document, QueryLog, ResearchSession
from .database import dumps_json


class SessionRepository:
    def create(self, db: Session, user_id: str, title: str) -> ResearchSession:
        new_session = ResearchSession(user_id=user_id, title=title)
        db.add(new_session)
        db.commit()
        db.refresh(new_session)
        return new_session

    def get_by_id(self, db: Session, session_id: int) -> ResearchSession | None:
        return db.get(ResearchSession, session_id)

    def list_by_user(self, db: Session, user_id: str) -> list[ResearchSession]:
        return (
            db.query(ResearchSession)
            .filter(ResearchSession.user_id == user_id)
            .order_by(ResearchSession.created_at.desc())
            .all()
        )


class DocumentRepository:
    def create(
        self,
        db: Session,
        session_id: int,
        source_type: str,
        content_text: str,
        doc_metadata: dict | None = None,
        vector_id: str | None = None,
    ) -> Document:
        new_document = Document(
            session_id=session_id,
            source_type=source_type,
            content_text=content_text,
            doc_metadata=dumps_json(doc_metadata or {}),
            vector_id=vector_id,
        )
        db.add(new_document)
        db.commit()
        db.refresh(new_document)
        return new_document

    def list_by_session(self, db: Session, session_id: int) -> list[Document]:
        return (
            db.query(Document)
            .filter(Document.session_id == session_id)
            .order_by(Document.created_at.asc())
            .all()
        )

    def delete_by_session(self, db: Session, session_id: int) -> int:
        """Delete every document of a session and return how many were removed."""
        result = (
            db.query(Document)
            .filter(Document.session_id == session_id)
            .delete(synchronize_session=False)
        )
        db.commit()
        return result

    def get_by_id(self, db: Session, document_id: int) -> Document | None:
        return db.get(Document, document_id)

    def list_file_sources(self, db: Session, session_id: int) -> list[dict]:
        """Return one entry per distinct uploaded source (file or url) for a session,
        with the id of its first chunk for deletion targeting and the chunk count."""
        sources: dict[tuple[str, str | None], dict] = {}
        for document in self.list_by_session(db, session_id):
            metadata = document.metadata_dict
            if document.source_type == "url":
                key = ("url", metadata.get("url"))
            else:
                key = ("file", metadata.get("filename") or f"document-{document.id}")
            existing = sources.get(key)
            if existing is None:
                sources[key] = {
                    "id": document.id,
                    "source_type": document.source_type,
                    "filename": metadata.get("filename"),
                    "url": metadata.get("url"),
                    "source_name": metadata.get("filename")
                    or metadata.get("url")
                    or f"document-{document.id}",
                    "chunk_count": 0,
                }
            sources[key]["chunk_count"] += 1
        return list(sources.values())

    def delete_file_members(
        self, db: Session, session_id: int, metadata_match: dict
    ) -> int:
        """Delete every document chunk of a session whose metadata contains all
        key/value pairs in ``metadata_match`` (e.g. filename). Returns count removed."""
        matching_ids = [
            document.id
            for document in self.list_by_session(db, session_id)
            if all(
                document.metadata_dict.get(key) == value
                for key, value in metadata_match.items()
            )
        ]
        if not matching_ids:
            return 0
        result = (
            db.query(Document)
            .filter(Document.id.in_(matching_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
        return result


class QueryLogRepository:
    def create(
        self,
        db: Session,
        session_id: int,
        prompt: str,
        generated_response: str,
        citations: list[dict],
    ) -> QueryLog:
        new_query_log = QueryLog(
            session_id=session_id,
            prompt=prompt,
            generated_response=generated_response,
            citations=dumps_json(citations),
        )
        db.add(new_query_log)
        db.commit()
        db.refresh(new_query_log)
        return new_query_log

    def list_by_session(self, db: Session, session_id: int) -> list[QueryLog]:
        return (
            db.query(QueryLog)
            .filter(QueryLog.session_id == session_id)
            .order_by(QueryLog.created_at.desc())
            .all()
        )

    def get_by_id(self, db: Session, query_log_id: int) -> QueryLog | None:
        return db.get(QueryLog, query_log_id)

