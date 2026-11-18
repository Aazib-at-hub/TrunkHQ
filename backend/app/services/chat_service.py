"""
TrunkHQ — Chat & Question Answering Service.

Orchestrates multi-turn RAG chat sessions scoped to repositories,
grounded generation, citation tracking, and message persistence.
"""

from __future__ import annotations

import re
from typing import Optional, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.decision import get_decision_service
from app.embeddings import get_embedding_service
from app.llm import get_llm_service
from app.models.conversation import Conversation
from app.models.document import Document, DocumentChunk
from app.models.message import Message, MessageSource
from app.rag.generator import RAGGenerator
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.repository_repo import RepositoryRepository
from app.retrieval.retriever import RetrieverService

logger = get_logger("chat_service")

_STOPWORDS = {
    "what", "where", "when", "which", "whose", "whom", "how", "does", "did",
    "doing", "done", "have", "has", "had", "will", "would", "could", "should",
    "can", "may", "might", "must", "need", "want", "tell", "show", "explain",
    "describe", "find", "list", "give", "make", "work", "works", "working",
    "used", "using", "uses", "this", "that", "these", "those", "with", "from",
    "into", "about", "there", "their", "them", "they", "then", "than", "some",
    "code", "file", "files", "function", "functions", "class", "classes",
    "method", "methods", "module", "modules", "repo", "repository", "project",
}


def extract_query_entities(question: str, max_entities: int = 5) -> list[str]:
    """
    Extract likely code symbols, file paths, and technical identifiers from a user question.

    Prioritizes backticked identifiers, file paths, CamelCase, snake_case, and dotted
    references before falling back to non-stopword technical tokens.
    """
    candidates: list[str] = []
    seen: set[str] = set()

    def _add(token: str) -> None:
        cleaned = token.strip("`\"'?,.:;()[]{}<>")
        if len(cleaned) < 2:
            return
        lowered = cleaned.lower()
        if lowered in _STOPWORDS or lowered in seen:
            return
        seen.add(lowered)
        candidates.append(cleaned)

    # 1. Backticked code spans
    for m in re.finditer(r"`([^`]+)`", question):
        for part in m.group(1).split():
            _add(part)

    # 2. File paths (e.g. app/services/chat_service.py)
    for m in re.finditer(r"\b(?:[a-zA-Z0-9_.-]+/)+[a-zA-Z0-9_.-]+\b", question):
        _add(m.group(0))

    # 3. Dotted qualified names (e.g. GraphRepository.search_nodes)
    for m in re.finditer(r"\b[a-zA-Z_][a-zA-Z0-9_]*(?:\.[a-zA-Z_][a-zA-Z0-9_]*)+\b", question):
        full = m.group(0)
        _add(full)
        _add(full.rsplit(".", 1)[-1])

    # 4. snake_case identifiers
    for m in re.finditer(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b", question):
        _add(m.group(0))

    # 5. CamelCase / PascalCase identifiers
    for m in re.finditer(r"\b(?:[A-Z][a-z0-9]+){2,}\b|\b[a-z]+[A-Z][a-zA-Z0-9]*\b", question):
        _add(m.group(0))

    # 6. Fallback to remaining non-stopword tokens (length >= 3)
    for raw in question.split():
        tok = raw.strip("`\"'?,.:;()[]{}<>")
        if len(tok) >= 3 and tok.lower() not in _STOPWORDS:
            _add(tok)

    return candidates[:max_entities]


class ChatService:
    """Business operations for repository RAG conversations."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._repo_dao = RepositoryRepository(session)
        self._conv_dao = ConversationRepository(session)
        self._msg_dao = MessageRepository(session)
        self._graph_dao = GraphRepository(session)
        self._settings = get_settings()

    async def ask_question(
        self,
        user_id: UUID,
        repository_id: UUID,
        question: str,
        conversation_id: Optional[UUID] = None,
        context_mode: str = "rag",
        organization_id: Optional[UUID] = None,
    ) -> tuple[Conversation, Message, list[MessageSource]]:
        """
        Execute RAG question-answering workflow on repository.

        Returns:
            tuple[Conversation, assistant Message, list[MessageSource]]
        """
        # 1. Verify repository exists & is ready within active organization
        repo = (
            await self._repo_dao.get_by_id_in_org(repository_id, organization_id)
            if organization_id is not None
            else await self._repo_dao.get_by_id_shared(repository_id)
        )
        if not repo:
            raise NotFoundError("Repository not found")

        if repo.status != "READY":
            raise ValidationError(
                f"Repository cannot be queried while status is '{repo.status}'. Must be 'READY'."
            )

        # 2. Get or create conversation
        if conversation_id:
            conv = await self._conv_dao.get_by_id(conversation_id, user_id)
            if not conv or conv.repository_id != repository_id:
                raise NotFoundError("Conversation not found for this repository")
        else:
            # Create new conversation with auto-title from question
            title_snippet = question.strip()[:60]
            conv = Conversation(
                user_id=user_id,
                organization_id=organization_id,
                repository_id=repository_id,
                title=title_snippet,
            )
            conv = await self._conv_dao.create(conv)

        # 3. Save user message
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=question,
        )
        await self._msg_dao.create_message(user_msg)

        # 4. Retrieve context
        embedding_service = get_embedding_service()
        retriever = RetrieverService(self._session, embedding_service)
        chunks = await retriever.retrieve(
            repository_id=repository_id,
            query=question,
            top_k=self._settings.top_k,
            similarity_threshold=self._settings.similarity_threshold,
        )

        # 5. Filter/rank with Decision layer
        decision_service = get_decision_service()
        ranked_chunks = await decision_service.filter_and_rank(question, chunks)

        # 5b. Graph-enhanced reasoning context extraction (Level 2)
        graph_context: Optional[str] = None
        if context_mode == "graph_enhanced":
            from app.graph.reasoning import GraphReasoningService

            entities = extract_query_entities(question)
            graph_context = await GraphReasoningService(self._session).build_query_graph_context(
                workspace_id=repo.user_id,
                repository_id=repository_id,
                question=question,
                entities=entities,
            )

        # 5b. Retrieve project documentation context (Phase 6)
        document_context: Optional[str] = None
        if getattr(repo, "project_id", None) and getattr(repo, "organization_id", None):
            try:
                from sqlalchemy import select

                query_emb = get_embedding_service().embed_text(question)
                dist_expr = DocumentChunk.embedding.cosine_distance(query_emb)
                doc_stmt = (
                    select(
                        Document.title,
                        Document.file_name,
                        DocumentChunk.section_title,
                        DocumentChunk.page_number,
                        DocumentChunk.content,
                    )
                    .join(Document, Document.id == DocumentChunk.document_id)
                    .where(
                        DocumentChunk.project_id == repo.project_id,
                        DocumentChunk.organization_id == repo.organization_id,
                        Document.status == "READY",
                    )
                    .order_by(dist_expr)
                    .limit(4)
                )
                doc_res = await self._session.execute(doc_stmt)
                doc_rows = doc_res.all()
                if doc_rows:
                    doc_parts = []
                    for d_title, d_file, sec, page, d_content in doc_rows:
                        loc = f"Page {page}" if page else (sec or d_file)
                        doc_parts.append(f"[Doc: {d_title} ({d_file} · {loc})]\n{d_content}")
                    document_context = "\n\n".join(doc_parts)
            except Exception as exc:
                logger.warning("Document context retrieval skipped", error=str(exc))

        # 6. Load recent conversation history & generate answer
        prior_messages = await self._msg_dao.list_by_conversation(conv.id)
        history_turns = [
            (m.role, m.content)
            for m in prior_messages
            if m.id != user_msg.id
        ][-6:]

        llm_service = get_llm_service()
        generator = RAGGenerator(llm_service)
        rag_output = await generator.generate_answer(
            question=question,
            retrieved_chunks=ranked_chunks,
            graph_context=graph_context,
            history=history_turns,
            document_context=document_context,
        )

        # 7. Persist assistant message & citations
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=rag_output.answer,
        )
        saved_assistant_msg = await self._msg_dao.create_message(assistant_msg)

        source_entities: list[MessageSource] = []
        for cite in rag_output.citations:
            source = MessageSource(
                message_id=saved_assistant_msg.id,
                chunk_id=cite.chunk_id,
                file_path=cite.file_path,
                start_line=cite.start_line,
                end_line=cite.end_line,
                similarity_score=cite.similarity_score,
            )
            source_entities.append(source)

        if source_entities:
            await self._msg_dao.create_sources_batch(source_entities)

        if organization_id is not None:
            try:
                from app.repositories.billing_repo import BillingRepository

                await BillingRepository(self._session).record_usage(
                    organization_id=organization_id,
                    metric="ai_queries",
                    quantity=1,
                )
            except Exception as exc:
                logger.warning("Usage metering skipped", error=str(exc))

        await self._session.commit()

        # Preload sources for response formatting
        saved_assistant_msg.sources = source_entities

        return conv, saved_assistant_msg, source_entities

    async def list_conversations(
        self,
        repository_id: UUID,
        user_id: UUID,
        organization_id: Optional[UUID] = None,
    ) -> Sequence[Conversation]:
        """List user's conversations for given repository."""
        repo = (
            await self._repo_dao.get_by_id_in_org(repository_id, organization_id)
            if organization_id is not None
            else await self._repo_dao.get_by_id_shared(repository_id)
        )
        if not repo:
            raise NotFoundError("Repository not found")
        return await self._conv_dao.list_by_repository(repository_id, user_id)

    async def get_conversation(
        self, conversation_id: UUID, user_id: UUID
    ) -> Conversation:
        """Fetch conversation details with full message history."""
        conv = await self._conv_dao.get_by_id(conversation_id, user_id)
        if not conv:
            raise NotFoundError("Conversation not found")
        return conv

    async def delete_conversation(self, conversation_id: UUID, user_id: UUID) -> None:
        """Delete conversation."""
        deleted = await self._conv_dao.delete(conversation_id, user_id)
        if not deleted:
            raise NotFoundError("Conversation not found")
        await self._session.commit()
