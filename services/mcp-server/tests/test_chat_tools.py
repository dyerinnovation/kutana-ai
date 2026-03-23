"""Unit tests for Chat & Status MCP tools.

Tests each of the 3 chat/status tools by mocking RedisChatStore, RedisTurnManager,
ApiClient, GatewayClient, and MCPIdentity globals in mcp_server.main.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

import mcp_server.main as main_module
from mcp_server.auth import MCPIdentity
from mcp_server.main import (
    convene_get_chat_messages as get_chat_messages,
    convene_get_meeting_status as get_meeting_status,
    convene_send_chat_message as send_chat_message,
)
from convene_core.models.chat import ChatMessage, ChatMessageType

# ---------------------------------------------------------------------------
# Shared test fixtures
# ---------------------------------------------------------------------------

TEST_USER_ID = uuid4()
TEST_AGENT_CONFIG_ID = uuid4()
TEST_MEETING_ID = uuid4()
TEST_SENDER_ID = uuid4()

TEST_IDENTITY = MCPIdentity(
    user_id=TEST_USER_ID,
    agent_config_id=TEST_AGENT_CONFIG_ID,
    name="TestAgent",
    scopes=["meetings:write"],
)

_NOW = datetime(2026, 3, 23, 14, 30, 0, tzinfo=UTC)


def _make_chat_message(
    content: str = "Hello meeting",
    message_type: ChatMessageType = ChatMessageType.TEXT,
    sender_name: str = "TestAgent",
    sequence: int = 1711201800000,
) -> ChatMessage:
    return ChatMessage(
        message_id=uuid4(),
        meeting_id=TEST_MEETING_ID,
        sender_id=TEST_AGENT_CONFIG_ID,
        sender_name=sender_name,
        content=content,
        message_type=message_type,
        sent_at=_NOW,
        sequence=sequence,
    )


def _make_chat_store() -> MagicMock:
    cs = MagicMock()
    cs.send_message = AsyncMock()
    cs.get_messages = AsyncMock()
    cs.clear_meeting = AsyncMock()
    return cs


def _make_turn_manager() -> MagicMock:
    tm = MagicMock()
    tm.get_queue_status = AsyncMock()
    tm.get_active_speaker = AsyncMock()
    return tm


def _make_queue_status(
    active_speaker_id: UUID | None = None,
    queue: list[MagicMock] | None = None,
) -> MagicMock:
    status = MagicMock()
    status.active_speaker_id = active_speaker_id
    status.queue = queue or []
    return status


def _make_api_client() -> MagicMock:
    client = MagicMock()
    client.list_meetings = AsyncMock(return_value=[])
    client.exchange_for_mcp_token = AsyncMock(return_value="token")
    return client


# ---------------------------------------------------------------------------
# send_chat_message
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_send_chat_message_default_type() -> None:
    """send_chat_message stores a text message and returns full message details."""
    cs = _make_chat_store()
    msg = _make_chat_message(content="Hello everyone")
    cs.send_message.return_value = msg

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await send_chat_message(str(TEST_MEETING_ID), "Hello everyone"))

    assert result["content"] == "Hello everyone"
    assert result["message_type"] == "text"
    assert result["sender_name"] == "TestAgent"
    assert "message_id" in result
    assert "sent_at" in result
    assert "sequence" in result

    cs.send_message.assert_awaited_once_with(
        meeting_id=TEST_MEETING_ID,
        sender_id=TEST_AGENT_CONFIG_ID,
        sender_name=TEST_IDENTITY.name,
        content="Hello everyone",
        message_type=ChatMessageType.TEXT,
    )


@pytest.mark.asyncio
async def test_send_chat_message_question_type() -> None:
    """send_chat_message accepts 'question' as message_type."""
    cs = _make_chat_store()
    msg = _make_chat_message(content="What is the timeline?", message_type=ChatMessageType.QUESTION)
    cs.send_message.return_value = msg

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(
            await send_chat_message(str(TEST_MEETING_ID), "What is the timeline?", message_type="question")
        )

    assert result["message_type"] == "question"
    cs.send_message.assert_awaited_once_with(
        meeting_id=TEST_MEETING_ID,
        sender_id=TEST_AGENT_CONFIG_ID,
        sender_name=TEST_IDENTITY.name,
        content="What is the timeline?",
        message_type=ChatMessageType.QUESTION,
    )


@pytest.mark.asyncio
async def test_send_chat_message_action_item_type() -> None:
    """send_chat_message accepts 'action_item' as message_type."""
    cs = _make_chat_store()
    msg = _make_chat_message(content="Review PR by Friday", message_type=ChatMessageType.ACTION_ITEM)
    cs.send_message.return_value = msg

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(
            await send_chat_message(str(TEST_MEETING_ID), "Review PR by Friday", message_type="action_item")
        )

    assert result["message_type"] == "action_item"


@pytest.mark.asyncio
async def test_send_chat_message_invalid_type() -> None:
    """send_chat_message returns error JSON for invalid message_type."""
    cs = _make_chat_store()

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(
            await send_chat_message(str(TEST_MEETING_ID), "Hello", message_type="invalid_type")
        )

    assert "error" in result
    assert "invalid_type" in result["error"]
    cs.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_send_chat_message_decision_type() -> None:
    """send_chat_message accepts 'decision' and passes it to the store."""
    cs = _make_chat_store()
    msg = _make_chat_message(content="We ship v2 next week", message_type=ChatMessageType.DECISION)
    cs.send_message.return_value = msg

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(
            await send_chat_message(str(TEST_MEETING_ID), "We ship v2 next week", message_type="decision")
        )

    assert result["message_type"] == "decision"


# ---------------------------------------------------------------------------
# get_chat_messages
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_chat_messages_returns_list() -> None:
    """get_chat_messages returns chronological list of messages."""
    cs = _make_chat_store()
    msgs = [
        _make_chat_message(content="First", sequence=1000),
        _make_chat_message(content="Second", sequence=2000),
    ]
    cs.get_messages.return_value = msgs

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_chat_messages(str(TEST_MEETING_ID)))

    assert isinstance(result, list)
    assert len(result) == 2
    assert result[0]["content"] == "First"
    assert result[1]["content"] == "Second"


@pytest.mark.asyncio
async def test_get_chat_messages_empty_meeting() -> None:
    """get_chat_messages returns empty list when no messages exist."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_chat_messages(str(TEST_MEETING_ID)))

    assert result == []
    cs.get_messages.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_chat_messages_with_limit() -> None:
    """get_chat_messages passes limit to the store."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await get_chat_messages(str(TEST_MEETING_ID), limit=10)

    call_kwargs = cs.get_messages.call_args.kwargs
    assert call_kwargs["limit"] == 10


@pytest.mark.asyncio
async def test_get_chat_messages_limit_clamped_to_max() -> None:
    """get_chat_messages clamps limit to 200 maximum."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await get_chat_messages(str(TEST_MEETING_ID), limit=9999)

    call_kwargs = cs.get_messages.call_args.kwargs
    assert call_kwargs["limit"] == 200


@pytest.mark.asyncio
async def test_get_chat_messages_with_message_type_filter() -> None:
    """get_chat_messages passes message_type filter to the store."""
    cs = _make_chat_store()
    cs.get_messages.return_value = [_make_chat_message(message_type=ChatMessageType.QUESTION)]

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_chat_messages(str(TEST_MEETING_ID), message_type="question"))

    call_kwargs = cs.get_messages.call_args.kwargs
    assert call_kwargs["message_type"] == ChatMessageType.QUESTION
    assert result[0]["message_type"] == "question"


@pytest.mark.asyncio
async def test_get_chat_messages_invalid_message_type() -> None:
    """get_chat_messages returns error for invalid message_type filter."""
    cs = _make_chat_store()

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_chat_messages(str(TEST_MEETING_ID), message_type="nonsense"))

    assert "error" in result
    cs.get_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_chat_messages_with_since_timestamp() -> None:
    """get_chat_messages parses ISO 8601 since timestamp and passes to store."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        await get_chat_messages(str(TEST_MEETING_ID), since="2026-03-23T14:00:00Z")

    call_kwargs = cs.get_messages.call_args.kwargs
    since_dt = call_kwargs["since"]
    assert since_dt is not None
    assert since_dt.year == 2026
    assert since_dt.month == 3
    assert since_dt.day == 23


@pytest.mark.asyncio
async def test_get_chat_messages_invalid_since_timestamp() -> None:
    """get_chat_messages returns error for unparseable since timestamp."""
    cs = _make_chat_store()

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_chat_messages(str(TEST_MEETING_ID), since="not-a-date"))

    assert "error" in result
    cs.get_messages.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_chat_messages_response_fields() -> None:
    """get_chat_messages includes all expected fields in each message."""
    cs = _make_chat_store()
    cs.get_messages.return_value = [_make_chat_message()]

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
    ):
        result = json.loads(await get_chat_messages(str(TEST_MEETING_ID)))

    msg = result[0]
    assert "message_id" in msg
    assert "sender_id" in msg
    assert "sender_name" in msg
    assert "content" in msg
    assert "message_type" in msg
    assert "sent_at" in msg
    assert "sequence" in msg


# ---------------------------------------------------------------------------
# get_meeting_status
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_meeting_status_structure() -> None:
    """get_meeting_status returns meeting, queue, participants, and recent_chat keys."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()
    client = _make_api_client()
    client.list_meetings.return_value = []

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_api_client", client),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_gateway_client", None),
    ):
        result = json.loads(await get_meeting_status(str(TEST_MEETING_ID)))

    assert "meeting" in result
    assert "queue" in result
    assert "participants" in result
    assert "recent_chat" in result


@pytest.mark.asyncio
async def test_get_meeting_status_finds_meeting() -> None:
    """get_meeting_status returns the matching meeting from the list."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()
    client = _make_api_client()
    client.list_meetings.return_value = [
        {"id": str(TEST_MEETING_ID), "title": "Sprint Review", "status": "active"},
        {"id": str(uuid4()), "title": "Other Meeting", "status": "scheduled"},
    ]

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_api_client", client),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_gateway_client", None),
    ):
        result = json.loads(await get_meeting_status(str(TEST_MEETING_ID)))

    assert result["meeting"] is not None
    assert result["meeting"]["title"] == "Sprint Review"


@pytest.mark.asyncio
async def test_get_meeting_status_queue_info() -> None:
    """get_meeting_status includes active_speaker and queue_length."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []
    tm = _make_turn_manager()
    speaker_id = uuid4()
    tm.get_queue_status.return_value = _make_queue_status(active_speaker_id=speaker_id)
    client = _make_api_client()

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_api_client", client),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_gateway_client", None),
    ):
        result = json.loads(await get_meeting_status(str(TEST_MEETING_ID)))

    assert result["queue"]["active_speaker"] == str(speaker_id)
    assert result["queue"]["queue_length"] == 0


@pytest.mark.asyncio
async def test_get_meeting_status_recent_chat() -> None:
    """get_meeting_status includes up to 10 recent chat messages."""
    cs = _make_chat_store()
    recent = [_make_chat_message(content=f"Message {i}") for i in range(3)]
    cs.get_messages.return_value = recent
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()
    client = _make_api_client()

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_api_client", client),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_gateway_client", None),
    ):
        result = json.loads(await get_meeting_status(str(TEST_MEETING_ID)))

    assert len(result["recent_chat"]) == 3
    assert result["recent_chat"][0]["content"] == "Message 0"

    # Verify the chat was requested with limit=10
    cs.get_messages.assert_awaited_once_with(TEST_MEETING_ID, limit=10)


@pytest.mark.asyncio
async def test_get_meeting_status_recent_chat_fields() -> None:
    """recent_chat entries have sender_name, content, message_type, sent_at."""
    cs = _make_chat_store()
    cs.get_messages.return_value = [_make_chat_message(content="Status update")]
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()
    client = _make_api_client()

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_api_client", client),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_gateway_client", None),
    ):
        result = json.loads(await get_meeting_status(str(TEST_MEETING_ID)))

    chat_entry = result["recent_chat"][0]
    assert chat_entry["content"] == "Status update"
    assert "sender_name" in chat_entry
    assert "message_type" in chat_entry
    assert "sent_at" in chat_entry


@pytest.mark.asyncio
async def test_get_meeting_status_unknown_meeting() -> None:
    """get_meeting_status returns null meeting when meeting_id not in list."""
    cs = _make_chat_store()
    cs.get_messages.return_value = []
    tm = _make_turn_manager()
    tm.get_queue_status.return_value = _make_queue_status()
    client = _make_api_client()
    client.list_meetings.return_value = [
        {"id": str(uuid4()), "title": "Other Meeting", "status": "active"},
    ]

    with (
        patch.object(main_module, "_chat_store", cs),
        patch.object(main_module, "_turn_manager", tm),
        patch.object(main_module, "_api_client", client),
        patch.object(main_module, "_mcp_identity", TEST_IDENTITY),
        patch.object(main_module, "_gateway_client", None),
    ):
        result = json.loads(await get_meeting_status(str(TEST_MEETING_ID)))

    assert result["meeting"] is None
