import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "./App";
import { roomApi, rosterApi, systemApi } from "./api/client";

describe("ExamGuard P0 & P1 UI Flows", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    window.sessionStorage.clear();
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
  });

  it("renders teacher roster management on /classes", async () => {
    vi.spyOn(rosterApi, "listClasses").mockResolvedValue([
      { id: "c1", name: "12A1", academic_year: "2026-2027", student_count: 1, archived: false },
    ]);
    vi.spyOn(rosterApi, "listStudents").mockResolvedValue([
      { id: "s1", roster_code: "HS001", full_name: "Nguyễn Văn An", archived: false },
    ]);

    render(
      <MemoryRouter initialEntries={["/classes"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("Quản lý lớp học & danh sách học sinh")).toBeInTheDocument();
    expect(await screen.findByText("Nguyễn Văn An")).toBeInTheDocument();
    expect(screen.getByText("Nhập Excel / CSV")).toBeInTheDocument();
  });

  it("allows student to join and displays pending approval state on /join", async () => {
    vi.spyOn(roomApi, "joinRoom").mockResolvedValue({
      attempt_token: "tok-1",
      attempt: {
        attempt_id: "att-1",
        exam_id: "ex-1",
        room_code: "AB12CD",
        exam_title: "Kiểm tra 15 phút",
        exam_status: "WAITING",
        student_id: "s1",
        student_name: "Nguyễn Văn An",
        roster_code: "HS001",
        state: "PENDING_APPROVAL",
      },
    });
    vi.spyOn(roomApi, "getMyAttempt").mockResolvedValue({
      attempt_id: "att-1",
      exam_id: "ex-1",
      room_code: "AB12CD",
      exam_title: "Kiểm tra 15 phút",
      exam_status: "WAITING",
      student_id: "s1",
      student_name: "Nguyễn Văn An",
      roster_code: "HS001",
      state: "PENDING_APPROVAL",
    });

    render(
      <MemoryRouter initialEntries={["/join"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    fireEvent.change(await screen.findByLabelText("Mã phòng thi"), { target: { value: "AB12CD" } });
    fireEvent.change(screen.getByLabelText("Mã học sinh"), { target: { value: "HS001" } });
    fireEvent.change(screen.getByLabelText("Mã tham gia cá nhân"), { target: { value: "XYZ999" } });
    fireEvent.click(screen.getByRole("button", { name: "Gửi yêu cầu vào phòng" }));

    expect(await screen.findByText("Đang chờ giáo viên xác nhận vào phòng")).toBeInTheDocument();
    expect(screen.getByText("Nguyễn Văn An")).toBeInTheDocument();
  });
});
