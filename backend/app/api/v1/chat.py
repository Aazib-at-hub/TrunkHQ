"""
TrunkHQ — Chat API Routes.

Endpoints for asking questions via RAG, listing conversations,
viewing message histories with source citations, and deleting conversations.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import TenantContext, get_current_user_id, get_tenant_context
from app.database.session import get_db
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationDetailResponse,
    ConversationResponse,
    MessageResponse,
    SourceResponse,
)
from app.services.chat_service import ChatService

router = APIRouter(tags=["Chat"])


@router.post(
    "/repositories/{repo_id}/chat",
    response_model=ChatResponse,
    summary="Ask a question about a repository (RAG)",
)
async def chat_with_repository(
    repo_id: UUID,
    data: ChatRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Ask a question against the indexed repository codebase."""
    service = ChatService(db)
    conv, assistant_msg, sources = await service.ask_question(
        user_id=tenant.user_id,
        repository_id=repo_id,
        question=data.question,
        conversation_id=data.conversation_id,
        context_mode=data.context_mode,
        organization_id=tenant.organization_id,
    )

    msg_resp = MessageResponse(
        id=assistant_msg.id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        sources=[SourceResponse.model_validate(s) for s in sources],
        created_at=assistant_msg.created_at,
    )

    return ChatResponse(
        conversation_id=conv.id,
        message=msg_resp,
    )


@router.post(
    "/repositories/{repo_id}/chat/stream",
    summary="Stream RAG chat response over Server-Sent Events (SSE)",
)
async def stream_chat_with_repository(
    repo_id: UUID,
    data: ChatRequest,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Execute RAG Q&A and stream sources, answer tokens, and completion metadata."""
    service = ChatService(db)
    conv, assistant_msg, sources = await service.ask_question(
        user_id=tenant.user_id,
        repository_id=repo_id,
        question=data.question,
        conversation_id=data.conversation_id,
        context_mode=data.context_mode,
        organization_id=tenant.organization_id,
    )

    msg_resp = MessageResponse(
        id=assistant_msg.id,
        role=assistant_msg.role,
        content=assistant_msg.content,
        sources=[SourceResponse.model_validate(s) for s in sources],
        created_at=assistant_msg.created_at,
    )

    async def _event_stream():
        yield f"data: {json.dumps({'type': 'sources', 'sources': [s.model_dump(mode='json') for s in msg_resp.sources]})}\n\n"
        text = assistant_msg.content or ""
        chunk_size = 24
        for idx in range(0, len(text), chunk_size):
            yield f"data: {json.dumps({'type': 'token', 'text': text[idx : idx + chunk_size]})}\n\n"
        yield f"data: {json.dumps({'type': 'done', 'conversation_id': str(conv.id), 'message': msg_resp.model_dump(mode='json')})}\n\n"

    return StreamingResponse(
        _event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.get(
    "/repositories/{repo_id}/conversations",
    response_model=list[ConversationResponse],
    summary="List conversations for repository",
)
async def list_conversations(
    repo_id: UUID,
    tenant: TenantContext = Depends(get_tenant_context),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationResponse]:
    """Retrieve all conversations belonging to given repository."""
    service = ChatService(db)
    convs = await service.list_conversations(
        repo_id, tenant.user_id, organization_id=tenant.organization_id
    )
    return [
        ConversationResponse(
            id=c.id,
            repository_id=c.repository_id,
            title=c.title,
            created_at=c.created_at,
            updated_at=c.updated_at,
            message_count=len(c.messages) if hasattr(c, "messages") and c.messages else 0,
        )
        for c in convs
    ]


@router.get(
    "/conversations/{conv_id}",
    response_model=ConversationDetailResponse,
    summary="Get conversation detail with messages",
)
async def get_conversation(
    conv_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> ConversationDetailResponse:
    """Retrieve full message history and citations for conversation."""
    service = ChatService(db)
    conv = await service.get_conversation(conv_id, current_user_id)

    formatted_messages: list[MessageResponse] = []
    for m in conv.messages:
        formatted_messages.append(
            MessageResponse(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=[SourceResponse.model_validate(s) for s in m.sources] if m.sources else [],
                created_at=m.created_at,
            )
        )

    return ConversationDetailResponse(
        id=conv.id,
        repository_id=conv.repository_id,
        title=conv.title,
        messages=formatted_messages,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
    )


@router.delete(
    "/conversations/{conv_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Delete conversation",
)
async def delete_conversation(
    conv_id: UUID,
    current_user_id: UUID = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Delete a conversation and its messages."""
    service = ChatService(db)
    await service.delete_conversation(conv_id, current_user_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
