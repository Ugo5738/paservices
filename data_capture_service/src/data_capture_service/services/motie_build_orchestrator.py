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


def _project_name_for(domain: str) -> str:
    """Mirrors the convention used in the V1 fetcher_builds_router."""
    return f"data-capture-{domain}"


async def ensure_project_for_domain(
    db: AsyncSession, domain: str
) -> tuple[MotieScraperProject, bool]:
    """
    Fetch the MotieScraperProject for a domain, creating it on Motie + locally
    if missing. Returns (project, created_new).

    Honours rule 8 (one project per domain) — the unique constraint on
    motie_scraper_projects.domain enforces this at the DB layer; we just
    surface the racy create_new=False path here.
    """
    project = await motie_project_crud.get_by_domain(db, domain)
    if project is not None:
        return project, False

    project_name = _project_name_for(domain)
    create_resp = await motie_client.create_project(
        name=project_name,
        description=f"Property data capture scraper for {domain}",
    )

    try:
        project = await motie_project_crud.create(
            db=db,
            domain=domain,
            motie_project_id=create_resp.id,
            motie_project_name=project_name,
        )
        await db.flush()
        return project, True
    except IntegrityError:
        await db.rollback()
        existing = await motie_project_crud.get_by_domain(db, domain)
        if existing is None:
            raise
        return existing, False


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
