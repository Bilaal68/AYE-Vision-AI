"""AI Surveillance Copilot API endpoints.

Provides conversational AI access to surveillance data through
natural-language queries powered by Google Gemini with tool-use capabilities.
"""

from __future__ import annotations

import json
import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.middleware.auth import JWTBearer, TokenPayload
from app.models.user import User
from app.schemas.copilot import (
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    CopilotChatRequest,
    CopilotChatResponse,
    CopilotCancelRequest,
    SuggestedQuestionsResponse,
)
from app.schemas.common import ErrorResponse, SuccessResponse
from app.services.copilot_service import CopilotService

from sqlalchemy import select

logger = structlog.stdlib.get_logger(__name__)

router = APIRouter()

# Singleton service instance
_copilot_service: CopilotService | None = None


def _get_copilot_service() -> CopilotService:
    """Return the singleton CopilotService instance."""
    global _copilot_service
    if _copilot_service is None:
        _copilot_service = CopilotService()
    return _copilot_service


# ── Helpers ──────────────────────────────────────────────────────────────────


async def _get_current_user(
    token: TokenPayload = Depends(JWTBearer()),
    db: AsyncSession = Depends(get_db_session),
) -> User:
    """Load the authenticated user from the JWT token."""
    result = await db.execute(
        select(User).where(User.id == uuid.UUID(token.sub), User.is_active.is_(True))
    )
    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated.",
        )
    return user


# ── POST /chat ─────────────────────────────────────────────────────────────


@router.post(
    "/chat",
    response_model=SuccessResponse,
    summary="Send a message to the AI Copilot",
    description=(
        "Send a natural-language message to the AI surveillance copilot. "
        "The copilot can query alerts, cameras, analytics, faces, vehicles, "
        "recordings, and system health using real-time data from the platform."
    ),
    responses={
        200: {
            "description": "AI copilot response with optional data cards",
            "content": {
                "application/json": {
                    "example": {
                        "status": "success",
                        "data": {
                            "response_text": "There are **12 alerts** in the last 24 hours...",
                            "conversation_id": "conv_abc123",
                            "data_cards": [],
                            "suggested_followups": [
                                "Show me critical alerts",
                                "Which cameras have the most alerts?",
                            ],
                        },
                    }
                }
            },
        },
        401: {"model": ErrorResponse},
        422: {"model": ErrorResponse},
    },
)
async def chat(
    body: CopilotChatRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Process a user message and return the AI copilot response.

    The copilot uses Google Gemini with tool calling to query real surveillance data
    before generating its natural-language response. Conversations are
    stored in Redis and can be continued by providing a conversation_id.
    """
    service = _get_copilot_service()

    logger.info(
        "Copilot chat request",
        user_id=str(user.id),
        org_id=str(user.org_id),
        conversation_id=body.conversation_id,
        message_length=len(body.message),
    )

    result = await service.chat(
        db=db,
        org_id=user.org_id,
        user=user,
        user_id=user.id,
        message=body.message,
        conversation_id=body.conversation_id,
    )

    return {
        "status": "success",
        "data": {
            "response_text": result["response_text"],
            "summary_sentence": result.get("summary_sentence", ""),
            "conversation_id": result["conversation_id"],
            "data_cards": result["data_cards"],
            "suggested_followups": result["suggested_followups"],
        },
    }


# ── POST /chat/stream ──────────────────────────────────────────────────────


@router.post(
    "/chat/stream",
    summary="Stream multi-step agent reasoning, tool execution, and response",
    description=(
        "Stream progress events (step progress, tool calls) and final answer "
        "as Server-Sent Events (SSE) for the AYE AI agent."
    ),
)
async def chat_stream(
    body: CopilotChatRequest,
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Stream multi-step agent tool execution events and response over SSE."""
    service = _get_copilot_service()

    logger.info(
        "Copilot chat stream request",
        user_id=str(user.id),
        org_id=str(user.org_id),
        conversation_id=body.conversation_id,
        message_length=len(body.message),
    )

    async def event_generator():
        try:
            async for chunk in service.chat_stream(
                db=db,
                org_id=user.org_id,
                user=user,
                user_id=user.id,
                message=body.message,
                conversation_id=body.conversation_id,
            ):
                event_type = chunk.get("event", "message")
                data_json = json.dumps(chunk, default=str)
                yield f"event: {event_type}\ndata: {data_json}\n\n"
        except Exception as exc:
            logger.exception("Error during agent stream", error=str(exc))
            err_payload = json.dumps({"error": str(exc)})
            yield f"event: error\ndata: {err_payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── POST /chat/cancel ──────────────────────────────────────────────────────


@router.post(
    "/chat/cancel",
    response_model=SuccessResponse,
    summary="Hard stop / cancel active copilot run",
    description="Immediately aborts the current agent multi-step run.",
)
async def cancel_chat(
    body: CopilotCancelRequest,
    user: User = Depends(_get_current_user),
) -> dict:
    """Immediately stop an in-progress agent run."""
    service = _get_copilot_service()
    await service.cancel_conversation(body.conversation_id)
    return {
        "status": "success",
        "data": {"conversation_id": body.conversation_id},
        "message": "Cancellation signal dispatched.",
    }


# ── GET /conversations ─────────────────────────────────────────────────────


@router.get(
    "/conversations",
    response_model=SuccessResponse,
    summary="List user's copilot conversations",
    description="Retrieve a list of all past copilot conversations for the current user.",
    responses={401: {"model": ErrorResponse}},
)
async def list_conversations(
    user: User = Depends(_get_current_user),
) -> dict:
    """Return all conversation summaries for the authenticated user."""
    service = _get_copilot_service()
    conversations = await service.get_conversations(user.id)

    return {
        "status": "success",
        "data": conversations,
    }


# ── GET /conversations/{conversation_id} ───────────────────────────────────


@router.get(
    "/conversations/{conversation_id}",
    response_model=SuccessResponse,
    summary="Get conversation messages",
    description="Retrieve the full message history for a specific conversation.",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(_get_current_user),
) -> dict:
    """Return all messages in a conversation."""
    service = _get_copilot_service()
    detail = await service.get_conversation_detail(user.id, conversation_id)

    if detail is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    return {
        "status": "success",
        "data": detail,
    }


# ── DELETE /conversations/{conversation_id} ────────────────────────────────


@router.delete(
    "/conversations/{conversation_id}",
    response_model=SuccessResponse,
    summary="Delete a conversation",
    description="Permanently delete a copilot conversation and all its messages.",
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(_get_current_user),
) -> dict:
    """Delete a conversation by ID."""
    service = _get_copilot_service()
    deleted = await service.delete_conversation(user.id, conversation_id)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )

    return {
        "status": "success",
        "data": None,
        "message": "Conversation deleted successfully.",
    }


# ── GET /suggestions ──────────────────────────────────────────────────────


@router.get(
    "/suggestions",
    response_model=SuccessResponse,
    summary="Get suggested questions",
    description=(
        "Get context-aware suggested questions based on the current "
        "system state (offline cameras, unresolved alerts, etc.)."
    ),
    responses={401: {"model": ErrorResponse}},
)
async def get_suggestions(
    user: User = Depends(_get_current_user),
    db: AsyncSession = Depends(get_db_session),
) -> dict:
    """Return suggested questions for the copilot interface."""
    service = _get_copilot_service()
    suggestions = await service.get_suggested_questions(db, user.org_id)

    return {
        "status": "success",
        "data": suggestions,
    }
