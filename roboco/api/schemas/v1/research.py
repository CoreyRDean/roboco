"""Request schemas for /api/v1/research/* external-research endpoints."""

from pydantic import BaseModel, Field


class WebSearchRequest(BaseModel):
    """Cited web search. ``top_k`` is clamped server-side to the cost bound.

    ``top_k`` is permissive here (only the floor is enforced) — the service
    clamps it to ``search_top_k_max`` so an over-eager value degrades to the
    cap rather than 422'ing at the route and tripping the agent's retry loop.
    """

    query: str = Field(..., min_length=1)
    top_k: int = Field(default=5, ge=1)


class WebFetchRequest(BaseModel):
    """Fetch and extract one page's text. Body is byte-capped server-side."""

    url: str = Field(..., min_length=1)
