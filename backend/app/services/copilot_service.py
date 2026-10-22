"""AI Surveillance Copilot Service.

Provides a conversational AI interface powered by the Google Gemini API
with tool-calling capabilities for querying surveillance data. Conversations
are persisted in Redis with a configurable TTL.

Usage::

    from app.services.copilot_service import CopilotService

    service = CopilotService()
    response = await service.chat(db, org_id, user_id, "How many alerts today?")
"""

from __future__ import annotations

import asyncio
import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import structlog
from google import genai
from google.genai import errors, types
from sqlalchemy import and_, case, distinct, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.alert import Alert, AlertStatus
from app.models.analytics import DwellRecord, FootfallRecord, HeatmapRecord
from app.models.camera import Camera, CameraHealth, CameraHealthStatus
from app.models.face import FaceEnrollment, FaceEvent
from app.models.organization import Organization
from app.models.person import Person, PersonType
from app.models.recording import Recording
from app.models.rule import Rule, RuleSeverity, RuleType
from app.models.user import User, UserRole
from app.models.vehicle import Vehicle, VehicleEvent, VehicleLog

logger = structlog.stdlib.get_logger(__name__)

# Redis key prefixes
_CONV_PREFIX = "copilot:conv:"
_CONV_LIST_PREFIX = "copilot:convlist:"
_CONV_CANCEL_PREFIX = "copilot:cancel:"
_CONV_TTL = 60 * 60 * 24 * 7  # 7 days

# Maximum number of conversation turns kept in context (10 user + 10 assistant turns = 10 turns per session)
_MAX_HISTORY_TURNS = 20

# Maximum tool calls allowed per single user request
_MAX_TOOL_CALLS = 5


def _utcnow_naive() -> datetime:
    """Return current UTC time as a naive datetime (no tzinfo).

    This is required because the database uses TIMESTAMP WITHOUT TIME ZONE
    columns, so all comparisons must use naive datetimes.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)

# Candidate Gemini models in fallback order
MODELS_TO_TRY = [
    "gemini-flash-lite-latest",      # Ultra-fast endpoint (1-2s response)
    "gemini-3.6-flash",              # Primary active model recommended by Google
    "gemini-3-flash-preview",        # Reliable preview model
    "gemini-3.1-flash-lite-preview", # Ultra-fast, high availability
    "gemini-3.8-flash",              # Next-gen fallback model
]

# Default Gemini model
_DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest"

# Tool declarations exposed to Gemini
_COPILOT_FUNCTION_DECLARATIONS: list[types.FunctionDeclaration] = [
    types.FunctionDeclaration(
        name="query_alerts",
        description=(
            "Query alert records for the organization. "
            "Can filter by severity, type, status, camera, date range, and limit. "
            "Returns a list of matching alerts with counts."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "severity": {
                    "type": "STRING",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Filter by alert severity level.",
                },
                "alert_type": {
                    "type": "STRING",
                    "description": "Filter by alert type (e.g. intrusion_detection, loitering, fire_smoke).",
                },
                "status": {
                    "type": "STRING",
                    "enum": ["new", "acknowledged", "resolved", "false_positive", "escalated"],
                    "description": "Filter by alert status.",
                },
                "camera_name": {
                    "type": "STRING",
                    "description": "Filter by camera name (partial match).",
                },
                "hours_ago": {
                    "type": "INTEGER",
                    "description": "Only include alerts from the last N hours. Defaults to 24.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum number of alerts to return. Defaults to 20.",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="query_cameras",
        description=(
            "Query camera information for the organization. "
            "Returns camera names, statuses (online/offline), locations, "
            "and configuration details."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "status": {
                    "type": "STRING",
                    "enum": ["online", "offline", "all"],
                    "description": "Filter cameras by online status.",
                },
                "name": {
                    "type": "STRING",
                    "description": "Filter by camera name (partial match).",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="query_analytics",
        description=(
            "Query footfall, occupancy, and dwell-time analytics data. "
            "Returns aggregated counts and trends for the requested period."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "metric": {
                    "type": "STRING",
                    "enum": ["footfall", "occupancy", "dwell_time"],
                    "description": "Type of analytics metric to query.",
                },
                "camera_name": {
                    "type": "STRING",
                    "description": "Filter by camera name (partial match).",
                },
                "hours_ago": {
                    "type": "INTEGER",
                    "description": "Query data from the last N hours. Defaults to 24.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum records to return. Defaults to 20.",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="query_faces",
        description=(
            "Search the enrolled face database and recent face recognition events. "
            "Can search by person name, type (employee, visitor, blacklisted), "
            "or recent events."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "search_type": {
                    "type": "STRING",
                    "enum": ["enrolled", "events"],
                    "description": "Search enrolled persons or recent face events.",
                },
                "person_name": {
                    "type": "STRING",
                    "description": "Filter by person name (partial match).",
                },
                "person_type": {
                    "type": "STRING",
                    "enum": ["employee", "visitor", "vip", "blacklisted", "contractor", "student"],
                    "description": "Filter by person type.",
                },
                "hours_ago": {
                    "type": "INTEGER",
                    "description": "For events: only include events from the last N hours.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum records to return. Defaults to 20.",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="query_vehicles",
        description=(
            "Search the vehicle database and recent ANPR detection events. "
            "Can search by plate number, category (whitelist, blacklist), "
            "or recent detection events."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "search_type": {
                    "type": "STRING",
                    "enum": ["registered", "events", "logs"],
                    "description": "Search registered vehicles, ANPR events, or entry/exit logs.",
                },
                "plate_number": {
                    "type": "STRING",
                    "description": "Filter by plate number (partial match).",
                },
                "category": {
                    "type": "STRING",
                    "enum": ["whitelist", "blacklist", "visitor", "employee", "vip"],
                    "description": "Filter registered vehicles by category.",
                },
                "hours_ago": {
                    "type": "INTEGER",
                    "description": "For events: only include from the last N hours.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum records to return. Defaults to 20.",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="search_recordings",
        description=(
            "Search video recordings by camera name, time range, "
            "and recording type (continuous or event-triggered)."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "camera_name": {
                    "type": "STRING",
                    "description": "Filter by camera name (partial match).",
                },
                "recording_type": {
                    "type": "STRING",
                    "enum": ["continuous", "event"],
                    "description": "Filter by recording type.",
                },
                "hours_ago": {
                    "type": "INTEGER",
                    "description": "Recordings from the last N hours. Defaults to 24.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum recordings to return. Defaults to 10.",
                },
            },
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="get_system_health",
        description=(
            "Get overall system health status including camera counts, "
            "alert statistics, storage usage, and service status."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {},
            "required": [],
        },
    ),
    types.FunctionDeclaration(
        name="acknowledge_alerts",
        description=(
            "Acknowledge one or more surveillance alerts to mark them as reviewed. "
            "Can accept specific alert UUIDs or filter criteria (camera_name, severity, limit). "
            "Requires operator role or higher. Deletion is never permitted."
        ),
        parameters={
            "type": "OBJECT",
            "properties": {
                "alert_ids": {
                    "type": "ARRAY",
                    "items": {"type": "STRING"},
                    "description": "List of alert UUID strings to mark as acknowledged.",
                },
                "camera_name": {
                    "type": "STRING",
                    "description": "Optional: acknowledge alerts from cameras matching this name.",
                },
                "severity": {
                    "type": "STRING",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Optional: acknowledge alerts of this severity.",
                },
                "limit": {
                    "type": "INTEGER",
                    "description": "Maximum number of alerts to acknowledge (default 10, max 50).",
                },
            },
            "required": [],
        },
    ),
]

# Security Tool Whitelist & Tiers
# Tier 1 (Read / Inspection) - Allowed for all authenticated roles
TIER_1_READ_TOOLS: set[str] = {
    "query_alerts",
    "query_cameras",
    "query_analytics",
    "query_faces",
    "query_vehicles",
    "search_recordings",
    "get_system_health",
}

# Tier 2 (Operational Actions) - Requires OPERATOR, MANAGER, ORG_ADMIN, or SUPER_ADMIN
TIER_2_OPERATIONAL_TOOLS: set[str] = {
    "acknowledge_alerts",
}

# Complete allowed tool whitelist (No deletion tools are ever permitted)
ALLOWED_COPILOT_TOOLS: set[str] = TIER_1_READ_TOOLS | TIER_2_OPERATIONAL_TOOLS

_GEMINI_TOOL = types.Tool(function_declarations=_COPILOT_FUNCTION_DECLARATIONS)
_TOOL_DEFINITIONS = [
    {
        "name": fd.name,
        "description": fd.description,
        "input_schema": fd.parameters,
    }
    for fd in _COPILOT_FUNCTION_DECLARATIONS
]


class CopilotService:
    """AI Surveillance Copilot backed by Google Gemini with tool-calling capabilities.

    The copilot can answer natural-language questions about the surveillance
    system by calling tool functions that execute real database queries.
    Conversations are stored in Redis for history and context management.
    """

    def __init__(self) -> None:
        """Initialise the Gemini client using the API key from settings.

        The service remains optional: if GEMINI_API_KEY is not configured, the
        copilot initializes safely with self._client = None without crashing.
        """
        settings = get_settings()
        api_key = (
            getattr(settings, "GEMINI_API_KEY", None)
            or getattr(settings, "ANTHROPIC_API_KEY", None)
            or ""
        )
        self._api_key = api_key.strip()
        configured_model = getattr(settings, "GEMINI_MODEL", None) or _DEFAULT_GEMINI_MODEL
        # Ensure configured model is first, followed by remaining fallback candidates
        candidates = [configured_model] + [m for m in MODELS_TO_TRY if m != configured_model]
        self._models_to_try = candidates
        self._model = self._models_to_try[0]
        self._client: Optional[genai.Client] = (
            genai.Client(api_key=self._api_key) if self._api_key else None
        )
        self._redis: Any = None

    async def _get_redis(self) -> Any:
        """Lazily obtain the Redis connection pool."""
        if self._redis is None:
            from app.dependencies import get_redis
            self._redis = await get_redis()
        return self._redis

    async def cancel_conversation(self, conversation_id: str) -> None:
        """Set hard cancellation flag in Redis for this conversation."""
        if not conversation_id:
            return
        redis = await self._get_redis()
        await redis.set(f"{_CONV_CANCEL_PREFIX}{conversation_id}", "1", ex=60)
        logger.info("Copilot run cancelled by user", conversation_id=conversation_id)

    async def _is_cancelled(self, conversation_id: Optional[str]) -> bool:
        """Check whether a hard cancellation flag has been set."""
        if not conversation_id:
            return False
        try:
            redis = await self._get_redis()
            val = await redis.get(f"{_CONV_CANCEL_PREFIX}{conversation_id}")
            return val is not None
        except Exception:
            return False

    @staticmethod
    def _format_progress_message(tool_name: str, args: dict[str, Any]) -> str:
        """Format an informative progress message for real-time UI streaming."""
        if tool_name == "query_cameras":
            name = args.get("name")
            status = args.get("status")
            if name:
                return f"Opening and checking cameras matching '{name}'..."
            if status:
                return f"Retrieving {status} cameras..."
            return "Opening cameras and inspecting status..."
        elif tool_name == "query_alerts":
            cam = args.get("camera_name")
            sev = args.get("severity")
            if cam and sev:
                return f"Filtering {sev} alerts for {cam}..."
            if cam:
                return f"Filtering alerts for {cam}..."
            if sev:
                return f"Filtering {sev} alerts..."
            return "Querying and filtering surveillance alerts..."
        elif tool_name == "acknowledge_alerts":
            cam = args.get("camera_name")
            if cam:
                return f"Acknowledging alerts for {cam}..."
            return "Acknowledging active alerts..."
        elif tool_name == "query_analytics":
            metric = args.get("metric", "analytics")
            return f"Analyzing {metric} data..."
        elif tool_name == "query_faces":
            name = args.get("person_name")
            return f"Searching face records for '{name}'..." if name else "Searching face recognition records..."
        elif tool_name == "query_vehicles":
            plate = args.get("plate_number")
            return f"Searching vehicle logs for '{plate}'..." if plate else "Searching vehicle ANPR records..."
        elif tool_name == "search_recordings":
            cam = args.get("camera_name")
            return f"Searching recordings for {cam}..." if cam else "Searching surveillance video recordings..."
        elif tool_name == "get_system_health":
            return "Checking platform and camera health..."
        return f"Executing {tool_name}..."

    @staticmethod
    def _extract_summary_sentence(text: str) -> tuple[str, str]:
        """Extract SUMMARY: tag from model response or generate a clean one-sentence voice summary."""
        import re
        match = re.search(r"(?:\n|\A)SUMMARY:\s*(.+?)(?:\n|\Z)", text, flags=re.IGNORECASE)
        if match:
            summary = match.group(1).strip()
            clean_summary = re.sub(r"[*_`#]", "", summary).strip()
            clean_text = re.sub(r"(?:\n|\A)SUMMARY:\s*.+?(?:\n|\Z)", "\n", text, flags=re.IGNORECASE).strip()
            return clean_text, clean_summary

        # Fallback: extract the first clear sentence from the response
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        for line in lines:
            if line.startswith("#") or line.startswith("|") or line.startswith("```"):
                continue
            cleaned_line = re.sub(r"^[\s*+-]+\s+", "", line)
            first_sent = cleaned_line.split(". ")[0].strip()
            if first_sent and len(first_sent) > 8:
                clean_sent = re.sub(r"[*_`#]", "", first_sent).strip()
                if not clean_sent.endswith("."):
                    clean_sent += "."
                return text, clean_sent

        return text, "Surveillance query processed successfully."

    # ------------------------------------------------------------------
    # Streaming Agent Engine (Multi-Step & Real-time Progress)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        message: str,
        user: Optional[User] = None,
        user_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[str] = None,
    ):
        """Asynchronously stream the agent's multi-step execution.

        Yields events:
        - {"event": "progress", "step": int, "max_steps": 5, "tool": str, "message": str}
        - {"event": "done", "response_text": str, "summary_sentence": str, ...}
        - {"event": "cancel", "message": str}
        """
        redis = await self._get_redis()
        effective_user_id = user.id if user else (user_id or uuid.uuid4())

        # Resolve or create conversation
        if conversation_id is None:
            conversation_id = f"conv_{uuid.uuid4().hex[:16]}"

        # Check for immediate cancellation before start
        if await self._is_cancelled(conversation_id):
            await redis.delete(f"{_CONV_CANCEL_PREFIX}{conversation_id}")
            yield {"event": "cancel", "message": "Agent run stopped by operator."}
            return

        conv_key = f"{_CONV_PREFIX}{effective_user_id}:{conversation_id}"
        raw_history = await redis.get(conv_key)
        history: list[dict[str, Any]] = json.loads(raw_history) if raw_history else []

        # Append new user message
        now_iso = datetime.now(timezone.utc).isoformat()
        history.append({
            "role": "user",
            "content": message,
            "data_cards": [],
            "timestamp": now_iso,
        })

        # Check if Gemini API key / client is configured
        if not self._client or not self._api_key:
            response_text = (
                "AYE AI is currently not configured. "
                "Please set the GEMINI_API_KEY environment variable to enable this feature."
            )
            summary_sentence = "AYE AI is currently not configured. Please set the Gemini API key."
            suggested_followups = [
                "How do I configure the Gemini API key?",
                "What can AYE AI do?",
            ]
            history.append({
                "role": "assistant",
                "content": response_text,
                "data_cards": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await redis.set(conv_key, json.dumps(history, default=str), ex=_CONV_TTL)
            await self._update_conversation_index(
                redis, effective_user_id, conversation_id, message, len(history)
            )
            yield {
                "event": "done",
                "response_text": response_text,
                "summary_sentence": summary_sentence,
                "conversation_id": conversation_id,
                "data_cards": [],
                "suggested_followups": suggested_followups,
            }
            return

        # Check for simple conversational greetings for instant response
        clean_msg = message.strip().lower().rstrip("!.,?")
        _GREETINGS = {"hi", "hello", "hey", "hola", "greetings", "good morning", "good evening", "good afternoon"}
        if clean_msg in _GREETINGS:
            response_text = (
                "Hello! I am **AYE AI**, your surveillance intelligence assistant for AYE Vision.\n\n"
                "I'm ready to assist you with:\n"
                "• **Alert Monitoring**: Active alerts, intrusions, loitering, or safety events\n"
                "• **Camera Health**: Online/offline camera statuses, diagnostics, and locations\n"
                "• **Analytics & Footfall**: Occupancy levels, footfall counts, and dwell-time metrics\n"
                "• **Face Recognition**: Search enrolled persons and recent detection events\n"
                "• **ANPR / Vehicles**: Look up registered license plates and entry logs\n"
                "• **System Health**: Overview of rules, storage, and platform operations\n\n"
                "How can I help you right now?"
            )
            summary_sentence = "Hello! I am AYE AI, your surveillance intelligence assistant. How can I assist you today?"
            suggested_followups = [
                "Which cameras are currently offline?",
                "Show me critical alerts from the last hour",
                "What is today's footfall summary?",
                "Are there any security rule violations?",
            ]
            history.append({
                "role": "assistant",
                "content": response_text,
                "data_cards": [],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await redis.set(conv_key, json.dumps(history, default=str), ex=_CONV_TTL)
            await self._update_conversation_index(
                redis, effective_user_id, conversation_id, message, len(history)
            )
            yield {
                "event": "done",
                "response_text": response_text,
                "summary_sentence": summary_sentence,
                "conversation_id": conversation_id,
                "data_cards": [],
                "suggested_followups": suggested_followups,
            }
            return

        # Build system prompt with live context and agent instructions
        system_prompt = await self._build_system_prompt(db, org_id)

        # Convert recent conversation history (bounded to last 10 turns = 20 messages)
        gemini_contents = self._history_to_gemini_contents(history)

        data_cards: list[dict[str, Any]] = []
        response_text = ""
        total_tool_calls = 0

        try:
            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                tools=[_GEMINI_TOOL],
                temperature=0.2,
            )

            max_iterations = 6
            iteration = 0

            while iteration < max_iterations:
                iteration += 1

                # Check hard stop before Gemini call
                if await self._is_cancelled(conversation_id):
                    await redis.delete(f"{_CONV_CANCEL_PREFIX}{conversation_id}")
                    yield {"event": "cancel", "message": "Agent execution stopped by operator."}
                    return

                response = await self._generate_with_retry(gemini_contents, config)

                function_calls = getattr(response, "function_calls", None)
                if not function_calls:
                    # Model returned final text
                    if getattr(response, "text", None):
                        response_text = response.text
                    elif getattr(response, "candidates", None) and response.candidates[0].content:
                        for part in response.candidates[0].content.parts:
                            if getattr(part, "text", None):
                                response_text += part.text
                    break

                # Append model message with function calls to dialog
                if getattr(response, "candidates", None) and response.candidates[0].content:
                    gemini_contents.append(response.candidates[0].content)

                # Execute requested function calls in sequence (up to 5 max)
                tool_results_parts: list[types.Part] = []
                for fc in function_calls:
                    # Check hard stop before each tool
                    if await self._is_cancelled(conversation_id):
                        await redis.delete(f"{_CONV_CANCEL_PREFIX}{conversation_id}")
                        yield {"event": "cancel", "message": "Agent execution stopped by operator."}
                        return

                    if total_tool_calls >= _MAX_TOOL_CALLS:
                        logger.info("Copilot reached max tool limit", count=total_tool_calls)
                        tool_results_parts.append(
                            types.Part.from_function_response(
                                name=fc.name,
                                response={
                                    "result": {
                                        "warning": f"Tool execution limit ({_MAX_TOOL_CALLS}) reached for this turn. Synthesize your final answer now."
                                    }
                                },
                            )
                        )
                        continue

                    total_tool_calls += 1
                    tool_name = fc.name
                    tool_input = dict(fc.args or {})

                    # Stream progress event to UI
                    progress_msg = self._format_progress_message(tool_name, tool_input)
                    yield {
                        "event": "progress",
                        "step": total_tool_calls,
                        "max_steps": _MAX_TOOL_CALLS,
                        "tool": tool_name,
                        "message": progress_msg,
                    }

                    # Execute tool with whitelist, tiers, role checks, and audit logging
                    tool_result, cards = await self._execute_tool(
                        db=db,
                        org_id=org_id,
                        user=user,
                        tool_name=tool_name,
                        tool_input=tool_input,
                    )
                    data_cards.extend(cards)

                    tool_results_parts.append(
                        types.Part.from_function_response(
                            name=tool_name,
                            response={"result": tool_result},
                        )
                    )

                # Feed tool results back to Gemini for the next step
                gemini_contents.append(
                    types.Content(role="user", parts=tool_results_parts)
                )

                if total_tool_calls >= _MAX_TOOL_CALLS:
                    # Enforce final synthesis without additional tools
                    config = types.GenerateContentConfig(
                        system_instruction=system_prompt,
                        tools=[],
                        temperature=0.2,
                    )

            # Check safety filters
            if not response_text and getattr(response, "candidates", None):
                candidate = response.candidates[0]
                finish_reason = getattr(candidate, "finish_reason", None)
                if finish_reason and str(finish_reason).upper() in (
                    "SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT"
                ):
                    response_text = (
                        "I cannot provide a response to this query due to safety policy restrictions. "
                        "Please rephrase your query."
                    )

            if not response_text:
                response_text = (
                    "I analyzed the surveillance data but was unable to produce a complete response. "
                    "Please try rephrasing your question."
                )

        except asyncio.TimeoutError:
            logger.error("Gemini API call timed out", conversation_id=conversation_id)
            response_text = "The request to the AI model timed out. Please try again or simplify your query."
        except errors.APIError as exc:
            exc_str = str(exc)
            code = getattr(exc, "code", None)
            if code == 429 or "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str:
                logger.warning("Gemini rate limit exceeded", conversation_id=conversation_id)
                response_text = "I've hit my rate limit with the AI service. Please wait a moment and try again."
            else:
                logger.error("Gemini API error", code=code, conversation_id=conversation_id)
                response_text = "I encountered an error communicating with the AI service. Please try again in a moment."
        except Exception as exc:
            logger.exception("Unexpected copilot error", error=str(exc))
            response_text = "An unexpected error occurred. Please try again or rephrase your question."

        # Extract voice summary sentence
        clean_response_text, summary_sentence = self._extract_summary_sentence(response_text)

        # Generate follow-up suggestions
        suggested_followups = self._generate_followups(message, clean_response_text)

        # Append assistant message to history
        history.append({
            "role": "assistant",
            "content": clean_response_text,
            "data_cards": data_cards,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        # Trim history to keep exactly last 10 turns (20 messages)
        if len(history) > _MAX_HISTORY_TURNS:
            history = history[-_MAX_HISTORY_TURNS:]

        # Persist conversation to Redis
        await redis.set(conv_key, json.dumps(history, default=str), ex=_CONV_TTL)

        # Update conversation index
        await self._update_conversation_index(
            redis, effective_user_id, conversation_id, message, len(history)
        )

        yield {
            "event": "done",
            "response_text": clean_response_text,
            "summary_sentence": summary_sentence,
            "conversation_id": conversation_id,
            "data_cards": data_cards,
            "suggested_followups": suggested_followups,
        }

    # ------------------------------------------------------------------
    # Main Chat (Unified wrapper using streaming agent)
    # ------------------------------------------------------------------

    async def chat(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        message: str,
        user: Optional[User] = None,
        user_id: Optional[uuid.UUID] = None,
        conversation_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Process a user message using the multi-step agent and return the final response."""
        last_done: Optional[dict[str, Any]] = None
        async for event in self.chat_stream(
            db=db,
            org_id=org_id,
            user=user,
            user_id=user_id,
            message=message,
            conversation_id=conversation_id,
        ):
            if event.get("event") == "done":
                last_done = event
            elif event.get("event") == "cancel":
                return {
                    "response_text": "🛑 Agent execution was stopped by operator.",
                    "summary_sentence": "Agent execution stopped.",
                    "conversation_id": conversation_id or "",
                    "data_cards": [],
                    "suggested_followups": [],
                }

        if last_done:
            return {
                "response_text": last_done["response_text"],
                "summary_sentence": last_done.get("summary_sentence", ""),
                "conversation_id": last_done["conversation_id"],
                "data_cards": last_done.get("data_cards", []),
                "suggested_followups": last_done.get("suggested_followups", []),
            }

        return {
            "response_text": "Unable to complete request.",
            "summary_sentence": "Request failed.",
            "conversation_id": conversation_id or "",
            "data_cards": [],
            "suggested_followups": [],
        }

    # ------------------------------------------------------------------
    # Gemini Invocation Helper with Retry & Timeout
    # ------------------------------------------------------------------

    async def _generate_with_retry(
        self,
        contents: list[types.Content],
        config: types.GenerateContentConfig,
        timeout_seconds: float = 25.0,
    ) -> Any:
        """Call Gemini API with automatic model fallback chain and retry for high availability."""
        last_exc: Optional[Exception] = None

        # Build list of models to try, starting with current active model
        models_order = [self._model] + [m for m in self._models_to_try if m != self._model]

        for model_name in models_order:
            for attempt in range(2):
                try:
                    coro = self._client.aio.models.generate_content(
                        model=model_name,
                        contents=contents,
                        config=config,
                    )
                    response = await asyncio.wait_for(coro, timeout=timeout_seconds)
                    # Successfully generated with this model; remember it for future calls
                    if self._model != model_name:
                        logger.info("Switching active Gemini model", model=model_name)
                        self._model = model_name
                    return response
                except asyncio.TimeoutError as exc:
                    logger.warning(
                        "Gemini model timed out, attempting next candidate",
                        model=model_name,
                        attempt=attempt + 1,
                    )
                    last_exc = exc
                    break  # Failover to next model immediately for fast user response
                except Exception as exc:
                    last_exc = exc
                    exc_str = str(exc)
                    code = getattr(exc, "code", None)
                    is_not_found = code == 404 or "404" in exc_str or "NOT_FOUND" in exc_str
                    is_unavailable = code == 503 or "503" in exc_str or "UNAVAILABLE" in exc_str
                    is_rate_limit = (
                        code == 429
                        or "429" in exc_str
                        or "RESOURCE_EXHAUSTED" in exc_str
                        or "rate_limit" in exc_str.lower()
                    )

                    if is_not_found or is_unavailable:
                        logger.warning(
                            "Gemini model unavailable or deprecated, falling back to next candidate",
                            model=model_name,
                            code=code,
                        )
                        break  # Fall back to next model immediately

                    if is_rate_limit:
                        logger.warning(
                            "Gemini model rate limited, attempting next candidate",
                            model=model_name,
                            attempt=attempt + 1,
                        )
                        if attempt == 0:
                            break  # Try next candidate model before sleeping
                        else:
                            await asyncio.sleep(1.0)
                            continue

                    logger.warning(
                        "Gemini API error, trying next candidate model",
                        model=model_name,
                        error=exc_str[:120],
                    )
                    break

        if last_exc:
            raise last_exc
        raise RuntimeError("Generation failed across all candidate models.")

    # ------------------------------------------------------------------
    # System Prompt
    # ------------------------------------------------------------------

    async def _build_system_prompt(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
    ) -> str:
        """Build a context-rich system prompt with live surveillance data.

        Includes organization info, camera count, active alert summary,
        and other contextual details that help the AI provide relevant
        answers. Results are cached in Redis for 45 seconds to ensure fast responses.
        """
        redis = await self._get_redis()
        cache_key = f"copilot:sysprompt:{org_id}"
        try:
            cached = await redis.get(cache_key)
            if cached:
                return cached if isinstance(cached, str) else cached.decode("utf-8")
        except Exception:
            pass

        # Gather contextual statistics
        org_result = await db.execute(
            select(Organization).where(Organization.id == org_id)
        )
        org = org_result.scalar_one_or_none()
        org_name = org.name if org else "Unknown"
        org_timezone = org.timezone if org else "UTC"

        # Camera counts
        total_cameras = (await db.execute(
            select(func.count()).select_from(Camera).where(Camera.org_id == org_id)
        )).scalar() or 0

        online_cameras = (await db.execute(
            select(func.count()).select_from(Camera).where(
                Camera.org_id == org_id, Camera.is_online.is_(True)
            )
        )).scalar() or 0

        offline_cameras = total_cameras - online_cameras

        # Today's alert counts (naive datetime for TIMESTAMP WITHOUT TIME ZONE)
        today_start = _utcnow_naive().replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        total_alerts_today = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id, Alert.created_at >= today_start
            )
        )).scalar() or 0

        critical_alerts = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id,
                Alert.created_at >= today_start,
                Alert.severity == RuleSeverity.CRITICAL,
            )
        )).scalar() or 0

        unresolved_alerts = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id,
                Alert.status.in_([AlertStatus.NEW, AlertStatus.ESCALATED]),
            )
        )).scalar() or 0

        # Enrolled persons count
        total_persons = (await db.execute(
            select(func.count()).select_from(Person).where(Person.org_id == org_id)
        )).scalar() or 0

        # Registered vehicles count
        total_vehicles = (await db.execute(
            select(func.count()).select_from(Vehicle).where(Vehicle.org_id == org_id)
        )).scalar() or 0

        # Active rules count
        active_rules = (await db.execute(
            select(func.count()).select_from(Rule).where(
                Rule.org_id == org_id, Rule.is_active.is_(True)
            )
        )).scalar() or 0

        current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

        prompt = f"""You are AYE AI, an intelligent AI assistant powered by Google Gemini embedded in the AYE Vision video surveillance and analytics platform. You help security operators, facility managers, and administrators query and understand their surveillance system through natural language.

## Your Capabilities
- Query and analyze alerts (intrusion, loitering, fire/smoke, PPE violations, etc.)
- Check camera status and health across the facility
- Retrieve footfall analytics, occupancy data, and dwell-time metrics
- Search the face recognition database and recent face events
- Search ANPR (Automatic Number Plate Recognition) vehicle records
- Find and reference video recordings
- Report on overall system health

## Current Context
- **Organization**: {org_name}
- **Timezone**: {org_timezone}
- **Current Time**: {current_time}
- **Cameras**: {total_cameras} total ({online_cameras} online, {offline_cameras} offline)
- **Today's Alerts**: {total_alerts_today} ({critical_alerts} critical, {unresolved_alerts} unresolved)
- **Enrolled Persons**: {total_persons}
- **Registered Vehicles**: {total_vehicles}
- **Active Detection Rules**: {active_rules}

## Guidelines & Agent Execution Rules
1. **Autonomous Multi-Step Execution**: You are an autonomous surveillance agent capable of calling tools sequentially (up to 5 tool calls per request). After each tool result is received, evaluate it to decide the next step or formulate your final answer.
2. **Ambiguity & Clarifying Questions**:
   - If a required detail is missing or ambiguous (e.g. user asks about "the gate camera" and multiple cameras match like "Front Gate" and "Back Gate", or an alert reference is unclear), DO NOT GUESS.
   - Ask a short, polite clarifying question presenting the options directly to the operator.
3. **Contextual Follow-ups**:
   - Maintain multi-turn context (last 10 turns per session). Follow-up commands like "now filter those to the main gate" or "acknowledge them" refer back to previously discussed cameras and alerts.
4. **Security Whitelist & Guardrails**:
   - You may only execute whitelisted tools (`query_*`, `search_*`, `get_system_health`, and `acknowledge_alerts`).
   - DELETIONS ARE STRICTLY FORBIDDEN. Never attempt or suggest deleting cameras, recordings, rules, or users.
5. **Clear Presentation**:
   - Present data clearly using tables and structured formats when appropriate.
   - Include severity levels, camera names, and timestamps for alerts.
   - If a query returns no results, state it clearly and suggest next steps.
6. **One-Sentence Voice Summary**:
   - At the very end of your final response, on a new line by itself, write:
     `SUMMARY: <one concise spoken sentence summarizing findings or actions taken>`
     Example: `SUMMARY: Found 2 offline cameras located in the north parking sector.` or `SUMMARY: Acknowledged 3 critical alerts for Front Gate.`
   - This summary is used for real-time operator voice readouts. Keep it under 25 words."""

        try:
            await redis.set(cache_key, prompt, ex=45)
        except Exception:
            pass

        return prompt

    # ------------------------------------------------------------------
    # History Conversion
    # ------------------------------------------------------------------

    @staticmethod
    def _history_to_gemini_contents(
        history: list[dict[str, Any]],
    ) -> list[types.Content]:
        """Convert the internal conversation history to Gemini Content format.

        Only keeps the last ``_MAX_HISTORY_TURNS`` messages and strips
        metadata (data_cards, timestamps). Converts 'assistant' to 'model'.
        Ensures the conversation begins with a 'user' message and alternates roles.
        """
        recent = history[-_MAX_HISTORY_TURNS:]
        raw_items: list[tuple[str, str]] = []
        for entry in recent:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if not content:
                continue
            gemini_role = "model" if role in ("assistant", "model") else "user"
            raw_items.append((gemini_role, content))

        # Ensure history starts with user
        while raw_items and raw_items[0][0] != "user":
            raw_items.pop(0)

        # Merge consecutive turns with same role
        merged: list[tuple[str, str]] = []
        for role, text in raw_items:
            if merged and merged[-1][0] == role:
                merged[-1] = (role, merged[-1][1] + "\n\n" + text)
            else:
                merged.append((role, text))

        contents: list[types.Content] = []
        for role, text in merged:
            contents.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=text)],
                )
            )
        return contents

    @staticmethod
    def _history_to_claude_messages(
        history: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Deprecated: Legacy Claude message format converter kept for compatibility."""
        recent = history[-_MAX_HISTORY_TURNS:]
        messages: list[dict[str, Any]] = []
        for entry in recent:
            role = entry.get("role", "user")
            content = entry.get("content", "")
            if role in ("user", "assistant") and content:
                messages.append({"role": role, "content": content})

        while messages and messages[0]["role"] != "user":
            messages.pop(0)

        merged: list[dict[str, Any]] = []
        for msg in messages:
            if merged and merged[-1]["role"] == msg["role"]:
                merged[-1]["content"] += "\n\n" + msg["content"]
            else:
                merged.append(msg)

        return merged

    # ------------------------------------------------------------------
    # Tool Execution
    # ------------------------------------------------------------------

    async def _execute_tool(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        user: Any,
        tool_name: str,
        tool_input: dict[str, Any],
    ) -> tuple[Any, list[dict[str, Any]]]:
        """Execute a tool function with security whitelist validation, role checks, and audit logging.

        Args:
            db: Async database session.
            org_id: Organization ID for data scoping.
            user: Authenticated user object with role and id.
            tool_name: Name of the tool to execute.
            tool_input: Input parameters for the tool.

        Returns:
            Tuple of (tool_result_data, list_of_data_cards).
        """
        # 1. Whitelist validation (strictly no delete tools or unknown tools)
        if tool_name not in ALLOWED_COPILOT_TOOLS or "delete" in tool_name.lower() or "drop" in tool_name.lower():
            logger.warning(
                "copilot_tool_blocked_whitelist_violation",
                tool=tool_name,
                user_id=str(getattr(user, "id", "anon")),
                org_id=str(org_id),
            )
            return {
                "error": f"Security restriction: Tool '{tool_name}' is not permitted by the Copilot whitelist. Deletion and modification of system entities are forbidden."
            }, []

        # 2. Tier & Role checks
        user_role = getattr(user, "role", None)
        if tool_name in TIER_2_OPERATIONAL_TOOLS:
            allowed_roles = {UserRole.SUPER_ADMIN, UserRole.ORG_ADMIN, UserRole.MANAGER, UserRole.OPERATOR}
            if user_role not in allowed_roles:
                logger.warning(
                    "copilot_tool_permission_denied",
                    tool=tool_name,
                    user_id=str(getattr(user, "id", "anon")),
                    role=str(user_role),
                )
                return {
                    "error": f"Permission denied: Operator role or higher is required to execute operational action '{tool_name}'. Current role: {user_role}."
                }, []

        # 3. Audit logging
        logger.info(
            "copilot_tool_audit_execution",
            tool=tool_name,
            user_id=str(getattr(user, "id", "")),
            user_role=str(getattr(user_role, "value", user_role)),
            org_id=str(org_id),
            params=tool_input,
        )

        tool_map = {
            "query_alerts": self._query_alerts,
            "query_cameras": self._query_cameras,
            "query_analytics": self._query_analytics,
            "query_faces": self._query_faces,
            "query_vehicles": self._query_vehicles,
            "search_recordings": self._search_recordings,
            "get_system_health": self._get_system_health,
            "acknowledge_alerts": lambda db, org_id, params: self._acknowledge_alerts(db, org_id, params, user),
        }

        handler = tool_map.get(tool_name)
        if handler is None:
            logger.warning("Unknown tool requested", tool_name=tool_name)
            return {"error": f"Unknown tool: {tool_name}"}, []

        try:
            return await handler(db, org_id, tool_input)
        except Exception as exc:
            logger.exception("Tool execution failed", tool=tool_name, error=str(exc))
            return {"error": f"Tool execution failed: {str(exc)}"}, []

    # ------------------------------------------------------------------
    # Tool Implementations
    # ------------------------------------------------------------------

    async def _query_alerts(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Query alerts with optional filters."""
        hours_ago = params.get("hours_ago", 24)
        limit = min(params.get("limit", 20), 50)
        since = _utcnow_naive() - timedelta(hours=hours_ago)

        query = (
            select(Alert)
            .where(Alert.org_id == org_id, Alert.created_at >= since)
        )

        if params.get("severity"):
            try:
                query = query.where(Alert.severity == RuleSeverity(params["severity"]))
            except ValueError:
                pass

        if params.get("alert_type"):
            try:
                query = query.where(Alert.alert_type == RuleType(params["alert_type"]))
            except ValueError:
                pass

        if params.get("status"):
            try:
                query = query.where(Alert.status == AlertStatus(params["status"]))
            except ValueError:
                pass

        if params.get("camera_name"):
            camera_sub = select(Camera.id).where(
                Camera.org_id == org_id,
                Camera.name.ilike(f"%{params['camera_name']}%"),
            )
            query = query.where(Alert.camera_id.in_(camera_sub))

        # Get total count
        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        # Get alert records
        query = query.order_by(Alert.created_at.desc()).limit(limit)
        result = await db.execute(query)
        alerts = result.scalars().all()

        # Severity breakdown
        severity_q = (
            select(Alert.severity, func.count().label("cnt"))
            .where(Alert.org_id == org_id, Alert.created_at >= since)
            .group_by(Alert.severity)
        )
        sev_result = await db.execute(severity_q)
        severity_breakdown = {
            row.severity.value: row.cnt for row in sev_result.all()
        }

        alert_rows = []
        for a in alerts:
            # Load camera name via relationship
            camera_name = "Unknown"
            if a.camera_id:
                cam_result = await db.execute(
                    select(Camera.name).where(Camera.id == a.camera_id)
                )
                cam_name = cam_result.scalar_one_or_none()
                if cam_name:
                    camera_name = cam_name

            alert_rows.append({
                "id": str(a.id),
                "title": a.title,
                "type": a.alert_type.value if a.alert_type else "",
                "severity": a.severity.value if a.severity else "",
                "status": a.status.value if a.status else "",
                "camera": camera_name,
                "created_at": a.created_at.isoformat() if a.created_at else "",
            })

        result_data = {
            "total": total,
            "returned": len(alert_rows),
            "time_range": f"Last {hours_ago} hours",
            "severity_breakdown": severity_breakdown,
            "alerts": alert_rows,
        }

        # Build data cards
        cards: list[dict[str, Any]] = []
        if severity_breakdown:
            cards.append({
                "type": "chart",
                "title": f"Alerts by Severity (Last {hours_ago}h)",
                "data": {
                    "labels": list(severity_breakdown.keys()),
                    "datasets": [{
                        "label": "Alert Count",
                        "data": list(severity_breakdown.values()),
                    }],
                },
            })

        if alert_rows:
            cards.append({
                "type": "alert_list",
                "title": f"Recent Alerts ({len(alert_rows)} of {total})",
                "data": alert_rows[:10],
            })

        return result_data, cards

    async def _query_cameras(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Query camera information with optional filters."""
        query = select(Camera).where(Camera.org_id == org_id)

        status_filter = params.get("status", "all")
        if status_filter == "online":
            query = query.where(Camera.is_online.is_(True))
        elif status_filter == "offline":
            query = query.where(Camera.is_online.is_(False))

        if params.get("name"):
            query = query.where(Camera.name.ilike(f"%{params['name']}%"))

        query = query.order_by(Camera.name)
        result = await db.execute(query)
        cameras = result.scalars().all()

        camera_rows = []
        for c in cameras:
            camera_rows.append({
                "id": str(c.id),
                "name": c.name,
                "location": c.location_description or "N/A",
                "status": "online" if c.is_online else "offline",
                "protocol": c.protocol.value if c.protocol else "",
                "resolution": c.resolution or "N/A",
                "fps": c.fps,
                "recording_mode": c.recording_mode.value if c.recording_mode else "",
                "last_seen": c.last_seen_at.isoformat() if c.last_seen_at else "Never",
            })

        online_count = sum(1 for c in camera_rows if c["status"] == "online")
        offline_count = len(camera_rows) - online_count

        result_data = {
            "total": len(camera_rows),
            "online": online_count,
            "offline": offline_count,
            "cameras": camera_rows,
        }

        # Ambiguity check: if user queried a specific camera name and multiple matched
        if params.get("name") and len(camera_rows) > 1:
            matching_names = [c["name"] for c in camera_rows]
            result_data["ambiguity_detected"] = True
            result_data["matching_camera_names"] = matching_names
            result_data["clarification_instruction"] = (
                f"Multiple cameras match the requested name '{params['name']}': {', '.join(matching_names)}. "
                "Ask a short clarifying question to ask which camera the user meant before proceeding."
            )

        cards: list[dict[str, Any]] = []
        if camera_rows:
            cards.append({
                "type": "camera_grid",
                "title": f"Cameras ({online_count} online, {offline_count} offline)",
                "data": camera_rows,
            })

        return result_data, cards

    async def _acknowledge_alerts(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
        user: Any,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Acknowledge one or more surveillance alerts by ID or filter criteria."""
        alert_ids = params.get("alert_ids") or []
        camera_name = params.get("camera_name")
        severity = params.get("severity")
        limit = min(params.get("limit", 10), 50)

        query = select(Alert).where(Alert.org_id == org_id, Alert.status == AlertStatus.NEW)

        if alert_ids:
            valid_ids = []
            for aid in alert_ids:
                try:
                    valid_ids.append(uuid.UUID(str(aid)))
                except (ValueError, TypeError):
                    pass
            if valid_ids:
                query = query.where(Alert.id.in_(valid_ids))

        if camera_name:
            cam_sub = select(Camera.id).where(
                Camera.org_id == org_id,
                Camera.name.ilike(f"%{camera_name}%"),
            )
            query = query.where(Alert.camera_id.in_(cam_sub))

        if severity:
            try:
                query = query.where(Alert.severity == RuleSeverity(severity))
            except ValueError:
                pass

        query = query.order_by(Alert.created_at.desc()).limit(limit)
        result = await db.execute(query)
        alerts = result.scalars().all()

        if not alerts:
            return {
                "acknowledged_count": 0,
                "message": "No new (unacknowledged) alerts found matching the criteria.",
            }, []

        now = _utcnow_naive()
        user_id = getattr(user, "id", None)
        acknowledged_titles: list[str] = []
        for a in alerts:
            a.status = AlertStatus.ACKNOWLEDGED
            a.acknowledged_by = user_id
            a.acknowledged_at = now
            db.add(a)
            acknowledged_titles.append(f"{a.title} ({a.severity.value})")

        await db.commit()

        cards = [{
            "type": "stat",
            "title": "Alerts Acknowledged",
            "data": {
                "label": "Acknowledged Alerts",
                "value": str(len(alerts)),
                "change_pct": 0,
                "trend": "down",
            },
        }]

        return {
            "acknowledged_count": len(alerts),
            "alerts": acknowledged_titles,
            "message": f"Successfully acknowledged {len(alerts)} alert(s).",
        }, cards

    async def _query_analytics(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Query analytics data (footfall, occupancy, dwell time)."""
        metric = params.get("metric", "footfall")
        hours_ago = params.get("hours_ago", 24)
        limit = min(params.get("limit", 20), 50)
        since = _utcnow_naive() - timedelta(hours=hours_ago)

        # Resolve camera filter
        camera_ids = None
        if params.get("camera_name"):
            cam_q = select(Camera.id).where(
                Camera.org_id == org_id,
                Camera.name.ilike(f"%{params['camera_name']}%"),
            )
            cam_result = await db.execute(cam_q)
            camera_ids = [row[0] for row in cam_result.all()]

        cards: list[dict[str, Any]] = []

        if metric == "footfall":
            query = (
                select(FootfallRecord)
                .join(Camera, FootfallRecord.camera_id == Camera.id)
                .where(Camera.org_id == org_id, FootfallRecord.timestamp >= since)
            )
            if camera_ids is not None:
                query = query.where(FootfallRecord.camera_id.in_(camera_ids))

            query = query.order_by(FootfallRecord.timestamp.desc()).limit(limit)
            result = await db.execute(query)
            records = result.scalars().all()

            total_entries = sum(r.entries_count for r in records)
            total_exits = sum(r.exits_count for r in records)

            rows = []
            for r in records:
                cam_result = await db.execute(
                    select(Camera.name).where(Camera.id == r.camera_id)
                )
                cam_name = cam_result.scalar_one_or_none() or "Unknown"
                rows.append({
                    "timestamp": r.timestamp.isoformat() if r.timestamp else "",
                    "camera": cam_name,
                    "entries": r.entries_count,
                    "exits": r.exits_count,
                    "occupancy": r.occupancy_estimate,
                })

            result_data = {
                "metric": "footfall",
                "time_range": f"Last {hours_ago} hours",
                "total_entries": total_entries,
                "total_exits": total_exits,
                "records": rows,
            }

            if rows:
                cards.append({
                    "type": "stat",
                    "title": "Footfall Summary",
                    "data": {
                        "label": "Total Entries / Exits",
                        "value": f"{total_entries} / {total_exits}",
                        "trend": "neutral",
                    },
                })
                cards.append({
                    "type": "table",
                    "title": f"Footfall Records (Last {hours_ago}h)",
                    "data": {
                        "headers": ["Timestamp", "Camera", "Entries", "Exits", "Occupancy"],
                        "rows": [
                            [r["timestamp"], r["camera"], r["entries"], r["exits"], r["occupancy"]]
                            for r in rows[:10]
                        ],
                    },
                })

        elif metric == "dwell_time":
            query = (
                select(DwellRecord)
                .join(Camera, DwellRecord.camera_id == Camera.id)
                .where(Camera.org_id == org_id, DwellRecord.enter_time >= since)
            )
            if camera_ids is not None:
                query = query.where(DwellRecord.camera_id.in_(camera_ids))

            query = query.order_by(DwellRecord.enter_time.desc()).limit(limit)
            result = await db.execute(query)
            records = result.scalars().all()

            dwell_values = [r.dwell_seconds for r in records if r.dwell_seconds is not None]
            avg_dwell = round(sum(dwell_values) / len(dwell_values), 1) if dwell_values else 0
            max_dwell = round(max(dwell_values), 1) if dwell_values else 0

            result_data = {
                "metric": "dwell_time",
                "time_range": f"Last {hours_ago} hours",
                "total_records": len(records),
                "avg_dwell_seconds": avg_dwell,
                "max_dwell_seconds": max_dwell,
            }

            cards.append({
                "type": "stat",
                "title": "Dwell Time Summary",
                "data": {
                    "label": "Avg / Max Dwell",
                    "value": f"{avg_dwell}s / {max_dwell}s",
                    "trend": "neutral",
                },
            })

        else:
            # occupancy - derive from footfall
            query = (
                select(FootfallRecord)
                .join(Camera, FootfallRecord.camera_id == Camera.id)
                .where(
                    Camera.org_id == org_id,
                    FootfallRecord.timestamp >= since,
                    FootfallRecord.occupancy_estimate.isnot(None),
                )
            )
            if camera_ids is not None:
                query = query.where(FootfallRecord.camera_id.in_(camera_ids))

            query = query.order_by(FootfallRecord.timestamp.desc()).limit(limit)
            result = await db.execute(query)
            records = result.scalars().all()

            occ_values = [r.occupancy_estimate for r in records if r.occupancy_estimate is not None]
            avg_occ = round(sum(occ_values) / len(occ_values), 1) if occ_values else 0
            max_occ = max(occ_values) if occ_values else 0

            result_data = {
                "metric": "occupancy",
                "time_range": f"Last {hours_ago} hours",
                "total_records": len(records),
                "avg_occupancy": avg_occ,
                "max_occupancy": max_occ,
            }

            cards.append({
                "type": "stat",
                "title": "Occupancy Summary",
                "data": {
                    "label": "Avg / Max Occupancy",
                    "value": f"{avg_occ} / {max_occ}",
                    "trend": "neutral",
                },
            })

        return result_data, cards

    async def _query_faces(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Search face enrollment database or recent events."""
        search_type = params.get("search_type", "enrolled")
        limit = min(params.get("limit", 20), 50)
        cards: list[dict[str, Any]] = []

        if search_type == "enrolled":
            query = select(Person).where(Person.org_id == org_id)

            if params.get("person_name"):
                query = query.where(
                    Person.full_name.ilike(f"%{params['person_name']}%")
                )
            if params.get("person_type"):
                try:
                    query = query.where(
                        Person.person_type == PersonType(params["person_type"])
                    )
                except ValueError:
                    pass

            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0

            query = query.order_by(Person.full_name).limit(limit)
            result = await db.execute(query)
            persons = result.scalars().all()

            rows = [{
                "id": str(p.id),
                "name": p.full_name,
                "type": p.person_type.value if p.person_type else "",
                "created_at": p.created_at.isoformat() if p.created_at else "",
            } for p in persons]

            result_data = {
                "search_type": "enrolled",
                "total": total,
                "returned": len(rows),
                "persons": rows,
            }

            if rows:
                cards.append({
                    "type": "table",
                    "title": f"Enrolled Persons ({len(rows)} of {total})",
                    "data": {
                        "headers": ["Name", "Type", "Enrolled"],
                        "rows": [[r["name"], r["type"], r["created_at"]] for r in rows[:10]],
                    },
                })

        else:
            # face events
            hours_ago = params.get("hours_ago", 24)
            since = _utcnow_naive() - timedelta(hours=hours_ago)

            query = (
                select(FaceEvent)
                .join(Camera, FaceEvent.camera_id == Camera.id)
                .where(Camera.org_id == org_id, FaceEvent.timestamp >= since)
            )

            if params.get("person_name"):
                person_sub = select(Person.id).where(
                    Person.org_id == org_id,
                    Person.full_name.ilike(f"%{params['person_name']}%"),
                )
                query = query.where(FaceEvent.person_id.in_(person_sub))

            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0

            query = query.order_by(FaceEvent.timestamp.desc()).limit(limit)
            result = await db.execute(query)
            events = result.scalars().all()

            rows = []
            for e in events:
                person_name = "Unknown"
                if e.person_id:
                    p_result = await db.execute(
                        select(Person.full_name).where(Person.id == e.person_id)
                    )
                    pname = p_result.scalar_one_or_none()
                    if pname:
                        person_name = pname

                cam_result = await db.execute(
                    select(Camera.name).where(Camera.id == e.camera_id)
                )
                cam_name = cam_result.scalar_one_or_none() or "Unknown"

                rows.append({
                    "id": str(e.id),
                    "person": person_name,
                    "camera": cam_name,
                    "confidence": round(e.confidence, 2) if e.confidence else None,
                    "emotion": e.emotion,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                })

            result_data = {
                "search_type": "events",
                "total": total,
                "returned": len(rows),
                "time_range": f"Last {hours_ago} hours",
                "events": rows,
            }

            if rows:
                cards.append({
                    "type": "table",
                    "title": f"Face Events ({len(rows)} of {total})",
                    "data": {
                        "headers": ["Person", "Camera", "Confidence", "Emotion", "Time"],
                        "rows": [
                            [r["person"], r["camera"], r["confidence"], r["emotion"], r["timestamp"]]
                            for r in rows[:10]
                        ],
                    },
                })

        return result_data, cards

    async def _query_vehicles(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Search vehicle database or ANPR events."""
        search_type = params.get("search_type", "registered")
        limit = min(params.get("limit", 20), 50)
        cards: list[dict[str, Any]] = []

        if search_type == "registered":
            query = select(Vehicle).where(Vehicle.org_id == org_id)

            if params.get("plate_number"):
                query = query.where(
                    Vehicle.plate_number.ilike(f"%{params['plate_number']}%")
                )
            if params.get("category"):
                from app.models.vehicle import VehicleCategory
                try:
                    query = query.where(
                        Vehicle.category == VehicleCategory(params["category"])
                    )
                except ValueError:
                    pass

            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0

            query = query.order_by(Vehicle.plate_number).limit(limit)
            result = await db.execute(query)
            vehicles = result.scalars().all()

            rows = [{
                "id": str(v.id),
                "plate": v.plate_number,
                "owner": v.owner_name or "N/A",
                "type": v.vehicle_type or "N/A",
                "color": v.color or "N/A",
                "category": v.category.value if v.category else "",
                "make_model": f"{v.make or ''} {v.model_name or ''}".strip() or "N/A",
            } for v in vehicles]

            result_data = {
                "search_type": "registered",
                "total": total,
                "returned": len(rows),
                "vehicles": rows,
            }

            if rows:
                cards.append({
                    "type": "table",
                    "title": f"Registered Vehicles ({len(rows)} of {total})",
                    "data": {
                        "headers": ["Plate", "Owner", "Type", "Color", "Category"],
                        "rows": [
                            [r["plate"], r["owner"], r["type"], r["color"], r["category"]]
                            for r in rows[:10]
                        ],
                    },
                })

        elif search_type == "events":
            hours_ago = params.get("hours_ago", 24)
            since = _utcnow_naive() - timedelta(hours=hours_ago)

            query = (
                select(VehicleEvent)
                .join(Camera, VehicleEvent.camera_id == Camera.id)
                .where(Camera.org_id == org_id, VehicleEvent.timestamp >= since)
            )

            if params.get("plate_number"):
                query = query.where(
                    VehicleEvent.plate_number.ilike(f"%{params['plate_number']}%")
                )

            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0

            query = query.order_by(VehicleEvent.timestamp.desc()).limit(limit)
            result = await db.execute(query)
            events = result.scalars().all()

            rows = []
            for e in events:
                cam_result = await db.execute(
                    select(Camera.name).where(Camera.id == e.camera_id)
                )
                cam_name = cam_result.scalar_one_or_none() or "Unknown"

                rows.append({
                    "id": str(e.id),
                    "plate": e.plate_number,
                    "camera": cam_name,
                    "confidence": round(e.plate_confidence, 2) if e.plate_confidence else None,
                    "direction": e.direction.value if e.direction else "N/A",
                    "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                })

            result_data = {
                "search_type": "events",
                "total": total,
                "returned": len(rows),
                "time_range": f"Last {hours_ago} hours",
                "events": rows,
            }

            if rows:
                cards.append({
                    "type": "table",
                    "title": f"Vehicle Events ({len(rows)} of {total})",
                    "data": {
                        "headers": ["Plate", "Camera", "Confidence", "Direction", "Time"],
                        "rows": [
                            [r["plate"], r["camera"], r["confidence"], r["direction"], r["timestamp"]]
                            for r in rows[:10]
                        ],
                    },
                })

        else:
            # vehicle logs (entry/exit)
            hours_ago = params.get("hours_ago", 24)
            since = _utcnow_naive() - timedelta(hours=hours_ago)

            query = (
                select(VehicleLog)
                .join(Vehicle, VehicleLog.vehicle_id == Vehicle.id)
                .where(Vehicle.org_id == org_id, VehicleLog.entry_time >= since)
            )

            if params.get("plate_number"):
                vehicle_sub = select(Vehicle.id).where(
                    Vehicle.org_id == org_id,
                    Vehicle.plate_number.ilike(f"%{params['plate_number']}%"),
                )
                query = query.where(VehicleLog.vehicle_id.in_(vehicle_sub))

            count_q = select(func.count()).select_from(query.subquery())
            total = (await db.execute(count_q)).scalar() or 0

            query = query.order_by(VehicleLog.entry_time.desc()).limit(limit)
            result = await db.execute(query)
            logs = result.scalars().all()

            rows = []
            for log in logs:
                v_result = await db.execute(
                    select(Vehicle.plate_number).where(Vehicle.id == log.vehicle_id)
                )
                plate = v_result.scalar_one_or_none() or "Unknown"

                rows.append({
                    "id": str(log.id),
                    "plate": plate,
                    "entry_time": log.entry_time.isoformat() if log.entry_time else "",
                    "exit_time": log.exit_time.isoformat() if log.exit_time else "Still parked",
                    "duration": f"{log.duration_seconds // 60}m" if log.duration_seconds else "N/A",
                })

            result_data = {
                "search_type": "logs",
                "total": total,
                "returned": len(rows),
                "time_range": f"Last {hours_ago} hours",
                "logs": rows,
            }

            if rows:
                cards.append({
                    "type": "table",
                    "title": f"Vehicle Logs ({len(rows)} of {total})",
                    "data": {
                        "headers": ["Plate", "Entry", "Exit", "Duration"],
                        "rows": [
                            [r["plate"], r["entry_time"], r["exit_time"], r["duration"]]
                            for r in rows[:10]
                        ],
                    },
                })

        return result_data, cards

    async def _search_recordings(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Search video recordings."""
        hours_ago = params.get("hours_ago", 24)
        limit = min(params.get("limit", 10), 30)
        since = _utcnow_naive() - timedelta(hours=hours_ago)

        query = (
            select(Recording)
            .where(Recording.org_id == org_id, Recording.start_time >= since)
        )

        if params.get("camera_name"):
            camera_sub = select(Camera.id).where(
                Camera.org_id == org_id,
                Camera.name.ilike(f"%{params['camera_name']}%"),
            )
            query = query.where(Recording.camera_id.in_(camera_sub))

        if params.get("recording_type"):
            from app.models.recording import RecordingType
            try:
                query = query.where(
                    Recording.recording_type == RecordingType(params["recording_type"])
                )
            except ValueError:
                pass

        count_q = select(func.count()).select_from(query.subquery())
        total = (await db.execute(count_q)).scalar() or 0

        query = query.order_by(Recording.start_time.desc()).limit(limit)
        result = await db.execute(query)
        recordings = result.scalars().all()

        rows = []
        for r in recordings:
            cam_result = await db.execute(
                select(Camera.name).where(Camera.id == r.camera_id)
            )
            cam_name = cam_result.scalar_one_or_none() or "Unknown"

            duration_str = "N/A"
            if r.duration_seconds:
                mins = int(r.duration_seconds // 60)
                secs = int(r.duration_seconds % 60)
                duration_str = f"{mins}m {secs}s"

            size_str = "N/A"
            if r.file_size_bytes:
                mb = r.file_size_bytes / (1024 * 1024)
                size_str = f"{mb:.1f} MB"

            rows.append({
                "id": str(r.id),
                "camera": cam_name,
                "type": r.recording_type.value if r.recording_type else "",
                "start": r.start_time.isoformat() if r.start_time else "",
                "end": r.end_time.isoformat() if r.end_time else "In progress",
                "duration": duration_str,
                "size": size_str,
            })

        result_data = {
            "total": total,
            "returned": len(rows),
            "time_range": f"Last {hours_ago} hours",
            "recordings": rows,
        }

        cards: list[dict[str, Any]] = []
        if rows:
            cards.append({
                "type": "table",
                "title": f"Recordings ({len(rows)} of {total})",
                "data": {
                    "headers": ["Camera", "Type", "Start", "Duration", "Size"],
                    "rows": [
                        [r["camera"], r["type"], r["start"], r["duration"], r["size"]]
                        for r in rows[:10]
                    ],
                },
            })

        return result_data, cards

    async def _get_system_health(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        params: dict[str, Any] | None = None,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Get overall system health status."""
        if params is None:
            params = {}

        # Camera stats
        total_cameras = (await db.execute(
            select(func.count()).select_from(Camera).where(Camera.org_id == org_id)
        )).scalar() or 0

        online_cameras = (await db.execute(
            select(func.count()).select_from(Camera).where(
                Camera.org_id == org_id, Camera.is_online.is_(True)
            )
        )).scalar() or 0

        # Alert stats (last 24h)
        since_24h = _utcnow_naive() - timedelta(hours=24)
        alerts_24h = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id, Alert.created_at >= since_24h
            )
        )).scalar() or 0

        critical_24h = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id,
                Alert.created_at >= since_24h,
                Alert.severity == RuleSeverity.CRITICAL,
            )
        )).scalar() or 0

        unresolved = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id,
                Alert.status.in_([AlertStatus.NEW, AlertStatus.ESCALATED]),
            )
        )).scalar() or 0

        # Rules
        active_rules = (await db.execute(
            select(func.count()).select_from(Rule).where(
                Rule.org_id == org_id, Rule.is_active.is_(True)
            )
        )).scalar() or 0

        total_rules = (await db.execute(
            select(func.count()).select_from(Rule).where(Rule.org_id == org_id)
        )).scalar() or 0

        # Persons and vehicles
        total_persons = (await db.execute(
            select(func.count()).select_from(Person).where(Person.org_id == org_id)
        )).scalar() or 0

        total_vehicles = (await db.execute(
            select(func.count()).select_from(Vehicle).where(Vehicle.org_id == org_id)
        )).scalar() or 0

        # Recordings storage (last 7 days)
        since_7d = _utcnow_naive() - timedelta(days=7)
        storage_result = await db.execute(
            select(func.sum(Recording.file_size_bytes)).where(
                Recording.org_id == org_id,
                Recording.start_time >= since_7d,
            )
        )
        total_storage_bytes = storage_result.scalar() or 0
        storage_gb = round(total_storage_bytes / (1024 ** 3), 2)

        # Users
        total_users = (await db.execute(
            select(func.count()).select_from(User).where(
                User.org_id == org_id, User.is_active.is_(True)
            )
        )).scalar() or 0

        camera_health_pct = round(
            (online_cameras / total_cameras * 100) if total_cameras > 0 else 0, 1
        )
        overall_status = "healthy"
        if camera_health_pct < 50:
            overall_status = "degraded"
        elif camera_health_pct < 80:
            overall_status = "warning"
        if critical_24h > 0 and unresolved > 5:
            overall_status = "attention_needed"

        result_data = {
            "overall_status": overall_status,
            "cameras": {
                "total": total_cameras,
                "online": online_cameras,
                "offline": total_cameras - online_cameras,
                "health_pct": camera_health_pct,
            },
            "alerts_24h": {
                "total": alerts_24h,
                "critical": critical_24h,
                "unresolved": unresolved,
            },
            "rules": {
                "total": total_rules,
                "active": active_rules,
            },
            "face_database": {
                "total_persons": total_persons,
            },
            "vehicle_database": {
                "total_vehicles": total_vehicles,
            },
            "storage": {
                "last_7_days_gb": storage_gb,
            },
            "users": {
                "active": total_users,
            },
        }

        cards: list[dict[str, Any]] = [
            {
                "type": "stat",
                "title": "System Status",
                "data": {
                    "label": "Overall Health",
                    "value": overall_status.replace("_", " ").title(),
                    "trend": "up" if overall_status == "healthy" else "down",
                },
            },
            {
                "type": "table",
                "title": "System Overview",
                "data": {
                    "headers": ["Component", "Status", "Details"],
                    "rows": [
                        ["Cameras", f"{online_cameras}/{total_cameras} online", f"{camera_health_pct}% health"],
                        ["Alerts (24h)", str(alerts_24h), f"{critical_24h} critical, {unresolved} unresolved"],
                        ["Detection Rules", f"{active_rules}/{total_rules} active", ""],
                        ["Face Database", f"{total_persons} persons", ""],
                        ["Vehicle Database", f"{total_vehicles} vehicles", ""],
                        ["Storage (7d)", f"{storage_gb} GB", ""],
                        ["Active Users", str(total_users), ""],
                    ],
                },
            },
        ]

        return result_data, cards

    # ------------------------------------------------------------------
    # Follow-up Suggestions
    # ------------------------------------------------------------------

    @staticmethod
    def _generate_followups(user_message: str, response_text: str) -> list[str]:
        """Generate context-aware follow-up question suggestions.

        Uses simple keyword matching on the conversation to suggest
        relevant next questions. This runs locally without an API call.
        """
        combined = (user_message + " " + response_text).lower()
        suggestions: list[str] = []

        if any(kw in combined for kw in ["alert", "intrusion", "violation", "fire"]):
            suggestions.extend([
                "Show me critical alerts from the last hour",
                "Which cameras have the most alerts today?",
                "What is the false positive rate for alerts?",
            ])

        if any(kw in combined for kw in ["camera", "online", "offline", "stream"]):
            suggestions.extend([
                "Which cameras are currently offline?",
                "Show me the camera health overview",
                "What is the uptime for all cameras this week?",
            ])

        if any(kw in combined for kw in ["footfall", "occupancy", "traffic", "people", "count"]):
            suggestions.extend([
                "What are the peak hours for footfall today?",
                "Show occupancy trends for the last 24 hours",
                "Which zones have the highest foot traffic?",
            ])

        if any(kw in combined for kw in ["face", "person", "recognition", "enrolled"]):
            suggestions.extend([
                "How many persons are enrolled in the database?",
                "Show recent face recognition events",
                "List all blacklisted persons",
            ])

        if any(kw in combined for kw in ["vehicle", "plate", "anpr", "parking", "car"]):
            suggestions.extend([
                "Show recent ANPR detections",
                "Are there any blacklisted vehicles detected today?",
                "List vehicles currently parked",
            ])

        if any(kw in combined for kw in ["health", "system", "status", "overview"]):
            suggestions.extend([
                "Show me today's alert summary",
                "How many cameras are recording?",
                "What is the storage usage this week?",
            ])

        if any(kw in combined for kw in ["recording", "video", "footage"]):
            suggestions.extend([
                "Find recordings from the last hour",
                "Show event-triggered recordings today",
                "How much storage are recordings using?",
            ])

        # Deduplicate and limit
        seen: set[str] = set()
        unique: list[str] = []
        for s in suggestions:
            if s.lower() not in seen:
                seen.add(s.lower())
                unique.append(s)
        return unique[:4]

    # ------------------------------------------------------------------
    # Conversation Management
    # ------------------------------------------------------------------

    async def get_conversations(self, user_id: uuid.UUID) -> list[dict[str, Any]]:
        """List all conversations for a user from Redis.

        Returns:
            List of conversation summary dicts sorted by last activity.
        """
        redis = await self._get_redis()
        index_key = f"{_CONV_LIST_PREFIX}{user_id}"
        raw = await redis.get(index_key)

        if not raw:
            return []

        conversations: list[dict[str, Any]] = json.loads(raw)
        # Sort by updated_at descending
        conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        return conversations

    async def get_conversation_detail(
        self, user_id: uuid.UUID, conversation_id: str
    ) -> dict[str, Any] | None:
        """Get full conversation detail with all messages.

        Args:
            user_id: The user's ID.
            conversation_id: The conversation ID to retrieve.

        Returns:
            Conversation detail dict or None if not found.
        """
        redis = await self._get_redis()
        conv_key = f"{_CONV_PREFIX}{user_id}:{conversation_id}"
        raw = await redis.get(conv_key)

        if not raw:
            return None

        messages: list[dict[str, Any]] = json.loads(raw)

        # Derive title from first user message
        title = "New Conversation"
        for msg in messages:
            if msg.get("role") == "user" and msg.get("content"):
                title = msg["content"][:80]
                if len(msg["content"]) > 80:
                    title += "..."
                break

        created_at = messages[0].get("timestamp", "") if messages else ""
        updated_at = messages[-1].get("timestamp", "") if messages else ""

        return {
            "id": conversation_id,
            "title": title,
            "messages": messages,
            "message_count": len(messages),
            "created_at": created_at,
            "updated_at": updated_at,
        }

    async def delete_conversation(
        self, user_id: uuid.UUID, conversation_id: str
    ) -> bool:
        """Delete a conversation from Redis.

        Removes both the conversation data and its index entry.

        Args:
            user_id: The user's ID.
            conversation_id: The conversation ID to delete.

        Returns:
            True if deleted, False if not found.
        """
        redis = await self._get_redis()

        # Delete conversation data
        conv_key = f"{_CONV_PREFIX}{user_id}:{conversation_id}"
        deleted = await redis.delete(conv_key)

        # Remove from index
        index_key = f"{_CONV_LIST_PREFIX}{user_id}"
        raw = await redis.get(index_key)
        if raw:
            conversations = json.loads(raw)
            conversations = [c for c in conversations if c.get("id") != conversation_id]
            await redis.set(index_key, json.dumps(conversations), ex=_CONV_TTL)

        return deleted > 0

    async def get_suggested_questions(
        self, db: AsyncSession, org_id: uuid.UUID
    ) -> list[dict[str, str]]:
        """Generate context-aware suggested questions based on current system state.

        Queries live system data to provide relevant starting questions.
        """
        suggestions: list[dict[str, str]] = []

        # Check for offline cameras
        offline_count = (await db.execute(
            select(func.count()).select_from(Camera).where(
                Camera.org_id == org_id, Camera.is_online.is_(False), Camera.is_active.is_(True)
            )
        )).scalar() or 0

        if offline_count > 0:
            suggestions.append({
                "question": f"There are {offline_count} cameras offline. Show me their details.",
                "category": "cameras",
                "icon": "camera-off",
            })

        # Check for unresolved alerts
        unresolved = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id,
                Alert.status.in_([AlertStatus.NEW, AlertStatus.ESCALATED]),
            )
        )).scalar() or 0

        if unresolved > 0:
            suggestions.append({
                "question": f"Show me the {unresolved} unresolved alerts that need attention.",
                "category": "alerts",
                "icon": "bell-ring",
            })

        # Check for critical alerts today
        # Use naive datetime to match TIMESTAMP WITHOUT TIME ZONE columns
        today_start = _utcnow_naive().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        critical_today = (await db.execute(
            select(func.count()).select_from(Alert).where(
                Alert.org_id == org_id,
                Alert.created_at >= today_start,
                Alert.severity == RuleSeverity.CRITICAL,
            )
        )).scalar() or 0

        if critical_today > 0:
            suggestions.append({
                "question": f"Summarize the {critical_today} critical alerts from today.",
                "category": "alerts",
                "icon": "alert-triangle",
            })

        # Always include standard suggestions
        suggestions.extend([
            {
                "question": "Give me an overview of the system health.",
                "category": "system",
                "icon": "activity",
            },
            {
                "question": "What are the footfall trends for today?",
                "category": "analytics",
                "icon": "bar-chart-2",
            },
            {
                "question": "Show me the latest face recognition events.",
                "category": "faces",
                "icon": "users",
            },
            {
                "question": "List recent ANPR vehicle detections.",
                "category": "vehicles",
                "icon": "car",
            },
            {
                "question": "Which cameras have the most alerts this week?",
                "category": "alerts",
                "icon": "bell",
            },
        ])

        return suggestions[:8]

    # ------------------------------------------------------------------
    # Internal Helpers
    # ------------------------------------------------------------------

    async def _update_conversation_index(
        self,
        redis: Any,
        user_id: uuid.UUID,
        conversation_id: str,
        first_message: str,
        message_count: int,
    ) -> None:
        """Update the conversation list index in Redis.

        Maintains a compact list of conversation summaries per user
        for the sidebar listing.
        """
        index_key = f"{_CONV_LIST_PREFIX}{user_id}"
        raw = await redis.get(index_key)
        conversations: list[dict[str, Any]] = json.loads(raw) if raw else []

        now_iso = datetime.now(timezone.utc).isoformat()

        # Check if conversation already exists in the index
        existing = None
        for conv in conversations:
            if conv.get("id") == conversation_id:
                existing = conv
                break

        if existing:
            existing["last_message"] = first_message[:100]
            existing["message_count"] = message_count
            existing["updated_at"] = now_iso
        else:
            title = first_message[:80]
            if len(first_message) > 80:
                title += "..."
            conversations.append({
                "id": conversation_id,
                "title": title,
                "last_message": first_message[:100],
                "message_count": message_count,
                "created_at": now_iso,
                "updated_at": now_iso,
            })

        # Limit to 50 most recent conversations
        conversations.sort(key=lambda c: c.get("updated_at", ""), reverse=True)
        conversations = conversations[:50]

        await redis.set(index_key, json.dumps(conversations), ex=_CONV_TTL)
