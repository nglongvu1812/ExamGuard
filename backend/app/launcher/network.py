"""LAN interface discovery, dynamic QR generation, and Windows firewall guidance."""

from __future__ import annotations

import io
import ipaddress
import platform
import re
import socket
import subprocess
from dataclasses import dataclass

import qrcode
import qrcode.image.svg


@dataclass(frozen=True)
class NetworkInterfaceInfo:
    name: str
    ip: str
    url: str
    kind: str  # "wifi" | "ethernet" | "hotspot" | "other"
    recommended: bool


def _classify_interface(name: str, ip: str) -> tuple[str, int]:
    lowered = name.lower()
    skip_keywords = (
        "virtual",
        "vethernet",
        "vmware",
        "vbox",
        "docker",
        "wsl",
        "loopback",
    )
    if any(skip in lowered for skip in skip_keywords):
        return ("other", 10)
    if "wi-fi" in lowered or "wifi" in lowered or "wlan" in lowered or "wireless" in lowered:
        return ("wifi", 100)
    if "local area connection*" in lowered or "hotspot" in lowered or ip.startswith("192.168.137."):
        return ("hotspot", 75)
    if "ethernet" in lowered or "lan" in lowered:
        return ("ethernet", 85)
    return ("other", 50)


def _discover_windows_interfaces() -> list[tuple[str, str]]:
    """Parse ipconfig output on Windows without external admin tools or hardcoding."""
    try:
        output = subprocess.check_output(
            ["ipconfig"],
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=3,
        )
    except (OSError, subprocess.SubprocessError):
        return []

    results: list[tuple[str, str]] = []
    current_adapter = "Network"
    for line in output.splitlines():
        if line and not line.startswith(" ") and line.strip().endswith(":"):
            current_adapter = line.strip().rstrip(":")
            continue
        match = re.search(r"IPv4[^:]*:\s*([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)", line)
        if match:
            results.append((current_adapter, match.group(1)))
    return results


def _discover_socket_fallback() -> list[tuple[str, str]]:
    """Cross-platform fallback interface discovery via local socket bindings."""
    candidates: list[tuple[str, str]] = []
    try:
        hostname = socket.gethostname()
        for info in socket.getaddrinfo(hostname, None, socket.AF_INET):
            ip = str(info[4][0])
            candidates.append(("LAN Interface", ip))
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            candidates.append(("Primary Route", str(sock.getsockname()[0])))
    except OSError:
        pass
    return candidates


def discover_lan_interfaces(port: int) -> list[NetworkInterfaceInfo]:
    """Enumerate valid private/LAN IPv4 interfaces dynamically (never hardcode IP)."""
    raw_pairs = (
        _discover_windows_interfaces()
        if platform.system().lower() == "windows"
        else []
    )
    if not raw_pairs:
        raw_pairs = _discover_socket_fallback()

    seen_ips: set[str] = set()
    scored: list[tuple[int, NetworkInterfaceInfo]] = []
    for adapter_name, ip_str in raw_pairs:
        if ip_str in seen_ips:
            continue
        try:
            ip_obj = ipaddress.IPv4Address(ip_str)
        except ipaddress.AddressValueError:
            continue
        if ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_multicast:
            continue
        seen_ips.add(ip_str)
        kind, score = _classify_interface(adapter_name, ip_str)
        scored.append(
            (
                score,
                NetworkInterfaceInfo(
                    name=adapter_name,
                    ip=ip_str,
                    url=f"http://{ip_str}:{port}/join",
                    kind=kind,
                    recommended=False,
                ),
            )
        )

    scored.sort(key=lambda item: item[0], reverse=True)
    interfaces: list[NetworkInterfaceInfo] = []
    for idx, (_score, info) in enumerate(scored):
        interfaces.append(
            NetworkInterfaceInfo(
                name=info.name,
                ip=info.ip,
                url=info.url,
                kind=info.kind,
                recommended=(idx == 0),
            )
        )
    return interfaces


def generate_qr_svg(url: str) -> str:
    """Generate a self-contained SVG QR code offline with no external service."""
    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(url, image_factory=factory, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def get_firewall_guide(port: int) -> list[str]:
    """Provide human-readable Windows Firewall troubleshooting steps."""
    return [
        "Đảm bảo laptop giáo viên và điện thoại học sinh dùng chung một mạng Wi-Fi/AP nội bộ.",
        (
            "Nếu điện thoại không mở được trang thi, kiểm tra Windows Defender Firewall "
            f"đã cho phép ExamGuard/Python nhận kết nối Private/LAN trên cổng {port}."
        ),
        (
            "Tránh bật Client Isolation (AP Isolation) trên bộ phát Wi-Fi lớp học "
            "vì tính năng này chặn điện thoại nhìn thấy máy chủ giáo viên."
        ),
        (
            "Nếu dùng Windows Mobile Hotspot và có trên 8 thiết bị bị rớt mạng, "
            "hãy chuyển sang Router/AP Wi-Fi nội bộ độc lập."
        ),
    ]
