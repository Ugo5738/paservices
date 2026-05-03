"""
Motie build orchestrator — encapsulates the 4-step Motie protocol.

Per Rolf's rule 7 (workflow logic outside the granular service): n8n should
not have to know about Motie's internal state machine
(invoke session → poll session → deploy → poll deployment). That's adapter
implementation detail. WF3 in n8n calls a single status endpoint until the
build is terminal; this orchestrator drives the state advance on each poll.

State machine:
    session_pending → session_running → session_complete
                                        → deploying → deployed   (terminal)
                                        → session_failed         (terminal)
                                        → deployment_failed      (terminal)

`start_build(...)` creates a motie_builds row and kicks off the Motie session.
`advance(...)` is called on each poll: it inspects the row's current state,
queries Motie for the next signal, and advances the row. Idempotent — calling
advance on a terminal row is a no-op.
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from data_capture_service.adapters.motie.motie_client import motie_client
from data_capture_service.crud import (
    motie_build_crud,
    motie_project_crud,
)
from data_capture_service.models.motie_build import (
    MotieBuild,
    MotieBuildPromptKind,
    MotieBuildState,
    TERMINAL_BUILD_STATES,
)
from data_capture_service.models.motie_scraper_project import MotieScraperProject

logger = logging.getLogger(__name__)


class MotieProjectBusy(Exception):
    """
    Raised by ensure_project_for_domain when the active project for a
    domain is busy on Motie's side and spawn_new_on_busy=False.

    The router translates this to HTTP 409. Carries enough detail for
    callers (and the Respond Busy node in WF3) to surface a useful error.
    """

    def __init__(
        self,
        project: "MotieScraperProject",
        agent_status: Optional[str],
        active_session_id: Optional[str],
    ) -> None:
        self.project = project
        self.agent_status = agent_status
        self.active_session_id = active_session_id
        super().__init__(
            f"Motie project {project.motie_project_id} for {project.domain} is "
            f"busy (agent_status={agent_status}, "
            f"active_session={active_session_id})."
        )


def _project_name_for(domain: str, suffix: Optional[str] = None) -> str:
    """
    Generate a human-readable Motie project name for a domain.

    Multiple Motie projects can exist for the same domain over time
    (orchestrator spawns a fresh one when an existing project's session
    is locked); we differentiate them with a UTC-timestamp suffix on the
    second-and-later invocations so the Motie dashboard stays readable.
    """
    base = f"data-capture-{domain}"
    if suffix is None:
        return base
    return f"{base}-{suffix}"


def _timestamp_suffix() -> str:
    """Compact UTC timestamp suitable for project name suffix."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


async def _create_new_project(
    db: AsyncSession, domain: str, *, with_suffix: bool
) -> MotieScraperProject:
    """Create a fresh Motie project on their side and mirror in our DB."""
    project_name = _project_name_for(
        domain, suffix=_timestamp_suffix() if with_suffix else None
    )
    create_resp = await motie_client.create_project(
        name=project_name,
        description=f"Property data capture scraper for {domain}",
    )
    project = await motie_project_crud.create(
        db=db,
        domain=domain,
        motie_project_id=create_resp.id,
        motie_project_name=project_name,
    )
    await db.flush()
    logger.info(
        f"Created new Motie project for {domain}: name={project_name}, "
        f"motie_project_id={create_resp.id}"
    )
    return project


async def ensure_project_for_domain(
    db: AsyncSession,
    domain: str,
    *,
    spawn_new_on_busy: bool = False,
) -> tuple[MotieScraperProject, bool]:
    """
    Return a Motie project we can start a new session on. Returns
    (project, created_new).

    Default (spawn_new_on_busy=False) preserves Rolf's "one project per
    domain" rule:
      1. No active project exists for this domain → create one.
      2. An active project exists and Motie says it's idle → reuse it.
         Building on the same project lets future sessions read prior
         code (the cheapest, highest-quality path).
      3. An active project exists but Motie says it's busy → raise
         MotieProjectBusy. The router translates this to HTTP 409 so
         WF3 (or a manual caller) can back off and retry later.

    Recovery path when a session is genuinely stuck on Motie's side:
    deactivate the affected project via
    POST /fetcher-builds/motie/projects/{uuid}/deactivate. The partial
    unique index permits creating a fresh active project for the domain
    immediately afterwards.

    spawn_new_on_busy=True (testing-only opt-in) skips the 409 path and
    creates a brand-new Motie project even when one is already busy.
    Production callers should leave the default; this keeps the schema
    "one active project per domain" invariant (enforced by the partial
    unique index) intact.
    """
    project = await motie_project_crud.get_by_domain(db, domain)

    if project is None:
        new_proj = await _create_new_project(db, domain, with_suffix=False)
        return new_proj, True

    busy, agent_status, active_session_id = await project_is_busy(project)
    if not busy:
        return project, False

    if not spawn_new_on_busy:
        raise MotieProjectBusy(project, agent_status, active_session_id)

    logger.info(
        f"Motie project {project.motie_project_id} for {domain} is busy "
        f"(agent_status={agent_status}, session={active_session_id}); "
        "spawn_new_on_busy=True → creating a fresh project for this build "
        "(testing path only)."
    )
    # Deactivate the busy project so the partial-unique index permits the
    # new row, and so the fetcher-registry replacement points at the new
    # project rather than the stuck one.
    await motie_project_crud.deactivate(db, project.id)
    new_proj = await _create_new_project(db, domain, with_suffix=True)
    return new_proj, True


async def project_is_busy(
    project: MotieScraperProject,
) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Live check: is Motie's project currently locked by an active session?

    Returns (busy, agent_status, active_session_id). On error, conservatively
    returns busy=False and lets the caller proceed.
    """
    try:
        live = await motie_client.get_project(project.motie_project_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            f"motie_build_orchestrator: project_is_busy probe failed for "
            f"{project.motie_project_id}: {exc}"
        )
        return False, None, None
    busy = bool(live.agent_status) and live.agent_status != "idle"
    return busy, live.agent_status, live.active_session_id


async def start_build(
    db: AsyncSession,
    *,
    project: MotieScraperProject,
    domain: str,
    url: str,
    prompt: str,
    prompt_kind: str = MotieBuildPromptKind.BUILD.value,
    parent_build_id: Optional[UUID] = None,
    metadata_json: Optional[Dict[str, Any]] = None,
) -> MotieBuild:
    """
    Create a motie_builds row and invoke the Motie agent session.

    The caller is responsible for:
    - having prepared `prompt` (use motie_prompts.build_initial_prompt /
      build_repair_prompt — vendor-agnostic prompt-building lives there).
    - having checked rule 8 (one session per project) via project_is_busy.

    Returns the new MotieBuild row in state=session_running.
    """
    attempt_number = (
        await motie_build_crud.latest_attempt_number(db, project.id) + 1
    )

    invoke = await motie_client.invoke(
        project_id=project.motie_project_id, prompt=prompt
    )

    build = await motie_build_crud.create(
        db,
        project_uuid=project.id,
        domain=domain,
        url=url,
        prompt_kind=prompt_kind,
        session_id=invoke.session_id,
        state=MotieBuildState.SESSION_RUNNING.value,
        attempt_number=attempt_number,
        parent_build_id=parent_build_id,
        metadata_json=metadata_json,
    )

    # Mirror the session id on the project so existing dashboards/queries that
    # read motie_scraper_projects.last_session_id keep working.
    await motie_project_crud.update_deployment(
        db=db, project_id=project.id, last_session_id=invoke.session_id
    )

    return build


async def advance(db: AsyncSession, build: MotieBuild) -> MotieBuild:
    """
    Poll Motie + advance the state machine by one step. Idempotent.

    Calling advance on a terminal row returns immediately.
    """
    if build.is_terminal():
        return build

    if build.state == MotieBuildState.SESSION_RUNNING.value:
        if not build.session_id:
            await motie_build_crud.update_state(
                db,
                build.id,
                state=MotieBuildState.SESSION_FAILED.value,
                error_message="Build started without a Motie session_id",
            )
            return await motie_build_crud.get_by_id(db, build.id)

        try:
            session = await motie_client.get_session(build.session_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"motie_build_orchestrator: get_session({build.session_id}) failed: {exc}"
            )
            return build  # transient — leave state, let caller poll again

        s_status = (session.status or "").lower()
        if s_status == "completed":
            # Kick off deploy immediately.
            try:
                deploy = await motie_client.deploy(
                    await _resolve_motie_project_id(db, build)
                )
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"motie_build_orchestrator: deploy() failed for build "
                    f"{build.id}: {exc}"
                )
                await motie_build_crud.update_state(
                    db,
                    build.id,
                    state=MotieBuildState.DEPLOYMENT_FAILED.value,
                    error_message=f"deploy invocation failed: {exc}",
                )
                return await motie_build_crud.get_by_id(db, build.id)

            await motie_build_crud.update_state(
                db,
                build.id,
                state=MotieBuildState.DEPLOYING.value,
                deployment_id=deploy.deployment_id,
                api_url=deploy.api_url,
            )
            await motie_project_crud.update_deployment(
                db=db,
                project_id=build.project_uuid,
                deployment_id=deploy.deployment_id,
                deployment_status=deploy.status or "pending",
            )
            return await motie_build_crud.get_by_id(db, build.id)

        if s_status == "failed":
            await motie_build_crud.update_state(
                db,
                build.id,
                state=MotieBuildState.SESSION_FAILED.value,
                error_message=session.error or "Motie session reported failed",
            )
            return await motie_build_crud.get_by_id(db, build.id)

        # Still running — leave state alone.
        return build

    if build.state == MotieBuildState.DEPLOYING.value:
        if not build.deployment_id:
            await motie_build_crud.update_state(
                db,
                build.id,
                state=MotieBuildState.DEPLOYMENT_FAILED.value,
                error_message="In deploying state without deployment_id",
            )
            return await motie_build_crud.get_by_id(db, build.id)

        try:
            deploy = await motie_client.get_deployment(build.deployment_id)
        except Exception as exc:  # noqa: BLE001
            logger.error(
                f"motie_build_orchestrator: get_deployment({build.deployment_id}) "
                f"failed: {exc}"
            )
            return build  # transient

        d_status = (deploy.status or "").lower()
        if d_status == "deployed" and deploy.api_url:
            await motie_build_crud.update_state(
                db,
                build.id,
                state=MotieBuildState.DEPLOYED.value,
                api_url=deploy.api_url,
            )
            await motie_project_crud.update_deployment(
                db=db,
                project_id=build.project_uuid,
                api_url=deploy.api_url,
                deployment_id=build.deployment_id,
                deployment_status="deployed",
            )
            return await motie_build_crud.get_by_id(db, build.id)
        if d_status == "failed":
            await motie_build_crud.update_state(
                db,
                build.id,
                state=MotieBuildState.DEPLOYMENT_FAILED.value,
                error_message=deploy.error or "Motie deployment reported failed",
            )
            await motie_project_crud.update_deployment(
                db=db,
                project_id=build.project_uuid,
                deployment_id=build.deployment_id,
                deployment_status="failed",
            )
            return await motie_build_crud.get_by_id(db, build.id)

        # Still deploying — leave state alone.
        return build

    # session_pending or session_complete: not currently in the state machine
    # paths above. Leaving them as no-ops keeps advance() idempotent in the
    # face of upstream additions.
    return build


async def _resolve_motie_project_id(db: AsyncSession, build: MotieBuild) -> str:
    """Look up the Motie-side project id for a build's project_uuid."""
    project = await db.get(MotieScraperProject, build.project_uuid)
    if project is None:
        raise RuntimeError(
            f"motie_builds row {build.id} references missing project {build.project_uuid}"
        )
    return project.motie_project_id
