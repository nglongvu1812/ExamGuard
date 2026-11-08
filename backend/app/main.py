"""FastAPI application factory for ExamGuard Local Server."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.api.assets import router as assets_router
from app.api.auth import router as auth_router
from app.api.exams import router as exams_router
from app.api.health import router as system_router
from app.api.monitoring import router as monitoring_router
from app.api.paper import router as paper_router
from app.api.questions import router as questions_router
from app.api.results import router as results_router
from app.api.rooms import router as rooms_router
from app.api.roster import router as roster_router
from app.api.ws import RoomConnectionManager
from app.api.ws import router as ws_router
from app.core.config import Settings, get_settings
from app.core.logging import configure_logging
from app.db.base import Base
from app.db.models import (  # noqa: F401
    AnswerKeyVersion,
    AnswerRevision,
    Asset,
    Attempt,
    AuditEvent,
    BackupManifest,
    ClassMembership,
    Classroom,
    DeviceBinding,
    Exam,
    ExamPermutation,
    ExamQuestion,
    GradeRun,
    ImportJob,
    Incident,
    OmrScanSubmission,
    PaperVersion,
    PresenceEvent,
    Question,
    QuestionDraft,
    QuestionVersion,
    ReceiptVersion,
    ScoreVersion,
    SourceDocument,
    Student,
    StudentInvite,
    Submission,
    SystemMetadata,
    TeacherProfile,
)
from app.db.session import create_session_factory, create_sqlite_engine
from app.security.auth import SlidingWindowRateLimiter, is_loopback_client, load_or_create_server_secret
from app.services.monitoring_service import evaluate_room_presence, get_room_monitoring_snapshot

logger = logging.getLogger("examguard.app")


def _resolve_static_dir(settings: Settings) -> Path | None:
    if settings.static_dir and settings.static_dir.exists():
        return settings.static_dir
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str):
        frozen_dist = Path(meipass) / "frontend" / "dist"
        if frozen_dist.exists() and (frozen_dist / "index.html").exists():
            return frozen_dist
    candidate = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if candidate.exists() and (candidate / "index.html").exists():
        return candidate
    candidate_alt = Path(__file__).resolve().parents[3] / "frontend" / "dist"
    if candidate_alt.exists() and (candidate_alt / "index.html").exists():
        return candidate_alt
    return None


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_settings.ensure_data_dirs()
        configure_logging(resolved_settings.logs_dir, resolved_settings.log_level)

        engine = create_sqlite_engine(resolved_settings)
        Base.metadata.create_all(bind=engine)
        session_factory = create_session_factory(engine)
        server_secret = load_or_create_server_secret(resolved_settings.data_dir)

        app.state.settings = resolved_settings
        app.state.engine = engine
        app.state.session_factory = session_factory
        app.state.server_secret = server_secret
        app.state.join_rate_limiter = SlidingWindowRateLimiter(max_attempts=10, window_seconds=60)
        app.state.ws_manager = RoomConnectionManager()
        app.state.bound_port = resolved_settings.port

        stop_event = asyncio.Event()

        async def _presence_sweeper() -> None:
            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=2.0)
                    break
                except TimeoutError:
                    pass
                try:
                    with session_factory() as db:
                        running_ids = (
                            db.execute(select(Exam.id).where(Exam.status == "RUNNING"))
                            .scalars()
                            .all()
                        )
                    for ex_id in running_ids:
                        with session_factory() as db:
                            changed = evaluate_room_presence(db, exam_id=ex_id)
                            if changed:
                                snap = get_room_monitoring_snapshot(db, exam_id=ex_id)
                                await app.state.ws_manager.broadcast_teacher_snapshot(ex_id, snap)
                except Exception:
                    logger.exception("Presence sweeper iteration error")

        sweeper_task = asyncio.create_task(_presence_sweeper())
        logger.info("ExamGuard backend started (version=%s)", resolved_settings.app_version)
        try:
            yield
        finally:
            stop_event.set()
            sweeper_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await sweeper_task
            engine.dispose()
            logger.info("ExamGuard backend stopped cleanly")

    app = FastAPI(
        title="ExamGuard Local Server",
        version=resolved_settings.app_version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://localhost:5173",
            "http://127.0.0.1:8000",
            "http://localhost:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(roster_router)
    app.include_router(rooms_router)
    app.include_router(exams_router)
    app.include_router(monitoring_router)
    app.include_router(results_router)
    app.include_router(paper_router)
    app.include_router(questions_router)
    app.include_router(assets_router)
    app.include_router(ws_router)

    static_dir = _resolve_static_dir(resolved_settings)
    if static_dir is not None:
        assets_path = static_dir / "assets"
        if assets_path.exists():
            app.mount("/assets", StaticFiles(directory=assets_path), name="static-assets")

        @app.get("/favicon.ico", include_in_schema=False)
        def get_favicon_ico() -> FileResponse:
            ico_file = static_dir / "favicon.ico"
            if ico_file.is_file():
                return FileResponse(
                    ico_file,
                    media_type="image/x-icon",
                    headers={"Cache-Control": "public, max-age=86400"},
                )
            raise HTTPException(status_code=404, detail="Favicon not found")

        @app.get("/favicon.svg", include_in_schema=False)
        def get_favicon_svg() -> FileResponse:
            svg_file = static_dir / "favicon.svg"
            if svg_file.is_file():
                return FileResponse(
                    svg_file,
                    media_type="image/svg+xml",
                    headers={"Cache-Control": "public, max-age=86400"},
                )
            raise HTTPException(status_code=404, detail="Favicon not found")

        @app.get("/{full_path:path}", include_in_schema=False)
        def serve_spa(request: Request, full_path: str) -> Response:
            if full_path.startswith("api/") or full_path.startswith("ws/"):
                raise HTTPException(status_code=404, detail="Not Found")

            # LAN Isolation: Devices connecting across LAN must never default to Teacher Console
            if not is_loopback_client(request):
                clean_path = full_path.strip("/")
                teacher_paths = {
                    "",
                    "index.html",
                    "classes",
                    "exams",
                    "questions",
                    "results",
                    "settings",
                    "paper",
                    "lan-help",
                    "dashboard",
                    "teacher",
                }
                if clean_path in {"", "index.html"}:
                    return RedirectResponse(url="/join", status_code=307)
                if not resolved_settings.allow_lan_teacher_console and clean_path in teacher_paths:
                    return RedirectResponse(url="/join", status_code=307)

            target = (static_dir / full_path).resolve()
            if full_path and target.is_file() and target.is_relative_to(static_dir.resolve()):
                return FileResponse(target)
            return FileResponse(static_dir / "index.html")

    return app


app = create_app()
