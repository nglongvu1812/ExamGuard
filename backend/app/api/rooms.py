"""Waiting room, student join, approval, device rebind, and isolated student status endpoints."""

from __future__ import annotations

from app.api.deps import get_db
from app.db.models import (
    AnswerRevision,
    Attempt,
    DeviceBinding,
    Exam,
    ExamQuestion,
    Incident,
    Student,
)
from app.security.auth import (
    StudentPrincipal,
    TeacherPrincipal,
    require_student,
    require_teacher,
)
from app.services.exam_service import compute_remaining_seconds
from app.services.monitoring_service import evaluate_room_presence, get_room_monitoring_snapshot
from app.services.room_service import (
    approve_all_pending,
    approve_attempt,
    create_waiting_room_session,
    join_exam_room,
    reset_attempt_device,
)
from app.services.roster_service import list_classroom_students
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

router = APIRouter(prefix="/api/v1", tags=["rooms"])


class CreateRoomRequest(BaseModel):
    classroom_id: str
    title: str = Field(min_length=1, max_length=200)
    duration_s: int = Field(default=2700, ge=60, le=14400)
    invite_ttl_minutes: int = Field(default=120, ge=5, le=1440)


class IssuedInviteResponse(BaseModel):
    student_id: str
    roster_code: str
    full_name: str
    invite_code: str
    expires_at: str


class RoomSummaryDTO(BaseModel):
    exam_id: str
    classroom_id: str
    room_code: str
    title: str
    duration_s: int
    status: str
    remaining_s: int = 0
    is_paused: bool = False
    question_count: int = 0


class CreateRoomResponse(BaseModel):
    room: RoomSummaryDTO
    invites: list[IssuedInviteResponse]


class RoomRosterEntryDTO(BaseModel):
    student_id: str
    roster_code: str
    full_name: str
    attempt_id: str | None
    attempt_state: str  # NOT_JOINED | PENDING_APPROVAL | READY | ACTIVE | SUBMITTED | LOCKED
    presence_state: str = "OFFLINE"
    device_bound: bool
    latest_revision: int = 0
    answered_count: int = 0
    reconnect_count: int = 0
    hidden_event_count: int = 0
    extra_time_s: int = 0
    open_incident_id: str | None = None
    submitted_at: str | None = None


class JoinRoomRequest(BaseModel):
    roster_code: str = Field(min_length=1, max_length=64)
    invite_code: str = Field(min_length=4, max_length=32)
    browser_key: str = Field(min_length=8, max_length=128)


class AttemptStatusResponse(BaseModel):
    attempt_id: str
    exam_id: str
    room_code: str
    exam_title: str
    exam_status: str
    student_id: str
    student_name: str
    roster_code: str
    state: str
    presence_state: str = "OFFLINE"
    extra_time_s: int = 0
    remaining_s: int = 0
    is_paused: bool = False
    latest_revision: int = 0
    submitted_at: str | None = None
    incident_reason: str | None = None


class JoinRoomResponse(BaseModel):
    attempt_token: str
    attempt: AttemptStatusResponse


class ResetDeviceRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=250)


@router.get("/rooms", response_model=list[RoomSummaryDTO])
def list_rooms(
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[RoomSummaryDTO]:
    exams = db.execute(select(Exam).order_by(Exam.created_at.desc())).scalars().all()
    q_counts = dict(
        db.execute(
            select(ExamQuestion.exam_id, func.count(ExamQuestion.id)).group_by(ExamQuestion.exam_id)
        ).all()
    )
    return [
        RoomSummaryDTO(
            exam_id=ex.id,
            classroom_id=ex.classroom_id,
            room_code=ex.room_code,
            title=ex.title,
            duration_s=ex.duration_s,
            status=ex.status,
            remaining_s=compute_remaining_seconds(ex),
            is_paused=ex.paused_at is not None,
            question_count=int(q_counts.get(ex.id, 0)),
        )
        for ex in exams
    ]


@router.post("/rooms", response_model=CreateRoomResponse, status_code=201)
def create_room(
    payload: CreateRoomRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> CreateRoomResponse:
    secret: bytes = request.app.state.server_secret
    exam, issued = create_waiting_room_session(
        db,
        classroom_id=payload.classroom_id,
        title=payload.title,
        duration_s=payload.duration_s,
        invite_ttl_minutes=payload.invite_ttl_minutes,
        teacher_id=teacher.teacher_id,
        server_secret=secret,
    )
    return CreateRoomResponse(
        room=RoomSummaryDTO(
            exam_id=exam.id,
            classroom_id=exam.classroom_id,
            room_code=exam.room_code,
            title=exam.title,
            duration_s=exam.duration_s,
            status=exam.status,
        ),
        invites=[
            IssuedInviteResponse(
                student_id=inv.student_id,
                roster_code=inv.roster_code,
                full_name=inv.full_name,
                invite_code=inv.invite_code,
                expires_at=inv.expires_at.isoformat(),
            )
            for inv in issued
        ],
    )


@router.get("/rooms/{exam_id}/roster", response_model=list[RoomRosterEntryDTO])
def get_room_roster(
    exam_id: str,
    _teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> list[RoomRosterEntryDTO]:
    exam = db.get(Exam, exam_id)
    if exam is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng thi.")
    if exam.status == "RUNNING":
        evaluate_room_presence(db, exam_id=exam_id)
    students = list_classroom_students(db, classroom_id=exam.classroom_id)
    attempts = {
        a.student_id: a
        for a in db.execute(select(Attempt).where(Attempt.exam_id == exam_id)).scalars().all()
    }
    open_incident_by_attempt = {
        inc.attempt_id: inc.id
        for inc in db.execute(
            select(Incident).where(Incident.exam_id == exam_id, Incident.state == "OPEN")
        )
        .scalars()
        .all()
    }
    bound_attempt_ids = set(
        db.execute(
            select(DeviceBinding.attempt_id).where(
                DeviceBinding.exam_id == exam_id,
                DeviceBinding.revoked_at.is_(None),
            )
        )
        .scalars()
        .all()
    )

    attempt_ids = [a.id for a in attempts.values()]
    answered_counts: dict[str, int] = {}
    if attempt_ids:
        rows = db.execute(
            select(
                AnswerRevision.attempt_id,
                func.count(func.distinct(AnswerRevision.question_version_id)),
            )
            .where(AnswerRevision.attempt_id.in_(attempt_ids))
            .group_by(AnswerRevision.attempt_id)
        ).all()
        answered_counts = {att_id: int(cnt) for att_id, cnt in rows}

    entries: list[RoomRosterEntryDTO] = []
    for st in students:
        att = attempts.get(st.id)
        entries.append(
            RoomRosterEntryDTO(
                student_id=st.id,
                roster_code=st.roster_code,
                full_name=st.full_name,
                attempt_id=att.id if att else None,
                attempt_state=att.state if att else "NOT_JOINED",
                presence_state=att.presence_state if att else "OFFLINE",
                device_bound=(att is not None and att.id in bound_attempt_ids),
                latest_revision=att.latest_revision if att else 0,
                answered_count=answered_counts.get(att.id, 0) if att else 0,
                reconnect_count=att.reconnect_count if att else 0,
                hidden_event_count=att.hidden_event_count if att else 0,
                extra_time_s=att.extra_time_s if att else 0,
                open_incident_id=open_incident_by_attempt.get(att.id) if att else None,
                submitted_at=att.submitted_at.isoformat() if (att and att.submitted_at) else None,
            )
        )
    return entries


@router.post("/rooms/{exam_id}/attempts/{attempt_id}/approve")
async def post_approve_attempt(
    exam_id: str,
    attempt_id: str,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    att = approve_attempt(db, exam_id=exam_id, attempt_id=attempt_id, teacher_id=teacher.teacher_id)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.send_to_attempt(
            exam_id,
            att.id,
            {"type": "attempt_update", "attempt_id": att.id, "attempt_state": att.state},
        )
        snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
        await ws_manager.broadcast_teacher_snapshot(exam_id, snap)
    return {"attempt_id": att.id, "state": att.state}


@router.post("/rooms/{exam_id}/approve-all")
async def post_approve_all(
    exam_id: str,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, int]:
    count = approve_all_pending(db, exam_id=exam_id, teacher_id=teacher.teacher_id)
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None and count > 0:
        snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
        await ws_manager.broadcast_teacher_snapshot(exam_id, snap)
    return {"approved_count": count}


@router.post("/rooms/{exam_id}/attempts/{attempt_id}/reset-device")
async def post_reset_device(
    exam_id: str,
    attempt_id: str,
    payload: ResetDeviceRequest,
    request: Request,
    teacher: TeacherPrincipal = Depends(require_teacher),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    att = reset_attempt_device(
        db,
        exam_id=exam_id,
        attempt_id=attempt_id,
        reason=payload.reason,
        teacher_id=teacher.teacher_id,
    )
    ws_manager = getattr(request.app.state, "ws_manager", None)
    if ws_manager is not None:
        await ws_manager.revoke_attempt_sockets(exam_id, att.id, "Thiết bị đã bị giáo viên đặt lại.")
        snap = get_room_monitoring_snapshot(db, exam_id=exam_id)
        await ws_manager.broadcast_teacher_snapshot(exam_id, snap)
    return {"attempt_id": att.id, "status": "device_reset"}


@router.post("/room/{room_code}/join", response_model=JoinRoomResponse)
def post_join_room(
    room_code: str,
    payload: JoinRoomRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> JoinRoomResponse:
    client_ip = request.client.host if request.client else "unknown"
    rate_key = f"{client_ip}:{room_code.strip().upper()}"
    request.app.state.join_rate_limiter.check_and_record(rate_key)

    secret: bytes = request.app.state.server_secret
    user_agent = request.headers.get("user-agent", "")
    result = join_exam_room(
        db,
        room_code=room_code,
        roster_code=payload.roster_code,
        invite_code=payload.invite_code,
        browser_key=payload.browser_key,
        user_agent=user_agent,
        server_secret=secret,
    )
    request.app.state.join_rate_limiter.reset(rate_key)

    return JoinRoomResponse(
        attempt_token=result.attempt_token,
        attempt=AttemptStatusResponse(
            attempt_id=result.attempt.id,
            exam_id=result.exam.id,
            room_code=result.exam.room_code,
            exam_title=result.exam.title,
            exam_status=result.exam.status,
            student_id=result.student.id,
            student_name=result.student.full_name,
            roster_code=result.student.roster_code,
            state=result.attempt.state,
            remaining_s=compute_remaining_seconds(result.exam, result.attempt),
            is_paused=result.exam.paused_at is not None,
            latest_revision=result.attempt.latest_revision,
            submitted_at=result.attempt.submitted_at.isoformat() if result.attempt.submitted_at else None,
        ),
    )


@router.get("/attempts/me", response_model=AttemptStatusResponse)
def get_my_attempt(
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> AttemptStatusResponse:
    attempt = db.get(Attempt, student.attempt_id)
    if attempt is None or attempt.student_id != student.student_id:
        raise HTTPException(status_code=404, detail="Không tìm thấy phiên thi.")
    if attempt.session_id != student.session_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Thiết bị này đã bị giáo viên đặt lại hoặc thay thế.",
        )
    exam = db.get(Exam, attempt.exam_id)
    st = db.get(Student, attempt.student_id)
    if exam is None or st is None:
        raise HTTPException(status_code=404, detail="Dữ liệu phòng thi không tồn tại.")
    open_inc = db.execute(
        select(Incident)
        .where(Incident.attempt_id == attempt.id, Incident.state == "OPEN")
        .order_by(Incident.opened_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    return AttemptStatusResponse(
        attempt_id=attempt.id,
        exam_id=exam.id,
        room_code=exam.room_code,
        exam_title=exam.title,
        exam_status=exam.status,
        student_id=st.id,
        student_name=st.full_name,
        roster_code=st.roster_code,
        state=attempt.state,
        presence_state=attempt.presence_state,
        extra_time_s=attempt.extra_time_s,
        remaining_s=compute_remaining_seconds(exam, attempt),
        is_paused=exam.paused_at is not None,
        latest_revision=attempt.latest_revision,
        submitted_at=attempt.submitted_at.isoformat() if attempt.submitted_at else None,
        incident_reason=open_inc.summary if open_inc else None,
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptStatusResponse)
def get_attempt_by_id(
    attempt_id: str,
    student: StudentPrincipal = Depends(require_student),
    db: Session = Depends(get_db),
) -> AttemptStatusResponse:
    """Strictly isolated: Student A cannot view Student B's attempt even if guessing UUID."""
    if attempt_id != student.attempt_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Không có quyền truy cập bài làm của học sinh khác.",
        )
    return get_my_attempt(student=student, db=db)
