import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "./App";
import { backupApi, questionApi, roomApi, rosterApi, studentExamApi, systemApi } from "./api/client";

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

  it("renders question bank & converter page with approved KaTeX item", async () => {
    vi.spyOn(questionApi, "listBank").mockResolvedValue([
      {
        question_id: "q1",
        version_id: "qv1",
        bank_name: "Toán 12",
        version_number: 1,
        blocks: [
          { type: "text", text: "Tính " },
          { type: "math", latex: "\\frac{1}{2}" },
        ],
        options: [],
        correct_option_ids: [],
        approved_at: "2026-11-08T11:00:00Z",
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/questions"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("Ngân hàng đề & Trình chuyển đổi Word (.docx)")).toBeInTheDocument();
    expect(await screen.findByText("Ngân hàng câu hỏi đã duyệt (1)")).toBeInTheDocument();
  });

  it("renders student active exam screen, saves answer with ACK badge, and opens submit confirm", async () => {
    window.sessionStorage.setItem("eg_student_token", "tok-active");
    vi.spyOn(roomApi, "getMyAttempt").mockResolvedValue({
      attempt_id: "att-live",
      exam_id: "ex-live",
      room_code: "LIVE99",
      exam_title: "Kiểm tra Toán giữa kỳ",
      exam_status: "RUNNING",
      student_id: "s1",
      student_name: "Nguyễn Văn An",
      roster_code: "HS001",
      state: "ACTIVE",
      remaining_s: 840,
      is_paused: false,
      latest_revision: 0,
    });
    vi.spyOn(studentExamApi, "getPaper").mockResolvedValue({
      attempt_id: "att-live",
      exam_id: "ex-live",
      exam_title: "Kiểm tra Toán giữa kỳ",
      room_code: "LIVE99",
      exam_status: "RUNNING",
      attempt_state: "ACTIVE",
      is_paused: false,
      remaining_s: 840,
      server_time_utc: "2026-11-08T11:30:00Z",
      deadline_at: "2026-11-08T11:44:00Z",
      latest_revision: 0,
      questions: [
        {
          position: 1,
          question_version_id: "qv-1",
          blocks: [{ type: "text", text: "1 + 1 bằng mấy?" }],
          options: [
            { option_id: "opt-a", display_label: "A", blocks: [{ type: "text", text: "2" }] },
            { option_id: "opt-b", display_label: "B", blocks: [{ type: "text", text: "3" }] },
          ],
        },
      ],
      saved_answers: {},
    });
    vi.spyOn(studentExamApi, "saveAnswer").mockResolvedValue({
      status: "saved",
      attempt_id: "att-live",
      question_version_id: "qv-1",
      selected_option_ids: ["opt-a"],
      server_revision: 1,
      idempotency_key: "k1",
      committed_at: "2026-11-08T11:30:05Z",
      duplicate: false,
    });

    render(
      <MemoryRouter initialEntries={["/join"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("1 + 1 bằng mấy?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /A\s*2/i }));
    expect(await screen.findByText("Đã lưu #1")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Nộp bài ngay/i }));
    expect(await screen.findByText("Xác nhận nộp bài?")).toBeInTheDocument();
  });

  it("renders settings & backup page on /settings", async () => {
    vi.spyOn(backupApi, "listBackups").mockResolvedValue([
      {
        id: "bk1",
        created_at: "2026-11-08T11:00:00Z",
        schema_version: "0004_exam_engine_and_answers",
        sha256: "abcdef1234567890abcdef1234567890",
        location: "examguard_manual_test.zip",
        record_counts: { exams: 1 },
        verified_at: null,
      },
    ]);

    render(
      <MemoryRouter initialEntries={["/settings"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("Sao lưu, Khôi phục & Cài đặt hệ thống")).toBeInTheDocument();
    expect(await screen.findByText("examguard_manual_test.zip")).toBeInTheDocument();
  });
});
