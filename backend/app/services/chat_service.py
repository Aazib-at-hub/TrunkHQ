"""
Cortex Engineering — Chat & Question Answering Service.

Orchestrates multi-turn RAG chat sessions scoped to repositories,
grounded generation, citation tracking, and message persistence.
"""

from __future__ import annotations

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
from app.models.message import Message, MessageSource
from app.rag.generator import RAGGenerator
from app.repositories.conversation_repo import ConversationRepository
from app.repositories.graph_repo import GraphRepository
from app.repositories.message_repo import MessageRepository
from app.repositories.repository_repo import RepositoryRepository
from app.retrieval.retriever import RetrieverService

logger = get_logger("chat_service")


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
    ) -> tuple[Conversation, Message, list[MessageSource]]:
        """
        Execute RAG question-answering workflow on repository.

        Returns:
            tuple[Conversation, assistant Message, list[MessageSource]]
        """
        # 1. Enforce repository ownership & readiness
        repo = await self._repo_dao.get_by_id(repository_id, user_id)
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

        # 5b. Graph-enhanced context extraction
        graph_context: Optional[str] = None
        if context_mode == "graph_enhanced":
            graph_lines: list[str] = []
            words = [w.strip("?,.:;()[]\"'") for w in question.split() if len(w) > 3]
            matched_nodes = []
            for word in words[:4]:
                found = await self._graph_dao.search_nodes(
                    workspace_id=user_id,
                    repository_id=repository_id,
                    query=word,
                    limit=2,
                )
                matched_nodes.extend(found)

            seen_ids = set()
            for node in matched_nodes[:3]:
                if node.id in seen_ids:
                    continue
                seen_ids.add(node.id)
                nbrs = await self._graph_dao.get_neighbors(
                    workspace_id=user_id,
                    node_id=node.id,
                    limit=10,
                )
                graph_lines.append(f"Entity: {node.name} ({node.node_type}) at {node.source_uri or 'unknown'}")
                for out_e in nbrs["outgoing_edges"][:5]:
                    tgt_name = next((n.name for n in nbrs["neighbors"] if n.id == out_e.target_node_id), str(out_e.target_node_id))
                    graph_lines.append(f"  - [{out_e.edge_type}] -> {tgt_name} (confidence={out_e.confidence})")
                for in_e in nbrs["incoming_edges"][:5]:
                    src_name = next((n.name for n in nbrs["neighbors"] if n.id == in_e.source_node_id), str(in_e.source_node_id))
                    graph_lines.append(f"  - <- [{in_e.edge_type}] from {src_name} (confidence={in_e.confidence})")

            if graph_lines:
                graph_context = "\n".join(graph_lines)

        # 6. Generate answer
        llm_service = get_llm_service()
        generator = RAGGenerator(llm_service)
        rag_output = await generator.generate_answer(
            question=question,
            retrieved_chunks=ranked_chunks,
            graph_context=graph_context,
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

        await self._session.commit()

        # Preload sources for response formatting
        saved_assistant_msg.sources = source_entities

        return conv, saved_assistant_msg, source_entities

    async def list_conversations(
        self, repository_id: UUID, user_id: UUID
    ) -> Sequence[Conversation]:
        """List user's conversations for given repository."""
        repo = await self._repo_dao.get_by_id(repository_id, user_id)
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
