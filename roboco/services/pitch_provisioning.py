"""Provision an approved pitch into real, working state (Phase 4 — 4.A2).

Given an *already-approved* pitch task, this service stands up the reality the
pitch described, autonomously (the CEO already said yes — INTENT.md §6 puts
*executing* an approved product inside the autonomy line):

1. create the private repo(s) via :mod:`roboco.services.github_provisioning`
   (one per participating cell for a multi-cell product, else a single repo);
2. register each repo as a :class:`ProjectTable`
   (``ProjectService.create``);
3. for a multi-cell product, register a :class:`ProductTable` mapping each
   cell → its Project (``ProductService.create``);
4. seed the initial delivery task(s) (``TaskService.create``) and hand back to
   the existing delivery engine.

It is **idempotent and guarded**: re-running on an already-provisioned pitch is
a no-op that returns the existing registration, and if no provisioning org is
configured the run aborts cleanly with a CEO-surfaceable reason rather than
half-creating state or failing hard.

The pitch's structured content (product name, participating cells, repo naming)
is read tolerantly from the task's ``plan`` JSON — the pitch-authoring sub-track
(Track D) writes it there. When a field is absent the value is derived from the
task itself, so provisioning still works against a minimally-formed pitch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar
from uuid import UUID

from roboco.foundation.identity import CELL_TEAMS, Team
from roboco.models.base import Complexity, TaskNature, TaskType
from roboco.models.business_goals import OperatingPolicy
from roboco.models.product import ProductCellMapping, ProductCreate
from roboco.models.project import ProjectCreate
from roboco.models.task import TaskCreateRequest
from roboco.services.base import BaseService
from roboco.services.business_goals import get_business_goals_service
from roboco.services.github_provisioning import (
    RepoProvisionResult,
    get_github_provisioning_service,
)
from roboco.services.product import get_product_service
from roboco.services.project import get_project_service
from roboco.services.task import get_task_service

if TYPE_CHECKING:
    from roboco.db.tables import TaskTable

# Cell → the default branch GitHub seeds an auto-init repo with. The provisioned
# repos are created with auto_init=True, which gives them a "main" default
# branch; the Project records that so branch-cutting targets the right base.
_DEFAULT_BRANCH = "main"

# Max length of a project/product slug (mirrors the Pydantic constraint on
# ProjectCreate.slug / ProductCreate.slug — keep the generated slug inside it).
_MAX_SLUG_LEN = 50


@dataclass
class ProvisionedRepo:
    """One repo that was (or already was) stood up for the pitch."""

    team: Team | None
    project_id: UUID
    slug: str
    html_url: str | None
    already_existed: bool


@dataclass
class PitchProvisionResult:
    """Outcome of provisioning an approved pitch.

    ``provisioned`` is False only when nothing was stood up: either the guard
    tripped (no org configured → ``reason`` set, ``available=False``) or the
    pitch was already provisioned (``skipped=True``). On success it carries the
    repos, the product (multi-cell), and the seeded delivery task ids.
    """

    provisioned: bool
    available: bool = True
    skipped: bool = False
    reason: str | None = None
    product_id: UUID | None = None
    repos: list[ProvisionedRepo] = field(default_factory=list)
    seeded_task_ids: list[UUID] = field(default_factory=list)


def _slugify(text: str, *, fallback: str = "product") -> str:
    """Lowercase, hyphenate, strip to the project/product slug charset.

    Matches the ``^[a-z0-9-]+$`` pattern ProjectCreate/ProductCreate enforce.
    Empty or all-symbol input falls back to a safe default so a thin pitch
    title can never produce an invalid (and thus un-registerable) slug.
    """
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        slug = fallback
    return slug[:_MAX_SLUG_LEN].strip("-") or fallback


class PitchProvisioningService(BaseService):
    """Stand up the repos/project/product/work for an approved pitch."""

    service_name: ClassVar[str] = "pitch_provisioning"

    # Where the idempotency marker lives on the task's plan JSON: once a pitch
    # is provisioned we stamp the resulting product/project ids here so a second
    # approval (or a retried approval hook) skips instead of double-creating.
    _PLAN_PROVISIONING_KEY: ClassVar[str] = "provisioning"

    async def provision_pitch(
        self,
        task_id: UUID,
        created_by: UUID,
    ) -> PitchProvisionResult:
        """Provision the approved pitch identified by ``task_id``.

        ``created_by`` is the agent the new Project/Product/Task rows are
        attributed to (the approving/Board identity). Returns a structured
        result; raises only on a genuine GitHub/DB failure (the guard and the
        already-provisioned cases are returned, not raised, so the approval
        flow can surface them without treating them as errors).
        """
        task = await get_task_service(self.session).get(task_id)
        if task is None:
            return PitchProvisionResult(
                provisioned=False,
                available=False,
                reason=f"pitch task not found: {task_id}",
            )

        # Idempotency guard: a prior run stamped the plan. Skip cleanly.
        existing_marker = self._existing_marker(task)
        if existing_marker is not None:
            return PitchProvisionResult(
                provisioned=False,
                skipped=True,
                reason="pitch already provisioned",
                product_id=existing_marker,
            )

        org = await self._resolve_org()
        cells = self._pitch_cells(task)
        product_slug = self._product_slug(task)

        # Idempotency guard #2: the registration already exists (the plan marker
        # was lost but the product/projects are present). Skip on slug hit.
        prior = await self._already_registered(product_slug, cells, task)
        if prior is not None:
            return prior

        repo_specs = self._repo_specs(task, cells, product_slug)

        provisioned_repos: list[ProvisionedRepo] = []
        provisioning = get_github_provisioning_service(self.session)
        for spec in repo_specs:
            repo = await provisioning.create_repository(
                name=spec.repo_name,
                description=spec.description,
                private=True,
                org=org,
            )
            if not repo.available:
                # Guard tripped (no org/token). Abort cleanly — surface to the
                # CEO rather than leaving a half-provisioned product.
                return PitchProvisionResult(
                    provisioned=False,
                    available=False,
                    reason=repo.reason,
                )
            project = await self._register_project(spec, repo, created_by)
            provisioned_repos.append(
                ProvisionedRepo(
                    team=spec.team,
                    project_id=UUID(str(project.id)),
                    slug=spec.project_slug,
                    html_url=repo.html_url,
                    already_existed=repo.already_existed,
                )
            )

        product_id = await self._register_product_if_multi_cell(
            task, product_slug, provisioned_repos, created_by
        )

        seeded = await self._seed_delivery(
            task, product_id, provisioned_repos, created_by
        )

        await self._stamp_marker(task, product_id, provisioned_repos)
        await self.session.flush()

        self.log.info(
            "Pitch provisioned",
            task_id=str(task_id),
            repos=len(provisioned_repos),
            product_id=str(product_id) if product_id else None,
            seeded=len(seeded),
        )
        return PitchProvisionResult(
            provisioned=True,
            product_id=product_id,
            repos=provisioned_repos,
            seeded_task_ids=seeded,
        )

    # =========================================================================
    # PITCH READING (tolerant of the not-yet-merged Track D content contract)
    # =========================================================================

    @dataclass
    class _RepoSpec:
        """One repo to create + the Project to register it as."""

        team: Team | None
        repo_name: str
        project_slug: str
        project_name: str
        assigned_cell: Team
        description: str | None

    def _plan(self, task: TaskTable) -> dict[str, Any]:
        """The task's plan JSON as a dict (empty when unset/non-dict)."""
        return task.plan if isinstance(task.plan, dict) else {}

    def _pitch_meta(self, task: TaskTable) -> dict[str, Any]:
        """The pitch's structured content block, if the author wrote one.

        Track D's ``TaskService.create_pitch`` persists the structured content
        contract under ``proactive_context['pitch']`` (objective / the_work /
        cells / name / slug …). Read it from there first; fall back to the plan
        (``plan['pitch']`` or the plan root) so an older/thin pitch that stashed
        its content on the plan still reads. The provisioning *marker* is a
        separate, provisioning-owned namespace and stays on the plan.
        """
        ctx = task.proactive_context if isinstance(task.proactive_context, dict) else {}
        meta = ctx.get("pitch")
        if isinstance(meta, dict):
            return meta
        plan = self._plan(task)
        plan_meta = plan.get("pitch")
        if isinstance(plan_meta, dict):
            return plan_meta
        return plan

    def _pitch_cells(self, task: TaskTable) -> list[Team]:
        """Participating cells for the pitch (empty → single-repo product).

        Reads a ``cells`` list from the pitch meta (cell slugs/names), keeping
        only real cell teams and de-duplicating while preserving order. An
        unparseable or absent value yields an empty list — a single-repo
        product keyed on the task's own team.

        Falls back to the per-cell ``the_work`` slices (the field Track D's
        pitch verb actually writes — each slice is ``{team, summary, items}``)
        when no explicit ``cells`` list is present, so a multi-cell pitch fans
        out to one repo per participating cell.
        """
        meta = self._pitch_meta(task)
        raw = meta.get("cells")
        if not isinstance(raw, list):
            raw = meta.get("the_work")
        if not isinstance(raw, list):
            return []
        out: list[Team] = []
        for item in raw:
            team = self._coerce_cell(item)
            if team is not None and team not in out:
                out.append(team)
        return out

    @staticmethod
    def _coerce_cell(value: Any) -> Team | None:
        """Coerce a cell name/slug/object into a cell Team, else None."""
        candidate: Any = value
        if isinstance(value, dict):
            candidate = value.get("team") or value.get("cell") or value.get("name")
        if candidate is None:
            return None
        try:
            team = Team(str(candidate).strip().lower())
        except ValueError:
            return None
        return team if team in CELL_TEAMS else None

    def _product_slug(self, task: TaskTable) -> str:
        """Deterministic product slug for the pitch (the idempotency key).

        Prefers an explicit ``slug``/``name`` from the pitch meta, else the
        task title. Deterministic so a retried provisioning resolves the same
        slug and the duplicate-slug guard fires.
        """
        meta = self._pitch_meta(task)
        explicit = meta.get("slug") or meta.get("name") or meta.get("product")
        base = str(explicit) if explicit else str(task.title)
        return _slugify(base, fallback="product")

    def _product_name(self, task: TaskTable) -> str:
        """Human-facing product name (pitch name → task title)."""
        meta = self._pitch_meta(task)
        name = meta.get("name") or meta.get("product")
        return str(name) if name else str(task.title)

    def _repo_specs(
        self, task: TaskTable, cells: list[Team], product_slug: str
    ) -> list[_RepoSpec]:
        """Build the per-repo spec list.

        Multi-cell: one repo per cell, named ``{product_slug}-{cell}``, each a
        Project assigned to that cell. Single-cell (or no cells named): one repo
        named ``{product_slug}``, assigned to the task's own team if it is a
        cell, else Backend as the default delivery cell.
        """
        description = self._product_name(task)
        if cells:
            return [
                self._RepoSpec(
                    team=cell,
                    repo_name=f"{product_slug}-{cell.value}",
                    project_slug=_slugify(
                        f"{product_slug}-{cell.value}", fallback=product_slug
                    ),
                    project_name=f"{self._product_name(task)} ({cell.value})",
                    assigned_cell=cell,
                    description=f"{description} — {cell.value} repo",
                )
                for cell in cells
            ]
        default_cell = self._default_single_cell(task)
        return [
            self._RepoSpec(
                team=None,
                repo_name=product_slug,
                project_slug=product_slug,
                project_name=self._product_name(task),
                assigned_cell=default_cell,
                description=description,
            )
        ]

    @staticmethod
    def _default_single_cell(task: TaskTable) -> Team:
        """Cell to own a single-repo product: the task's team if a cell, else
        Backend (the default delivery cell for an unspecified product)."""
        team = task.team
        if isinstance(team, Team) and team in CELL_TEAMS:
            return team
        try:
            coerced = Team(str(team))
        except ValueError:
            return Team.BACKEND
        return coerced if coerced in CELL_TEAMS else Team.BACKEND

    # =========================================================================
    # ORG RESOLUTION
    # =========================================================================

    async def _resolve_org(self) -> str | None:
        """Org from the Business Goals charter (config fallback handled by the
        provisioning service). Returns None when the charter leaves it unset.
        """
        goals = await get_business_goals_service(self.session).get_or_initialize()
        policy = OperatingPolicy.model_validate(goals.operating_policy)
        org = policy.provisioning.github_org
        return org.strip() if org and org.strip() else None

    # =========================================================================
    # REGISTRATION
    # =========================================================================

    async def _register_project(
        self,
        spec: _RepoSpec,
        repo: RepoProvisionResult,
        created_by: UUID,
    ) -> Any:
        """Register (or fetch existing) a Project for a provisioned repo.

        Idempotent on slug: if a Project with this slug already exists (a prior
        provisioning run), return it rather than conflicting.
        """
        project_service = get_project_service(self.session)
        existing = await project_service.get_by_slug(spec.project_slug)
        if existing is not None:
            return existing
        return await project_service.create(
            ProjectCreate(
                name=spec.project_name,
                slug=spec.project_slug,
                git_url=repo.clone_url or "",
                default_branch=repo.default_branch or _DEFAULT_BRANCH,
                assigned_cell=spec.assigned_cell,
            ),
            created_by=created_by,
        )

    async def _register_product_if_multi_cell(
        self,
        task: TaskTable,
        product_slug: str,
        repos: list[ProvisionedRepo],
        created_by: UUID,
    ) -> UUID | None:
        """Register a Product mapping cells→projects for a multi-cell pitch.

        Single-repo pitches need no Product (the lone Project is targeted
        directly). Idempotent on slug.
        """
        cell_repos = [r for r in repos if r.team is not None]
        if len(cell_repos) < 2:  # noqa: PLR2004 — multi-cell means >= 2 cells
            return None

        product_service = get_product_service(self.session)
        existing = await product_service.get_by_slug(product_slug)
        if existing is not None:
            return UUID(str(existing.id))

        product = await product_service.create(
            ProductCreate(
                name=self._product_name(task),
                slug=product_slug,
                description=str(task.description) if task.description else None,
                cells=[
                    ProductCellMapping(team=r.team, project_id=r.project_id)
                    for r in cell_repos
                    if r.team is not None
                ],
            ),
            created_by=created_by,
        )
        return UUID(str(product.id))

    # =========================================================================
    # DELIVERY SEEDING
    # =========================================================================

    async def _seed_delivery(
        self,
        task: TaskTable,
        product_id: UUID | None,
        repos: list[ProvisionedRepo],
        created_by: UUID,
    ) -> list[UUID]:
        """Seed the initial delivery task and hand to the delivery engine.

        One root delivery task: targets the Product (multi-cell, so Main PM
        fans it out across cells) or the single Project. Title/description/
        acceptance criteria carry the pitch's intent so the cells start with
        context rather than an empty repo.
        """
        if not repos:
            return []
        task_service = get_task_service(self.session)
        single_project_id = repos[0].project_id if product_id is None else None
        # Multi-cell fan-out (product_id set) belongs to Main PM, who delegates
        # to each cell; a single-repo product is owned by that repo's own cell.
        if product_id is not None:
            seed_team: Team = Team.MAIN_PM
        else:
            seed_team = repos[0].team if repos[0].team is not None else Team.BACKEND
        delivery = await task_service.create(
            TaskCreateRequest(
                title=f"Build: {self._product_name(task)}",
                description=self._seed_description(task),
                acceptance_criteria=self._seed_acceptance(task),
                team=seed_team,
                created_by=created_by,
                task_type=TaskType.CODE,
                nature=TaskNature.TECHNICAL,
                estimated_complexity=Complexity.HIGH,
                project_id=single_project_id,
                product_id=product_id,
                source="pitch",
            )
        )
        return [UUID(str(delivery.id))]

    def _seed_description(self, task: TaskTable) -> str:
        """Seed-task description: the pitch's own description, or a stub that
        points back at the pitch so the cells can read the rationale."""
        if task.description:
            return str(task.description)
        return f"Initial delivery for the approved pitch '{self._product_name(task)}'."

    def _seed_acceptance(self, task: TaskTable) -> list[str]:
        """Seed-task acceptance criteria: the pitch's own criteria, or a single
        baseline so the task is well-formed (no criteria-less task)."""
        criteria = list(task.acceptance_criteria) if task.acceptance_criteria else []
        if criteria:
            return criteria
        return [
            "Stand up the project skeleton and a first working slice of the "
            "approved pitch.",
        ]

    # =========================================================================
    # IDEMPOTENCY MARKER
    # =========================================================================

    def _existing_marker(self, task: TaskTable) -> UUID | None:
        """Return the marker's product_id (or a sentinel) if already stamped.

        A stamped plan means provisioning ran. We return the product_id when
        present; for single-repo pitches (no product) we return the first
        project_id so the skip path still carries a real id.
        """
        plan = self._plan(task)
        marker = plan.get(self._PLAN_PROVISIONING_KEY)
        if not isinstance(marker, dict):
            return None
        for key in ("product_id", "project_id"):
            value = marker.get(key)
            if value:
                try:
                    return UUID(str(value))
                except ValueError:
                    continue
        # Stamped but id-less (shouldn't happen) — still treat as provisioned.
        return UUID(int=0)

    async def _already_registered(
        self,
        product_slug: str,
        cells: list[Team],
        task: TaskTable,
    ) -> PitchProvisionResult | None:
        """Detect a prior provisioning whose plan marker was lost.

        Resolves the deterministic slug(s) the run would create and, if they
        already exist, returns a skip result rather than re-creating. Covers a
        retried approval where the marker write didn't persist.
        """
        repo_specs = self._repo_specs(task, cells, product_slug)
        project_service = get_project_service(self.session)
        product_service = get_product_service(self.session)

        existing_projects = [
            await project_service.get_by_slug(spec.project_slug) for spec in repo_specs
        ]
        if not all(existing_projects):
            return None

        product = await product_service.get_by_slug(product_slug)
        return PitchProvisionResult(
            provisioned=False,
            skipped=True,
            reason="pitch already provisioned (registration present)",
            product_id=UUID(str(product.id)) if product is not None else None,
            repos=[
                ProvisionedRepo(
                    team=spec.team,
                    project_id=UUID(str(proj.id)),
                    slug=spec.project_slug,
                    html_url=None,
                    already_existed=True,
                )
                for spec, proj in zip(repo_specs, existing_projects, strict=True)
                if proj is not None
            ],
        )

    async def _stamp_marker(
        self,
        task: TaskTable,
        product_id: UUID | None,
        repos: list[ProvisionedRepo],
    ) -> None:
        """Stamp the provisioning marker onto the task's plan (idempotency).

        Merges into the existing plan dict so the pitch content the author
        wrote is preserved.
        """
        plan = dict(self._plan(task))
        plan[self._PLAN_PROVISIONING_KEY] = {
            "product_id": str(product_id) if product_id else None,
            "project_id": str(repos[0].project_id) if repos else None,
            "project_ids": [str(r.project_id) for r in repos],
            "repos": [
                {
                    "team": r.team.value if r.team else None,
                    "slug": r.slug,
                    "html_url": r.html_url,
                }
                for r in repos
            ],
        }
        task.plan = plan


def get_pitch_provisioning_service(session: Any) -> PitchProvisioningService:
    """Get a PitchProvisioningService instance."""
    return PitchProvisioningService(session)
