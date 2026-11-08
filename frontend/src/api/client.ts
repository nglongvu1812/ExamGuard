export interface HealthResponse {
  status: string;
  app_name: string;
  app_version: string;
  db_ok: boolean;
  db_journal_mode: string;
  data_dir_writable: boolean;
  server_time_utc: string;
}

export interface NetworkInterfaceInfo {
  name: string;
  ip: string;
  url: string;
  kind: "wifi" | "ethernet" | "hotspot" | "other";
  recommended: boolean;
}

export interface NetworkStatusResponse {
  port: number;
  selected_url: string;
  qr_svg: string;
  interfaces: NetworkInterfaceInfo[];
  firewall_guide: string[];
  offline_ready: boolean;
}

export interface ClassroomDTO {
  id: string;
  name: string;
  academic_year: string;
  student_count: number;
  archived: boolean;
}

export interface StudentDTO {
  id: string;
  roster_code: string;
  full_name: string;
  archived: boolean;
}

export interface ImportPreviewRowDTO {
  row_number: number;
  roster_code: string;
  full_name: string;
  note: string;
  status: "NEW" | "DUPLICATE_IN_FILE" | "EXISTS_SAME_CLASS" | "EXISTS_OTHER_CLASS" | "INVALID";
  message: string;
}

export interface ImportPreviewResponse {
  rows: ImportPreviewRowDTO[];
  new_count: number;
  conflict_count: number;
  invalid_count: number;
  has_conflicts: boolean;
}

export interface ImportCommitResponse {
  added: number;
  updated: number;
  skipped: number;
}

export interface RoomSummaryDTO {
  exam_id: string;
  classroom_id: string;
  room_code: string;
  title: string;
  duration_s: number;
  status: string;
}

export interface IssuedInviteResponse {
  student_id: string;
  roster_code: string;
  full_name: string;
  invite_code: string;
  expires_at: string;
}

export interface CreateRoomResponse {
  room: RoomSummaryDTO;
  invites: IssuedInviteResponse[];
}

export interface RoomRosterEntryDTO {
  student_id: string;
  roster_code: string;
  full_name: string;
  attempt_id: string | null;
  attempt_state: string;
  device_bound: boolean;
}

export interface AttemptStatusResponse {
  attempt_id: string;
  exam_id: string;
  room_code: string;
  exam_title: string;
  exam_status: string;
  student_id: string;
  student_name: string;
  roster_code: string;
  state: string;
}

export interface JoinRoomResponse {
  attempt_token: string;
  attempt: AttemptStatusResponse;
}

let cachedTeacherToken: string | null = null;

async function ensureTeacherToken(): Promise<string> {
  if (cachedTeacherToken) return cachedTeacherToken;
  const res = await fetch("/api/v1/auth/teacher/local-session", { method: "POST" });
  if (!res.ok) {
    throw new Error("Không thể xác thực phiên giáo viên trên máy chủ cục bộ.");
  }
  const data = (await res.json()) as { token: string };
  cachedTeacherToken = data.token;
  return cachedTeacherToken;
}

async function fetchJson<T>(url: string, init?: RequestInit, authMode?: "teacher" | "student", studentToken?: string): Promise<T> {
  const headers = new Headers(init?.headers);
  if (!(init?.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (authMode === "teacher") {
    const token = await ensureTeacherToken();
    headers.set("Authorization", `Bearer ${token}`);
  } else if (authMode === "student" && studentToken) {
    headers.set("Authorization", `Bearer ${studentToken}`);
  }

  const response = await fetch(url, { ...init, headers });
  if (response.status === 401 && authMode === "teacher") {
    cachedTeacherToken = null;
    const retryToken = await ensureTeacherToken();
    headers.set("Authorization", `Bearer ${retryToken}`);
    const retry = await fetch(url, { ...init, headers });
    if (retry.ok) return (await retry.json()) as T;
  }

  if (!response.ok) {
    let detail = `Lỗi máy chủ (${response.status})`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      // ignore json parse failure
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

export const systemApi = {
  getHealth(): Promise<HealthResponse> {
    return fetchJson<HealthResponse>("/api/v1/health");
  },
  getNetworkStatus(selectedIp?: string): Promise<NetworkStatusResponse> {
    const query = selectedIp ? `?selected_ip=${encodeURIComponent(selectedIp)}` : "";
    return fetchJson<NetworkStatusResponse>(`/api/v1/system/network${query}`);
  },
};

export const rosterApi = {
  listClasses(): Promise<ClassroomDTO[]> {
    return fetchJson<ClassroomDTO[]>("/api/v1/classes", undefined, "teacher");
  },
  createClass(name: string, academic_year: string): Promise<ClassroomDTO> {
    return fetchJson<ClassroomDTO>(
      "/api/v1/classes",
      { method: "POST", body: JSON.stringify({ name, academic_year }) },
      "teacher"
    );
  },
  archiveClass(id: string): Promise<ClassroomDTO> {
    return fetchJson<ClassroomDTO>(`/api/v1/classes/${id}`, { method: "DELETE" }, "teacher");
  },
  listStudents(classroomId: string): Promise<StudentDTO[]> {
    return fetchJson<StudentDTO[]>(`/api/v1/classes/${classroomId}/students`, undefined, "teacher");
  },
  createStudent(classroomId: string, roster_code: string, full_name: string): Promise<StudentDTO> {
    return fetchJson<StudentDTO>(
      `/api/v1/classes/${classroomId}/students`,
      { method: "POST", body: JSON.stringify({ roster_code, full_name }) },
      "teacher"
    );
  },
  updateStudent(studentId: string, full_name: string): Promise<StudentDTO> {
    return fetchJson<StudentDTO>(
      `/api/v1/students/${studentId}`,
      { method: "PATCH", body: JSON.stringify({ full_name }) },
      "teacher"
    );
  },
  archiveStudent(studentId: string): Promise<StudentDTO> {
    return fetchJson<StudentDTO>(`/api/v1/students/${studentId}`, { method: "DELETE" }, "teacher");
  },
  previewImport(classroomId: string, file: File): Promise<ImportPreviewResponse> {
    const form = new FormData();
    form.append("file", file);
    return fetchJson<ImportPreviewResponse>(
      `/api/v1/classes/${classroomId}/import/preview`,
      { method: "POST", body: form },
      "teacher"
    );
  },
  commitImport(
    classroomId: string,
    rows: ImportPreviewRowDTO[],
    duplicate_policy: "skip" | "update_name" | "fail"
  ): Promise<ImportCommitResponse> {
    return fetchJson<ImportCommitResponse>(
      `/api/v1/classes/${classroomId}/import/commit`,
      { method: "POST", body: JSON.stringify({ rows, duplicate_policy }) },
      "teacher"
    );
  },
};

export const roomApi = {
  listRooms(): Promise<RoomSummaryDTO[]> {
    return fetchJson<RoomSummaryDTO[]>("/api/v1/rooms", undefined, "teacher");
  },
  createRoom(classroom_id: string, title: string, duration_s: number): Promise<CreateRoomResponse> {
    return fetchJson<CreateRoomResponse>(
      "/api/v1/rooms",
      { method: "POST", body: JSON.stringify({ classroom_id, title, duration_s }) },
      "teacher"
    );
  },
  getRoomRoster(examId: string): Promise<RoomRosterEntryDTO[]> {
    return fetchJson<RoomRosterEntryDTO[]>(`/api/v1/rooms/${examId}/roster`, undefined, "teacher");
  },
  approveAttempt(examId: string, attemptId: string): Promise<{ attempt_id: string; state: string }> {
    return fetchJson<{ attempt_id: string; state: string }>(
      `/api/v1/rooms/${examId}/attempts/${attemptId}/approve`,
      { method: "POST" },
      "teacher"
    );
  },
  approveAll(examId: string): Promise<{ approved_count: number }> {
    return fetchJson<{ approved_count: number }>(
      `/api/v1/rooms/${examId}/approve-all`,
      { method: "POST" },
      "teacher"
    );
  },
  resetDevice(examId: string, attemptId: string, reason: string): Promise<{ attempt_id: string }> {
    return fetchJson<{ attempt_id: string }>(
      `/api/v1/rooms/${examId}/attempts/${attemptId}/reset-device`,
      { method: "POST", body: JSON.stringify({ reason }) },
      "teacher"
    );
  },
  joinRoom(
    roomCode: string,
    roster_code: string,
    invite_code: string,
    browser_key: string
  ): Promise<JoinRoomResponse> {
    return fetchJson<JoinRoomResponse>(`/api/v1/room/${encodeURIComponent(roomCode)}/join`, {
      method: "POST",
      body: JSON.stringify({ roster_code, invite_code, browser_key }),
    });
  },
  getMyAttempt(studentToken: string): Promise<AttemptStatusResponse> {
    return fetchJson<AttemptStatusResponse>("/api/v1/attempts/me", undefined, "student", studentToken);
  },
};
