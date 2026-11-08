import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "./App";
import { systemApi } from "./api/client";

describe("ExamGuard P0 Shells", () => {
  beforeEach(() => {
    vi.spyOn(systemApi, "getHealth").mockResolvedValue({
      status: "ok",
      app_name: "ExamGuard",
      app_version: "0.1.0",
      db_ok: true,
      db_journal_mode: "wal",
      data_dir_writable: true,
      server_time_utc: "2026-11-08T11:00:00Z",
    });
    vi.spyOn(systemApi, "getNetworkStatus").mockResolvedValue({
      port: 8000,
      selected_url: "http://192.168.10.20:8000/join",
      qr_svg: '<svg viewBox="0 0 10 10"><path d="M0 0h1v1z"/></svg>',
      interfaces: [
        {
          name: "Wi-Fi",
          ip: "192.168.10.20",
          url: "http://192.168.10.20:8000/join",
          kind: "wifi",
          recommended: true,
        },
      ],
      firewall_guide: ["Đảm bảo laptop giáo viên và điện thoại dùng chung mạng LAN."],
      offline_ready: true,
    });
  });

  it("renders teacher dashboard with Vietnamese navigation and LAN QR", async () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("Bảng điều khiển giáo viên")).toBeInTheDocument();
    expect(await screen.findByText("http://192.168.10.20:8000/join")).toBeInTheDocument();
    expect(screen.getByText("Lớp học")).toBeInTheDocument();
    expect(screen.getByText("Ngân hàng đề")).toBeInTheDocument();
  });

  it("renders distraction-free student join shell on /join", async () => {
    render(
      <MemoryRouter initialEntries={["/join"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("Vào phòng kiểm tra")).toBeInTheDocument();
    expect(screen.getByLabelText("Mã phòng thi")).toBeInTheDocument();
    expect(screen.getByLabelText("Mã học sinh")).toBeInTheDocument();
  });
});
