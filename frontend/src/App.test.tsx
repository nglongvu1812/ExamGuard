import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "./App";
import {
  auditApi,
  backupApi,
  examApi,
  monitoringApi,
  questionApi,
  resultsApi,
  roomApi,
  rosterApi,
  studentExamApi,
  studentResultApi,
  systemApi,
} from "./api/client";

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

  it("renders teacher T6 live monitoring dashboard and opens incident verification drawer", async () => {
    vi.spyOn(rosterApi, "listClasses").mockResolvedValue([
      { id: "c1", name: "12A9", academic_year: "2026-2027", student_count: 1, archived: false },
    ]);
    vi.spyOn(questionApi, "listBank").mockResolvedValue([]);
    vi.spyOn(roomApi, "listRooms").mockResolvedValue([
      {
        exam_id: "ex-mon",
        classroom_id: "c1",
        room_code: "MON123",
        title: "Kiểm tra Vật lý",
        duration_s: 900,
        status: "RUNNING",
        remaining_s: 650,
        is_paused: false,
        question_count: 5,
      },
    ]);
    vi.spyOn(monitoringApi, "getSnapshot").mockResolvedValue({
      exam_id: "ex-mon",
      room_code: "MON123",
      title: "Kiểm tra Vật lý",
      status: "RUNNING",
      is_paused: false,
      remaining_s: 650,
      question_count: 5,
      server_time_utc: "2026-11-08T12:00:00Z",
      policy: { heartbeat_s: 3, suspected_s: 5, disconnect_s: 15, lock_after_s: 30, grace_submit_s: 30 },
      summary: {
        total_students: 1,
        active_count: 0,
        submitted_count: 0,
        pending_count: 0,
        suspected_count: 0,
        disconnected_count: 1,
        locked_count: 1,
        open_incidents_count: 1,
      },
      open_incidents: [
        {
          id: "inc-1",
          attempt_id: "att-1",
          roster_code: "HS001",
          full_name: "Nguyễn Văn An",
          state: "OPEN",
          trigger_type: "HEARTBEAT_TIMEOUT",
          summary: "Mất tín hiệu kết nối 32 giây. Cần giáo viên xác minh kỹ thuật.",
          opened_at: "2026-11-08T12:00:00Z",
        },
      ],
      roster: [
        {
          student_id: "s1",
          roster_code: "HS001",
          full_name: "Nguyễn Văn An",
          attempt_id: "att-1",
          attempt_state: "LOCKED_PENDING_REVIEW",
          presence_state: "DISCONNECTED",
          device_bound: true,
          latest_revision: 3,
          answered_count: 3,
          last_heartbeat_at: "2026-11-08T11:59:28Z",
          heartbeat_age_s: 32,
          reconnect_count: 1,
          hidden_event_count: 2,
          extra_time_s: 0,
          open_incident_id: "inc-1",
          open_incident_summary: "Mất tín hiệu kết nối 32 giây. Cần giáo viên xác minh kỹ thuật.",
          submitted_at: null,
        },
      ],
    });
    vi.spyOn(monitoringApi, "getTimeline").mockResolvedValue({
      attempt_id: "att-1",
      exam_id: "ex-mon",
      roster_code: "HS001",
      full_name: "Nguyễn Văn An",
      attempt_state: "LOCKED_PENDING_REVIEW",
      presence_state: "DISCONNECTED",
      extra_time_s: 0,
      reconnect_count: 1,
      hidden_event_count: 2,
      events: [
        {
          id: "ev1",
          event_type: "HEARTBEAT_TIMEOUT",
          server_time: "2026-11-08T12:00:00Z",
          details: {},
        },
      ],
      incidents: [
        {
          id: "inc-1",
          state: "OPEN",
          trigger_type: "HEARTBEAT_TIMEOUT",
          summary: "Mất tín hiệu kết nối 32 giây. Cần giáo viên xác minh kỹ thuật.",
          opened_at: "2026-11-08T12:00:00Z",
          resolved_at: null,
          resolution_reason: null,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/exams/new"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Sự cố đang chờ giáo viên xác minh/i)).toBeInTheDocument();
    expect(screen.getByText(/Rời màn hình \(2\) · Cần xác minh/i)).toBeInTheDocument();
    expect(screen.getByText(/không tự động kết luận gian lận/i)).toBeInTheDocument();
    expect(screen.queryByText(/^GIAN LẬN$/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Xử lý sự cố" }));
    expect(await screen.findByText(/Hồ sơ sự cố & Nhật ký tín hiệu — HS001/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Gia hạn (+phút)" })).toBeInTheDocument();
  });

  it("renders S5 technical lock screen on /join when attempt is LOCKED_PENDING_REVIEW", async () => {
    window.sessionStorage.setItem("eg_student_token", "tok-locked");
    vi.spyOn(roomApi, "getMyAttempt").mockResolvedValue({
      attempt_id: "att-lock",
      exam_id: "ex-lock",
      room_code: "LOCK01",
      exam_title: "Kiểm tra Hóa",
      exam_status: "RUNNING",
      student_id: "s1",
      student_name: "Lê Minh",
      roster_code: "HS002",
      state: "LOCKED_PENDING_REVIEW",
      presence_state: "DISCONNECTED",
      remaining_s: 500,
      is_paused: false,
      latest_revision: 4,
      incident_reason: "Mất tín hiệu kết nối quá 30 giây. Cần giáo viên xác minh kỹ thuật.",
    });
    vi.spyOn(studentExamApi, "syncAttempt").mockResolvedValue({
      attempt_id: "att-lock",
      exam_id: "ex-lock",
      exam_status: "RUNNING",
      attempt_state: "LOCKED_PENDING_REVIEW",
      presence_state: "DISCONNECTED",
      extra_time_s: 0,
      is_paused: false,
      remaining_s: 500,
      server_time_utc: "2026-11-08T12:05:00Z",
      latest_revision: 4,
      saved_answers: {},
      submitted_at: null,
      snapshot_hash: null,
      incident_reason: "Mất tín hiệu kết nối quá 30 giây. Cần giáo viên xác minh kỹ thuật.",
    });

    render(
      <MemoryRouter initialEntries={["/join"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(
      await screen.findByText("Bài thi đang tạm khóa chờ giáo viên xác minh")
    ).toBeInTheDocument();
    expect(screen.getByText(/Máy chủ đã lưu an toàn đến lần sửa #4/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Kiểm tra trạng thái mở lại" })).toBeInTheDocument();
  });

  it("renders T7/T8 teacher results, publish modal, audit verification, and Phúc khảo trace on /results", async () => {
    vi.spyOn(examApi, "listExams").mockResolvedValue([
      {
        exam_id: "ex-res-1",
        classroom_id: "c1",
        room_code: "RES01",
        title: "Kiểm tra Toán Học kỳ 1",
        duration_s: 900,
        status: "REVIEWED",
        question_count: 1,
        shuffle_questions: true,
        shuffle_options: true,
        remaining_s: 0,
        is_paused: false,
        start_at: "2026-11-08T10:00:00Z",
        deadline_at: "2026-11-08T10:15:00Z",
        closed_at: "2026-11-08T10:15:00Z",
        policy: { heartbeat_s: 3, suspected_s: 5, disconnect_s: 15, lock_after_s: 30, grace_submit_s: 30 },
      },
    ]);
    vi.spyOn(resultsApi, "getExamResults").mockResolvedValue({
      exam: {
        exam_id: "ex-res-1",
        classroom_id: "c1",
        classroom_name: "12A1",
        room_code: "RES01",
        title: "Kiểm tra Toán Học kỳ 1",
        status: "REVIEWED",
        closed_at: "2026-11-08T10:15:00Z",
        reviewed_at: "2026-11-08T10:20:00Z",
        published_at: null,
        unresolved_attempts: 0,
        question_count: 1,
      },
      stats: {
        total_students: 1,
        graded_count: 1,
        unsubmitted_count: 0,
        mean_score: 10,
        median_score: 10,
        max_score: 10,
        min_score: 10,
        bins: { excellent: 1, good: 0, average: 0, below_average: 0 },
      },
      students: [
        {
          student_id: "s1",
          roster_code: "HS001",
          full_name: "Nguyễn Văn An",
          attempt_id: "att1",
          attempt_state: "SUBMITTED",
          status_label: "Đã nộp bài",
          submission_id: "sub1",
          submitted_at: "2026-11-08T10:14:00Z",
          snapshot_hash: "abcdef1234567890abcdef",
          raw_correct: 1,
          total_questions: 1,
          earned_points: 1,
          max_points: 1,
          score_10: 10,
          score_version: 1,
          regrade_count: 0,
          receipt_code: null,
          receipt_version: 0,
          open_incidents: 0,
        },
      ],
      grade_runs: [
        {
          id: "gr1",
          run_number: 1,
          code_version: "scoring-v1.0",
          reason: "Chấm lần đầu",
          created_at: "2026-11-08T10:20:00Z",
        },
      ],
      questions: [],
    });
    vi.spyOn(auditApi, "verifyChain").mockResolvedValue({
      valid: true,
      event_count: 5,
      broken_event_id: null,
      limitation_note: "Chuỗi hash SHA-256 hợp lệ cục bộ.",
      recent_events: [],
    });
    vi.spyOn(resultsApi, "getStudentTrace").mockResolvedValue({
      exam: { exam_id: "ex-res-1", room_code: "RES01", title: "Kiểm tra Toán Học kỳ 1", status: "REVIEWED", seed: 99 },
      student: { student_id: "s1", roster_code: "HS001", full_name: "Nguyễn Văn An" },
      attempt: null,
      submission: { submission_id: "sub1", submission_mode: "student_submit", snapshot_hash: "abcdef1234567890", submitted_at: "2026-11-08T10:14:00Z", answer_snapshot: {} },
      permutation_seed: 12345,
      questions: [],
      answer_revisions: [],
      score_versions: [
        {
          id: "sv1",
          version: 1,
          score_10: 10,
          raw_correct: 1,
          total_questions: 1,
          earned_points: 1,
          max_points: 1,
          reason: "Chấm lần đầu",
          supersedes_id: null,
          is_current: true,
          created_at: "2026-11-08T10:20:00Z",
        },
      ],
      receipt_versions: [],
      presence_events: [],
      incidents: [],
      audit_events: [],
    });

    render(
      <MemoryRouter initialEntries={["/results"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText("Chấm điểm, Công bố Kết quả & Phúc khảo")).toBeInTheDocument();
    expect(await screen.findByText("Chuỗi Audit hợp lệ (5 sự kiện)")).toBeInTheDocument();
    expect(screen.getByText("Nguyễn Văn An")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Công bố điểm & Đáp án/i }));
    expect(await screen.findByText("Xác nhận Công bố Điểm & Đáp án?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Hủy bỏ" }));

    fireEvent.click(screen.getByRole("button", { name: /Xem vết phúc khảo/i }));
    expect(await screen.findByText(/Hồ sơ Phúc khảo — HS001 · Nguyễn Văn An/i)).toBeInTheDocument();
  });

  it("renders S7 student published result with superseded update banner on /join", async () => {
    window.sessionStorage.setItem("eg_student_token", "tok-pub");
    vi.spyOn(roomApi, "getMyAttempt").mockResolvedValue({
      attempt_id: "att-pub",
      exam_id: "ex-pub",
      room_code: "PUB01",
      exam_title: "Kiểm tra Sử",
      exam_status: "PUBLISHED",
      student_id: "s1",
      student_name: "Trần Thu Hà",
      roster_code: "HS005",
      state: "SUBMITTED",
      submitted_at: "2026-11-08T11:00:00Z",
    });
    vi.spyOn(studentResultApi, "getMyResult").mockResolvedValue({
      exam_id: "ex-pub",
      exam_title: "Kiểm tra Sử",
      room_code: "PUB01",
      exam_status: "PUBLISHED",
      attempt_id: "att-pub",
      student_name: "Trần Thu Hà",
      roster_code: "HS005",
      score_10: 10,
      raw_correct: 1,
      total_questions: 1,
      earned_points: 1,
      max_points: 1,
      score_version: 2,
      regrade_reason: "Cập nhật đáp án câu 1",
      receipt_code: "EG-PUB01-HS005",
      receipt_version: 2,
      superseded_previous: true,
      document_sha256: "abcdef1234567890abcdef1234567890",
      snapshot_hash: "112233445566",
      submitted_at: "2026-11-08T11:00:00Z",
      published_at: "2026-11-08T11:10:00Z",
      questions: [
        {
          position: 1,
          question_version_id: "qv1",
          blocks: [{ type: "text", text: "Chiến thắng Điện Biên Phủ năm nào?" }],
          options: [
            { option_id: "o1", display_label: "A", blocks: [{ type: "text", text: "1954" }] },
          ],
          selected_option_ids: ["o1"],
          correct_option_ids: ["o1"],
          is_correct: true,
          earned_points: 1,
          weight: 1,
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/join"]}>
        <AppRoutes />
      </MemoryRouter>
    );

    expect(await screen.findByText(/Có kết quả cập nhật \(Biên nhận v2\)/i)).toBeInTheDocument();
    expect(screen.getByText("10.00")).toBeInTheDocument();
    expect(screen.getByText("Chiến thắng Điện Biên Phủ năm nào?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Tải biên nhận PDF" })).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /Tải thẻ chia sẻ PNG/i })
    ).toBeInTheDocument();
  });
});
