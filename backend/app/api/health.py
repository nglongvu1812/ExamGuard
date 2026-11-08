"""Health and system network API routes."""

from __future__ import annotations

from datetime import UTC, datetime

from app.db.session import check_db_integrity
from app.launcher.network import discover_lan_interfaces, generate_qr_svg, get_firewall_guide
from fastapi import APIRouter, Query, Request
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1", tags=["system"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    app_version: str
    db_ok: bool
    db_journal_mode: str
    data_dir_writable: bool
    server_time_utc: str


class NetworkInterfaceDTO(BaseModel):
    name: str
    ip: str
    url: str
    kind: str
    recommended: bool


class NetworkStatusResponse(BaseModel):
    port: int
    selected_url: str
    qr_svg: str
    interfaces: list[NetworkInterfaceDTO]
    firewall_guide: list[str]
    offline_ready: bool


@router.get("/health", response_model=HealthResponse)
def get_health(request: Request) -> HealthResponse:
    settings = request.app.state.settings
    engine = request.app.state.engine
    db_ok, journal_mode = check_db_integrity(engine)
    writable = settings.data_dir.exists()
    return HealthResponse(
        status="ok" if db_ok and writable else "degraded",
        app_name=settings.app_name,
        app_version=settings.app_version,
        db_ok=db_ok,
        db_journal_mode=journal_mode,
        data_dir_writable=writable,
        server_time_utc=datetime.now(UTC).isoformat(),
    )


@router.get("/system/network", response_model=NetworkStatusResponse)
def get_network_status(
    request: Request,
    selected_ip: str | None = Query(default=None),
) -> NetworkStatusResponse:
    settings = request.app.state.settings
    port = int(getattr(request.app.state, "bound_port", settings.port))
    interfaces = discover_lan_interfaces(port)

    selected_url = f"http://127.0.0.1:{port}/join"
    if interfaces:
        matched = next((iface for iface in interfaces if iface.ip == selected_ip), None)
        selected_url = matched.url if matched else interfaces[0].url

    return NetworkStatusResponse(
        port=port,
        selected_url=selected_url,
        qr_svg=generate_qr_svg(selected_url),
        interfaces=[
            NetworkInterfaceDTO(
                name=iface.name,
                ip=iface.ip,
                url=iface.url,
                kind=iface.kind,
                recommended=iface.recommended,
            )
            for iface in interfaces
        ],
        firewall_guide=get_firewall_guide(port),
        offline_ready=True,
    )
