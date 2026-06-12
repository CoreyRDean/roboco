"""GitHub provisioning service (Phase 4 — Pitch → Approve → Provision).

There is no repo *creation* anywhere else in the codebase — `services/git.py`
only clones/branches/PRs/merges against repos that already exist. This service
adds the one missing capability: creating a brand-new **private** repository in
the dedicated provisioning org (INTENT.md §7), so an approved pitch can be
stood up automatically.

The GitHub HTTP call mirrors the existing REST usage in `GitService` (httpx
`AsyncClient`, `Authorization: Bearer …`, the `Accept` +
`X-GitHub-Api-Version` headers, and HTTP failures translated to `GitError`).
The difference is the auth scope: a freshly-created repo has no project row
yet, so there is no per-project PAT — provisioning uses the org-scoped
operator token from config.

CRITICAL GUARD: when no org is configured (neither the Business Goals charter
nor config supplies one), this service does **not** attempt creation. It
returns a clear ``available=False`` result so the caller can surface
"provisioning unavailable" to the CEO instead of failing hard mid-approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar

import httpx

from roboco.config import settings
from roboco.exceptions import GitError
from roboco.services.base import BaseService

# GitHub returns 201 on a successful repo create; 422 when the repo already
# exists under the org (the idempotent re-provision case). We treat an existing
# repo of the same name as success so a retried provisioning run is a no-op
# rather than a hard failure.
_GH_CREATED = 201
_GH_UNPROCESSABLE = 422


@dataclass(frozen=True)
class RepoProvisionResult:
    """Outcome of a repo-provisioning attempt.

    ``available`` is the guard signal: when False, no creation was attempted
    (no org configured) and ``reason`` explains why, for the CEO-facing
    surface. When True, ``clone_url`` / ``html_url`` / ``full_name`` describe
    the live private repo (``already_existed`` distinguishes a fresh create
    from an idempotent hit on a repo that was already there).
    """

    available: bool
    reason: str | None = None
    name: str | None = None
    full_name: str | None = None
    clone_url: str | None = None
    html_url: str | None = None
    default_branch: str | None = None
    already_existed: bool = False


class GitHubProvisioningService(BaseService):
    """Creates private GitHub repositories for approved pitches."""

    service_name: ClassVar[str] = "github_provisioning"

    def _resolve_org(self, org: str | None) -> str | None:
        """Pick the org to provision into.

        Priority: explicit caller arg (resolved by the caller from the
        Business Goals charter) → ``settings.github_provisioning_org``
        fallback. Returns None when neither yields a non-empty org — the
        guard the caller checks before surfacing "provisioning unavailable".
        """
        if org and org.strip():
            return org.strip()
        configured = settings.github_provisioning_org.strip()
        return configured or None

    def _provisioning_token(self) -> str | None:
        """The org-scoped PAT used to create repos, or None if unset."""
        token = settings.github_provisioning_token.strip()
        return token or None

    async def _post_create_repo(
        self,
        org: str,
        token: str,
        payload: dict[str, Any],
    ) -> httpx.Response:
        """POST /orgs/{org}/repos; translate HTTP errors to GitError.

        Mirrors `GitService._post_pr` — same client construction, headers, and
        error-to-GitError mapping, so provisioning behaves like the rest of the
        GitHub REST surface.
        """
        try:
            async with httpx.AsyncClient(
                timeout=settings.git_command_timeout_seconds
            ) as client:
                return await client.post(
                    f"https://api.github.com/orgs/{org}/repos",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json=payload,
                )
        except httpx.HTTPError as e:
            name = payload.get("name")
            raise GitError(
                f"GitHub API error while creating repository '{org}/{name}': {e}",
                {"org": org, "name": name},
            ) from e

    async def _get_existing_repo(
        self, org: str, name: str, token: str
    ) -> dict[str, Any] | None:
        """Fetch an existing repo's metadata (idempotent re-provision path)."""
        try:
            async with httpx.AsyncClient(
                timeout=settings.git_command_timeout_seconds
            ) as client:
                resp = await client.get(
                    f"https://api.github.com/repos/{org}/{name}",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                )
        except httpx.HTTPError:
            return None
        if not resp.is_success:
            return None
        return resp.json()  # type: ignore[no-any-return]

    async def create_repository(
        self,
        name: str,
        description: str | None = None,
        private: bool = True,
        org: str | None = None,
    ) -> RepoProvisionResult:
        """Create a private repository in the provisioning org.

        ``private`` defaults to True (INTENT.md §7 — new repos are created
        private; going public is a separate, explicitly gated step). The org
        is the caller-supplied value (from the Business Goals charter) with a
        config fallback.

        Returns a :class:`RepoProvisionResult`. When no org is configured the
        result is ``available=False`` with a reason — creation is NOT attempted,
        so the approval flow can surface the gap to the CEO instead of erroring.
        An existing repo of the same name is treated as success
        (``already_existed=True``) so re-provisioning is idempotent.
        """
        resolved_org = self._resolve_org(org)
        if resolved_org is None:
            return RepoProvisionResult(
                available=False,
                reason=(
                    "provisioning unavailable: no github_org configured. Set "
                    "operating_policy.provisioning.github_org in Business Goals "
                    "(or ROBOCO_GITHUB_PROVISIONING_ORG) before approving a pitch."
                ),
                name=name,
            )

        token = self._provisioning_token()
        if token is None:
            return RepoProvisionResult(
                available=False,
                reason=(
                    "provisioning unavailable: no provisioning token configured. "
                    "Set ROBOCO_GITHUB_PROVISIONING_TOKEN (an org-scoped GitHub "
                    "PAT) before approving a pitch."
                ),
                name=name,
            )

        payload: dict[str, Any] = {
            "name": name,
            "private": private,
            # Seed with a README so the default branch exists immediately and
            # the delivery engine can cut branches off it without an empty-repo
            # special case.
            "auto_init": True,
        }
        if description:
            payload["description"] = description

        resp = await self._post_create_repo(resolved_org, token, payload)

        # Idempotency: a prior provisioning run already created this repo. 422
        # "name already exists" → look it up and return it as success rather
        # than failing the approval on a retry.
        if resp.status_code == _GH_UNPROCESSABLE and "already exists" in resp.text:
            existing = await self._get_existing_repo(resolved_org, name, token)
            if existing is not None:
                self.log.info(
                    "Repository already existed; provisioning is idempotent",
                    org=resolved_org,
                    name=name,
                )
                return self._result_from_repo(existing, already_existed=True)

        if resp.status_code != _GH_CREATED and not resp.is_success:
            raise GitError(
                f"GitHub API refused repository creation ({resp.status_code}): "
                f"{resp.text[:200]}",
                {"org": resolved_org, "name": name},
            )

        self.log.info(
            "Private repository provisioned",
            org=resolved_org,
            name=name,
            private=private,
        )
        return self._result_from_repo(resp.json(), already_existed=False)

    @staticmethod
    def _result_from_repo(
        repo: dict[str, Any], *, already_existed: bool
    ) -> RepoProvisionResult:
        """Build a result from a GitHub repo object (create or lookup)."""
        return RepoProvisionResult(
            available=True,
            name=str(repo.get("name", "")),
            full_name=str(repo.get("full_name", "")),
            clone_url=str(repo.get("clone_url", "")),
            html_url=str(repo.get("html_url", "")),
            default_branch=str(repo.get("default_branch") or "main"),
            already_existed=already_existed,
        )


def get_github_provisioning_service(session: Any) -> GitHubProvisioningService:
    """Get a GitHubProvisioningService instance."""
    return GitHubProvisioningService(session)
