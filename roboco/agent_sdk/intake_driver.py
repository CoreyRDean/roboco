"""Intake agent driver — a long-lived Claude Code session the human chats with.

The intake (``prompter``) agent is not a one-shot ``claude -p`` like every other
RoboCo agent; it is an interactive session. This driver is the container's
entrypoint: it opens ONE ``claude-agent-sdk`` ``ClaudeSDKClient`` (Claude Code
held open), then loops — pull the human's next message, stream the agent's reply
(token deltas, tool calls), wait for the next message — keeping conversation
context in-process. The container stays alive for the whole chat and is reaped
when the draft becomes a task.

The SDK call surface is isolated in ``SdkIntakeSession`` (lazy import, so this
module imports without ``claude-agent-sdk`` installed). The loop
(``IntakeDriver``) and event normalization are SDK-free and unit-tested with
fakes.
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Protocol

import structlog

if TYPE_CHECKING:
    from contextlib import AbstractAsyncContextManager

logger = structlog.get_logger()

# The intake agent emits the finished structured task draft as a fenced block
# (see the prompter system prompt). The driver mines it from the complete reply
# and surfaces it as one ``draft`` chunk for the panel's draft card.
_DRAFT_FENCE = re.compile(r"```roboco-draft\s*\n(.*?)```", re.DOTALL)


# ---------------------------------------------------------------------------
# Normalized stream chunk — what the panel SSE consumes. SDK-free.
# ---------------------------------------------------------------------------


@dataclass
class StreamChunk:
    """One normalized event in the agent's live reply.

    ``kind`` is the panel-facing event type; the rest is payload. Decoupled
    from the SDK's message classes so the relay/panel never import the SDK.
    Kinds: text, thinking, tool_use, tool_result, turn_end, system, draft,
    goal_edit, error.
    """

    kind: str
    text: str = ""
    tool: str = ""
    data: dict[str, Any] = field(default_factory=dict)


def _coerce_draft(data: Any) -> dict[str, Any] | None:
    """Return ``data`` as a draft dict (with a string ``title``), else ``None``.

    Accepts a dict, or a JSON string the agent may have passed.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            return None
    if isinstance(data, dict) and isinstance(data.get("title"), str):
        return data
    return None


def _extract_draft(text: str) -> dict[str, Any] | None:
    """Parse a fenced ``roboco-draft`` JSON block out of the agent's reply.

    A fallback to the ``propose_draft`` tool: returns the parsed object (a dict
    with a string ``title``) or ``None`` when no well-formed block is present.
    """
    match = _DRAFT_FENCE.search(text)
    if match is None:
        return None
    return _coerce_draft(match.group(1))


def _draft_from_tool_input(tool_input: Any) -> dict[str, Any] | None:
    """Pull the draft out of a ``propose_draft`` tool call's input.

    Tolerant of both shapes the agent might use: the draft nested under a
    ``draft`` key, or the draft fields passed flat as the input itself.
    """
    if not isinstance(tool_input, dict):
        return None
    return _coerce_draft(tool_input.get("draft", tool_input))


def _is_propose_draft(name: str) -> bool:
    """True for the intake ``propose_draft`` tool, however the SDK namespaces it."""
    return name == "propose_draft" or name.endswith("__propose_draft")


def _is_propose_goal_edit(name: str) -> bool:
    """True for the ``propose_goal_edit`` tool, however the SDK namespaces it.

    The Secretary's goal-editing seam mirrors ``propose_draft``: the agent calls
    the tool, the driver intercepts it and surfaces a confirmable ``goal_edit``
    chunk. The actual CEO-authenticated ``PUT /api/goals`` happens when the human
    confirms the card in the panel (the container has no CEO authority), so the
    change lands in the SAME Business Goals artifact the panel editor writes.
    """
    return name == "propose_goal_edit" or name.endswith("__propose_goal_edit")


def _coerce_goal_edit(data: Any) -> dict[str, Any] | None:
    """Return ``data`` as a goal-edit patch dict, else ``None``.

    Accepts a dict or a JSON string. A valid patch carries at least one of the
    editable Business Goals fields (``north_star``, ``objectives``,
    ``operating_policy``, ``constraints``) — an empty object is not a usable
    edit and is dropped, mirroring the ``propose_draft`` "needs a title" guard.
    """
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except (ValueError, TypeError):
            return None
    if not isinstance(data, dict):
        return None
    fields = ("north_star", "objectives", "operating_policy", "constraints")
    if any(data.get(f) is not None for f in fields):
        return data
    return None


def _goal_edit_from_tool_input(tool_input: Any) -> dict[str, Any] | None:
    """Pull the goal-edit patch out of a ``propose_goal_edit`` tool call's input.

    Tolerant of both shapes: the patch nested under an ``edit`` key, or the patch
    fields passed flat as the input itself (mirrors ``_draft_from_tool_input``).
    """
    if not isinstance(tool_input, dict):
        return None
    return _coerce_goal_edit(tool_input.get("edit", tool_input))


@dataclass
class _BlockParts:
    """What one assistant content block decomposes into for ``_blocks_to_chunks``.

    A block contributes at most one of these: a normalized ``chunk`` (thinking /
    tool_use), a ``text_part`` (already streamed live; mined for a fenced draft),
    a ``draft`` (``propose_draft``), or a ``goal_edit`` patch
    (``propose_goal_edit``). Unset fields stay ``None``.
    """

    chunk: StreamChunk | None = None
    text_part: str | None = None
    draft: dict[str, Any] | None = None
    goal_edit: dict[str, Any] | None = None


def _block_to_chunk(block: Any) -> _BlockParts:
    """Classify one assistant content block into its contribution.

    ``propose_draft`` yields a draft; ``propose_goal_edit`` yields a goal-edit
    patch; thinking / other tool_use yield a chunk; a TextBlock yields a
    text_part (already streamed live, mined for a fenced draft by the caller).
    Unknown blocks yield an empty result.
    """
    if hasattr(block, "thinking"):  # ThinkingBlock
        return _BlockParts(chunk=StreamChunk(kind="thinking", text=str(block.thinking)))
    if hasattr(block, "name") and hasattr(block, "input"):  # ToolUseBlock
        name = str(block.name)
        tool_input = getattr(block, "input", {})
        if _is_propose_draft(name):
            return _BlockParts(draft=_draft_from_tool_input(tool_input))
        if _is_propose_goal_edit(name):
            return _BlockParts(goal_edit=_goal_edit_from_tool_input(tool_input))
        return _BlockParts(
            chunk=StreamChunk(kind="tool_use", tool=name, data={"input": tool_input})
        )
    if hasattr(block, "text"):  # TextBlock — already streamed; mine for a draft
        return _BlockParts(text_part=str(block.text))
    return _BlockParts()


def _blocks_to_chunks(content: list[Any]) -> list[StreamChunk]:
    """Map an assistant message's content blocks to chunks (duck-typed).

    Text is deliberately NOT re-emitted here: with ``include_partial_messages``
    the live token deltas (``StreamEvent``) already streamed it, so re-emitting
    the complete ``TextBlock`` would render every reply twice on the panel.

    The canonical draft signal is the agent calling the **``propose_draft``**
    tool — that ToolUseBlock becomes a single ``draft`` chunk. As a fallback (if
    the agent types the spec instead of calling the tool) the complete text is
    also mined for a fenced ``roboco-draft`` block. thinking + other tool_use
    (which do NOT arrive as deltas) are emitted as before.

    The Secretary's **``propose_goal_edit``** tool is handled the same way: it
    becomes a single ``goal_edit`` chunk the panel renders as a confirmable card
    (the CEO confirms it, and the panel applies the patch as the CEO).
    """
    chunks: list[StreamChunk] = []
    text_parts: list[str] = []
    draft: dict[str, Any] | None = None
    goal_edit: dict[str, Any] | None = None
    for block in content or []:
        parts = _block_to_chunk(block)
        if parts.chunk is not None:
            chunks.append(parts.chunk)
        if parts.text_part is not None:
            text_parts.append(parts.text_part)
        draft = draft or parts.draft
        goal_edit = goal_edit or parts.goal_edit
    draft = draft or _extract_draft("".join(text_parts))
    if draft is not None:
        chunks.append(StreamChunk(kind="draft", data=draft))
    if goal_edit is not None:
        chunks.append(StreamChunk(kind="goal_edit", data=goal_edit))
    return chunks


def _stream_event_to_chunks(msg: Any) -> list[StreamChunk]:
    """Extract a live text delta from a partial StreamEvent (token streaming)."""
    event = getattr(msg, "event", None) or {}
    delta = event.get("delta") if isinstance(event, dict) else None
    if isinstance(delta, dict) and delta.get("type") == "text_delta":
        text = str(delta.get("text", ""))
        if text:
            return [StreamChunk(kind="text", text=text)]
    return []


def normalize(msg: Any) -> list[StreamChunk]:
    """Map a single ``claude-agent-sdk`` message to panel-facing chunks.

    Duck-typed on type name + attributes so it works on real SDK messages and
    on test fakes alike (no SDK import required).
    """
    name = type(msg).__name__
    if name == "StreamEvent":
        return _stream_event_to_chunks(msg)
    if name == "AssistantMessage":
        return _blocks_to_chunks(getattr(msg, "content", []))
    if name == "ResultMessage":
        return [
            StreamChunk(
                kind="turn_end",
                data={
                    "session_id": getattr(msg, "session_id", None),
                    "cost_usd": getattr(msg, "total_cost_usd", None),
                },
            )
        ]
    if name == "SystemMessage":
        return [
            StreamChunk(kind="system", data={"subtype": getattr(msg, "subtype", "")})
        ]
    return []


# ---------------------------------------------------------------------------
# Session seam — one conversational turn -> a stream of chunks.
# ---------------------------------------------------------------------------


class IntakeSession(Protocol):
    """A live agent session. ``send`` runs one turn and streams its chunks."""

    def send(self, text: str) -> AsyncIterator[StreamChunk]: ...


# A factory that yields an async-context-managed IntakeSession (opens/closes
# the underlying client). Injected so the driver loop is testable with a fake.
SessionFactory = Callable[[], "AbstractAsyncContextManager[IntakeSession]"]
# Source of the human's messages (e.g. the in-container inbox). Returns None to
# signal shutdown (container being reaped).
MessageSource = Callable[[], Awaitable[str | None]]
# Where normalized chunks go (the relay -> panel SSE).
EventSink = Callable[[StreamChunk], Awaitable[None]]


# ---------------------------------------------------------------------------
# The driver loop — SDK-free, unit-tested with fakes.
# ---------------------------------------------------------------------------


class IntakeDriver:
    """Owns the chat loop for the lifetime of one intake session."""

    def __init__(
        self,
        session_factory: SessionFactory,
        next_message: MessageSource,
        emit: EventSink,
    ) -> None:
        self._session_factory = session_factory
        self._next_message = next_message
        self._emit = emit
        self.log = logger.bind(component="intake_driver")

    async def run(self) -> None:
        """Open the session and process human turns until shutdown.

        One ``ClaudeSDKClient`` is held open across all turns (context persists
        in-process). The loop ends when ``next_message`` returns ``None``.
        """
        async with self._session_factory() as session:
            self.log.info("Intake session opened")
            turns = 0
            while True:
                text = await self._next_message()
                if text is None:
                    self.log.info("Intake session closing", turns=turns)
                    return
                turns += 1
                self.log.info("Intake turn received", turn=turns, chars=len(text))
                await self._run_turn(session, text)

    async def _run_turn(self, session: IntakeSession, text: str) -> None:
        """Stream one turn's chunks to the sink, logging each tool call.

        The conversation streams to the relay (panel), not stdout — so without
        this, ``docker logs`` on the intake container is a black box between turn
        start and end even while the agent reads the codebase and spawns subagents.
        Logging each ``tool_use`` (and the draft) shows the turn's real shape;
        text deltas are intentionally NOT logged (they'd spam). A failure ends as
        an error chunk.
        """
        chunks = 0
        tools = 0
        drafted = False
        try:
            async for chunk in session.send(text):
                chunks += 1
                if chunk.kind == "tool_use":
                    tools += 1
                    self.log.info("Intake tool use", tool=chunk.tool)
                elif chunk.kind == "draft":
                    drafted = True
                    self.log.info("Intake draft emitted")
                elif chunk.kind == "goal_edit":
                    self.log.info("Secretary goal-edit proposed")
                await self._emit(chunk)
        except Exception as exc:
            self.log.error("Intake turn failed", error=str(exc), chunks=chunks)
            await self._emit(StreamChunk(kind="error", text=str(exc)))
        else:
            self.log.info(
                "Intake turn streamed", chunks=chunks, tools=tools, drafted=drafted
            )


# ---------------------------------------------------------------------------
# Orchestrator HTTP bridge — how the Secretary's read tools see the company.
# Mirrors roboco/mcp/flow_server.py's bridge: env-driven base URL + the
# container's own agent-identity headers. SDK-free and unit-testable.
# ---------------------------------------------------------------------------


def _orchestrator_base_url() -> str:
    """Base URL of the orchestrator API (defaults to the docker-network host).

    ``ROBOCO_API_URL`` is the same env the intake container already carries
    (set by the orchestrator's intake spawn); fall back to the service DNS name
    so a bare ``docker run`` still reaches it.
    """
    return os.environ.get("ROBOCO_API_URL", "http://roboco-orchestrator:8000")


def _orchestrator_headers() -> dict[str, str]:
    """Agent-identity headers for the read tools (the flow_server pattern).

    The Secretary reads company state on the CEO's behalf, but it authenticates
    as its OWN identity (``intake-1`` / ``prompter``) — the read endpoints
    (``GET /api/goals``, ``/api/secretary/status|queue``) accept any
    authenticated agent. ``X-Agent-Token`` is forwarded when present so the calls
    keep working under ``ROBOCO_AGENT_AUTH_REQUIRED`` (the orchestrator only
    issues a token into the container env in that mode).
    """
    headers = {
        "X-Agent-ID": os.environ.get("ROBOCO_AGENT_ID", "intake-1"),
        "X-Agent-Role": os.environ.get("ROBOCO_AGENT_ROLE", "prompter"),
    }
    token = os.environ.get("ROBOCO_AGENT_TOKEN")
    if token:
        headers["X-Agent-Token"] = token
    return headers


def _ceo_headers() -> dict[str, str]:
    """CEO-identity headers for the Secretary's ACTION tools.

    The Secretary is the CEO's human-only interface and acts on the CEO's
    behalf (INTENT.md §2/§3), so its *action* tools authenticate **as the
    CEO** — ``X-Agent-ID`` = the CEO UUID, ``X-Agent-Role`` = ``ceo`` — using
    the CEO-scoped token the orchestrator injected (``ROBOCO_SECRETARY_CEO_*``,
    signed by the same signer the panel uses). This is distinct from
    ``_orchestrator_headers`` (the read tools' own prompter identity): the read
    surfaces accept any authenticated agent, but creating tasks / editing goals /
    messaging / announcing requires CEO authority.

    Falls back to the container's own identity when the CEO env is absent (e.g.
    auth disabled in a dev/test run) so the tools still function locally.
    """
    headers = {
        "X-Agent-ID": os.environ.get(
            "ROBOCO_SECRETARY_CEO_ID", os.environ.get("ROBOCO_AGENT_ID", "intake-1")
        ),
        "X-Agent-Role": os.environ.get("ROBOCO_SECRETARY_CEO_ROLE", "ceo"),
    }
    token = os.environ.get("ROBOCO_SECRETARY_CEO_TOKEN") or os.environ.get(
        "ROBOCO_AGENT_TOKEN"
    )
    if token:
        headers["X-Agent-Token"] = token
    return headers


async def _orchestrator_get(path: str) -> dict[str, Any]:
    """GET a read surface from the orchestrator, returning a tool-content dict.

    Returns the standard MCP tool result shape (a ``content`` list with one text
    block of the JSON body, or a readable error) so a read tool can ``return``
    it directly. Never raises — a failed read becomes an error message the agent
    can relay to the CEO rather than a stalled turn.
    """
    import httpx

    url = f"{_orchestrator_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(url, headers=_orchestrator_headers())
            response.raise_for_status()
            payload = response.json()
        text = json.dumps(payload, indent=2, default=str)
    except Exception as exc:
        logger.error("Secretary read failed", path=path, error=str(exc))
        text = f"Could not read {path}: {exc}"
    return {"content": [{"type": "text", "text": text}]}


async def _orchestrator_ceo_write(
    method: str, path: str, body: dict[str, Any]
) -> dict[str, Any]:
    """POST/PUT to an orchestrator surface AS THE CEO, returning a tool dict.

    Backs the Secretary's *action* tools — the ones that act directly on the
    CEO's word (create a task, edit goals, message an agent, announce). Uses the
    CEO-identity headers (``_ceo_headers``) so the server authorizes the write
    as the CEO. Like ``_orchestrator_get`` it never raises: a failed write
    becomes a readable error the agent can relay to the CEO rather than a
    stalled turn. The full response body is returned so the agent can confirm
    exactly what happened (e.g. a gate decision: executed vs. gated).
    """
    import httpx

    url = f"{_orchestrator_base_url()}{path}"
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.request(
                method, url, headers=_ceo_headers(), json=body
            )
            response.raise_for_status()
            payload = response.json()
        text = json.dumps(payload, indent=2, default=str)
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        logger.error("Secretary action failed", path=path, error=detail)
        text = f"{method} {path} failed ({exc.response.status_code}): {detail}"
    except Exception as exc:
        logger.error("Secretary action failed", path=path, error=str(exc))
        text = f"Could not {method} {path}: {exc}"
    return {"content": [{"type": "text", "text": text}]}


# ---------------------------------------------------------------------------
# SDK adapter — the only SDK-coupled code (lazy import). Verified against
# claude-agent-sdk; not exercised in the gate (needs the live claude binary).
# ---------------------------------------------------------------------------


# The intake agent's hard tool allowlist: read-only built-ins + the draft tool.
_INTAKE_BASE_TOOLS: tuple[str, ...] = ("Read", "Grep", "Glob", "Task")

# The Secretary's MCP tools, by bare name. The ``_gate`` allows exactly these
# (however the SDK namespaces them) and nothing else; ``allowed_tools`` lists
# their fully-namespaced forms. Three groups:
#   - reads (3.D1): read_goals / read_status / read_queue — own (prompter) auth.
#   - proposals: propose_draft (intake card) + propose_goal_edit (confirm-card
#     path) — surfaced to the CEO for confirmation, no direct side effect.
#   - CEO actions: create_task / update_goals / message_agent / announce /
#     surface — act DIRECTLY on the CEO's word, authenticated AS THE CEO. The
#     gated guardrail (spend / go_public / new_product_line / cap_breach) is
#     enforced server-side: a gated action is surfaced to the CEO action queue
#     instead of executing.
_SECRETARY_MCP_TOOLS: tuple[str, ...] = (
    "propose_draft",
    "read_goals",
    "read_status",
    "read_queue",
    "read_task",
    "propose_goal_edit",
    "create_task",
    "update_goals",
    "message_agent",
    "announce",
    "surface",
)


def _is_secretary_mcp_tool(name: str) -> bool:
    """True for any Secretary MCP tool, however the SDK namespaces the name."""
    return any(name == t or name.endswith(f"__{t}") for t in _SECRETARY_MCP_TOOLS)


def build_intake_options(
    *,
    system_prompt: str,
    cwd: str,
    model: str | None = None,
) -> Any:  # pragma: no cover - thin SDK construction
    """Build locked-down ``ClaudeAgentOptions`` for the Secretary session.

    Isolation/security: the Secretary agent must NOT inherit the host's personal
    Claude Code env (Gmail/Notion MCP, Write/Edit/Bash). So:

    - ``strict_mcp_config=True`` + ``setting_sources=[]`` → ignore the host's
      ``~/.claude.json`` / ``settings.json``; use ONLY the MCP server below.
    - ``permission_mode="dontAsk"`` (NOT ``bypassPermissions``) + a ``can_use_tool``
      gate → a hard allowlist (Read/Grep/Glob/Task + the Secretary MCP tools),
      no prompts.

    Secretary MCP tools (``_SECRETARY_MCP_TOOLS``):

    - ``propose_draft`` — KEPT: emit a task-draft card (the original intake job).
    - ``read_goals`` / ``read_status`` / ``read_queue`` — read-only company state
      so the Secretary can brief the CEO (3.D1); each GETs an orchestrator read
      surface via the HTTP bridge above and returns the JSON to the agent.
    - ``propose_goal_edit`` — propose a Business Goals change (3.D2); like
      ``propose_draft`` the driver turns it into a confirmable ``goal_edit`` card,
      and the CEO-authenticated panel applies the patch to the SAME artifact the
      Panel editor writes (``PUT /api/goals``).
    - ``create_task`` / ``update_goals`` / ``message_agent`` / ``announce`` /
      ``surface`` — the Secretary's CEO-authority ACTION tools: they act DIRECTLY
      on the CEO's word (not a confirm-card round-trip). They authenticate as the
      CEO via ``_ceo_headers`` (the CEO-scoped token the orchestrator injected),
      and the gated guardrail (spend / go_public / new_product_line / cap_breach)
      is enforced server-side — a gated action is surfaced to the CEO action
      queue instead of executing.

    Draft / goal-edit emission is deterministic via the MCP tool call → driver
    interception, not a fragile text fence.

    NOTE: ``setting_sources=[]`` must be validated against the mounted-``~/.claude``
    auth on the next smoke; if auth breaks, narrow it instead of removing it.
    """
    from claude_agent_sdk import (
        ClaudeAgentOptions,
        PermissionResultAllow,
        PermissionResultDeny,
        create_sdk_mcp_server,
        tool,
    )

    @tool(
        "propose_draft",
        "Submit the finished task draft for the human to review and confirm. Call "
        "this once the spec is complete. Pass a JSON object: title, objective, "
        "what_this_builds[], the_work[] ({team, summary, items}), notes[], "
        "acceptance_criteria[], team, scale, task_type, nature, "
        "estimated_complexity, priority.",
        {"draft": dict},
    )
    async def _propose_draft(_args: dict[str, Any]) -> dict[str, Any]:
        # The driver intercepts this tool call (ToolUseBlock) and emits the draft
        # event; the handler only acknowledges so the agent knows it landed.
        return {
            "content": [
                {"type": "text", "text": "Draft submitted — the human can review it."}
            ]
        }

    @tool(
        "read_goals",
        "Read the live Business Goals charter (north star, objectives, operating "
        "policy, constraints). Call this to ground a status brief or before "
        "proposing a goal edit, so you know the current state. Takes no arguments.",
        {},
    )
    async def _read_goals(_args: dict[str, Any]) -> dict[str, Any]:
        return await _orchestrator_get("/api/goals")

    @tool(
        "read_status",
        "Read a compact company status: in-flight work by state, active blockers, "
        "recent activity, and spend vs. budget. Use it to answer 'how are we "
        "doing?' and to brief the CEO. Takes no arguments.",
        {},
    )
    async def _read_status(_args: dict[str, Any]) -> dict[str, Any]:
        return await _orchestrator_get("/api/secretary/status")

    @tool(
        "read_queue",
        "Read the CEO action queue: tasks awaiting CEO approval, board reviews "
        "ready to approve & start, stranded/blocked work needing a human call, and "
        "unacked CEO notifications (pitches, escalations). Walk the CEO through "
        "these one at a time. Takes no arguments.",
        {},
    )
    async def _read_queue(_args: dict[str, Any]) -> dict[str, Any]:
        return await _orchestrator_get("/api/secretary/queue")

    @tool(
        "read_task",
        "Read the FULL details of ONE task or pitch by its id (use the "
        "related_task_id from a queue item or notification): title, status, the "
        "pitch/objective description, acceptance criteria, team, PR. Use this to "
        "actually tell the CEO what an item in the queue is about.",
        {"task_id": str},
    )
    async def _read_task(args: dict[str, Any]) -> dict[str, Any]:
        task_id = str(args.get("task_id", "")).strip()
        if not task_id:
            return {"content": [{"type": "text", "text": "read_task needs a task_id."}]}
        return await _orchestrator_get(f"/api/tasks/{task_id}")

    @tool(
        "propose_goal_edit",
        "Propose a change to the Business Goals charter for the CEO to confirm. "
        "Call this once the CEO has agreed to set or update direction. Pass a JSON "
        "patch with only the fields that change: north_star (string), objectives "
        "(list), operating_policy (object), constraints (list of strings). The CEO "
        "confirms the card and the change lands in the same artifact the Panel "
        "edits — you do not write it yourself.",
        {"edit": dict},
    )
    async def _propose_goal_edit(_args: dict[str, Any]) -> dict[str, Any]:
        # Mirrors propose_draft: the driver intercepts this call and emits the
        # goal_edit card; this handler only acknowledges. The CEO-authenticated
        # panel applies the patch via PUT /api/goals on confirm.
        return {
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Goal edit submitted — the CEO can review and confirm it."
                    ),
                }
            ]
        }

    @tool(
        "create_task",
        "Create a task DIRECTLY (you act with CEO authority). Use this when the "
        "CEO clearly wants a specific piece of work built and there is no need to "
        "round-trip a draft card. Pass a JSON 'task' object with: title, "
        "description (>=20 chars), acceptance_criteria (list), team (backend | "
        "frontend | ux_ui), task_type (code | documentation | research | planning "
        "| design | administrative), nature (technical | ...), "
        "estimated_complexity (low | medium | high | ...), priority (0-3), and "
        "EXACTLY ONE of project_id (single repo) or product_id (cross-cell "
        "fan-out). Returns the created task or a readable error. Prefer "
        "propose_draft when the CEO still wants to review before it enters the "
        "workflow.",
        {"task": dict},
    )
    async def _create_task(args: dict[str, Any]) -> dict[str, Any]:
        body = args.get("task", args)
        # Mark CEO-originated and human-confirmed so the prompter-origin gate in
        # the route does not reject it (the CEO is the human, acting live).
        if isinstance(body, dict):
            body = {**body, "source": "ceo", "confirmed_by_human": True}
        return await _orchestrator_ceo_write("POST", "/api/tasks", body)

    @tool(
        "update_goals",
        "Apply a Business Goals change DIRECTLY (you act with CEO authority), "
        "landing it in the SAME singleton charter the Panel edits. Use this for a "
        "direction change the CEO has clearly stated and you don't need a "
        "confirm-card round-trip. Pass an 'edit' patch with only the fields that "
        "change: north_star (string), objectives (list), operating_policy "
        "(object), constraints (list of strings). For a heavier or ambiguous edit "
        "the CEO may want to eyeball, use propose_goal_edit instead (it surfaces a "
        "confirmable card). Returns the updated charter.",
        {"edit": dict},
    )
    async def _update_goals(args: dict[str, Any]) -> dict[str, Any]:
        body = args.get("edit", args)
        return await _orchestrator_ceo_write("PUT", "/api/goals", body)

    @tool(
        "message_agent",
        "DM/nudge a single agent on the CEO's behalf (e.g. 'be-dev-1, prioritize "
        "the auth bug' or answer an agent's open question). Pass agent (slug, e.g. "
        "'main-pm', 'be-dev-1') and message (plain language). Gate-checked: if the "
        "message reads like a gated action (spend, go-public, greenlight, cap "
        "breach) it is surfaced to the CEO action queue instead of sent — the "
        "response says whether it was 'executed' or 'gated'.",
        {"agent": str, "message": str},
    )
    async def _message_agent(args: dict[str, Any]) -> dict[str, Any]:
        body = {"agent": args.get("agent", ""), "message": args.get("message", "")}
        return await _orchestrator_ceo_write(
            "POST", "/api/secretary/message-agent", body
        )

    @tool(
        "announce",
        "Post a company-wide announcement as the CEO. Pass channel "
        "('announcements' for a read-only broadcast, or 'all-hands' for open "
        "discussion) and message (plain language). Gate-checked like message_agent: "
        "an announcement that reads like a gated action is surfaced to the CEO "
        "action queue instead of broadcast.",
        {"message": str, "channel": str},
    )
    async def _announce(args: dict[str, Any]) -> dict[str, Any]:
        body = {
            "channel": args.get("channel", "announcements"),
            "message": args.get("message", ""),
        }
        return await _orchestrator_ceo_write("POST", "/api/secretary/announce", body)

    @tool(
        "surface",
        "Surface what needs the CEO right now: human-resolvable blockers (stranded "
        "work) and unacked CEO-targeted signals (pitches, escalations). A focused "
        "slice of the action queue for a quick proactive check-in. Takes no "
        "arguments.",
        {},
    )
    async def _surface(_args: dict[str, Any]) -> dict[str, Any]:
        return await _orchestrator_get("/api/secretary/surface")

    server = create_sdk_mcp_server(
        name="intake",
        version="1.0.0",
        tools=[
            _propose_draft,
            _read_goals,
            _read_status,
            _read_queue,
            _read_task,
            _propose_goal_edit,
            _create_task,
            _update_goals,
            _message_agent,
            _announce,
            _surface,
        ],
    )

    async def _gate(tool_name: str, _input: dict[str, Any], _ctx: Any) -> Any:
        if tool_name in _INTAKE_BASE_TOOLS or _is_secretary_mcp_tool(tool_name):
            return PermissionResultAllow()
        # The intake's job is to ask questions, so it reaches for AskUserQuestion
        # by reflex. It isn't wired to the live chat panel (and isn't allowed), so
        # nudge it to just ask inline rather than leave it to stumble on a bare deny.
        if tool_name == "AskUserQuestion" or tool_name.endswith("AskUserQuestion"):
            return PermissionResultDeny(
                message=(
                    "AskUserQuestion isn't available here — just write your "
                    "questions as a normal chat message; the human reads every "
                    "reply live."
                )
            )
        # Plan mode is a Claude Code workflow the intake keeps slipping into; its
        # "plan" is the propose_draft draft, so steer it straight there.
        if tool_name == "ExitPlanMode" or tool_name.endswith("ExitPlanMode"):
            return PermissionResultDeny(
                message=(
                    "You don't use plan mode. When your spec is ready, call "
                    "propose_draft to produce the reviewable draft card — don't "
                    "announce a plan and wait."
                )
            )
        # Generic deny, but guiding: the agent reflexively probes Claude Code
        # built-ins (Write, ToolSearch, …). Tell it what it actually has.
        return PermissionResultDeny(
            message=(
                f"{tool_name} is not available to the Secretary agent. Your tools "
                "are Read, Grep, Glob, Task; read_goals / read_status / read_queue / "
                "read_task / surface to see the company; create_task / update_goals / "
                "message_agent / announce to act on the CEO's word; propose_draft / "
                "propose_goal_edit to surface a confirmable card. Ask the human "
                "inline by writing a normal chat message."
            )
        )

    return ClaudeAgentOptions(
        system_prompt=system_prompt,
        cwd=cwd,
        mcp_servers={"intake": server},
        allowed_tools=[
            *_INTAKE_BASE_TOOLS,
            *(f"mcp__intake__{t}" for t in _SECRETARY_MCP_TOOLS),
        ],
        model=model,
        include_partial_messages=True,  # live token streaming
        permission_mode="dontAsk",
        strict_mcp_config=True,
        setting_sources=[],
        can_use_tool=_gate,
    )


class SdkIntakeSession:  # pragma: no cover - requires the live claude binary
    """``IntakeSession`` backed by a real ``ClaudeSDKClient``.

    Async context manager: connects the client on enter, disconnects on exit.
    ``send`` runs one turn (query + receive_response) and yields normalized
    chunks. The conversation context lives in the client across turns.
    """

    def __init__(self, options: Any) -> None:
        self._options = options
        self._client: Any = None

    async def __aenter__(self) -> SdkIntakeSession:
        from claude_agent_sdk import ClaudeSDKClient

        self._client = ClaudeSDKClient(options=self._options)
        await self._client.connect()
        return self

    async def __aexit__(self, *exc: object) -> None:
        if self._client is not None:
            await self._client.disconnect()

    async def send(self, text: str) -> AsyncIterator[StreamChunk]:
        await self._client.query(text)
        async for msg in self._client.receive_response():
            for chunk in normalize(msg):
                yield chunk
