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
  remaining_s?: number;
  is_paused?: boolean;
  question_count?: number;
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
  presence_state?: string;
  device_bound: boolean;
  latest_revision?: number;
  answered_count?: number;
  reconnect_count?: number;
  hidden_event_count?: number;
  extra_time_s?: number;
  open_incident_id?: string | null;
  submitted_at?: string | null;
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
  presence_state?: string;
  extra_time_s?: number;
  remaining_s?: number;
  is_paused?: boolean;
  latest_revision?: number;
  submitted_at?: string | null;
  incident_reason?: string | null;
}

export interface JoinRoomResponse {
  attempt_token: string;
  attempt: AttemptStatusResponse;
}

let cachedTeacherToken: string | null = null;

export async function ensureTeacherToken(): Promise<string> {
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

export interface ContentBlockDTO {
  type: string;
  text?: string;
  latex?: string;
  asset_id?: string;
  alt?: string;
  parse_warning?: boolean;
}

export interface OptionDraftDTO {
  option_id: string;
  label: string;
  blocks: ContentBlockDTO[];
}

export interface QuestionDraftDTO {
  id: string;
  import_job_id: string;
  position: number;
  question_type: string;
  blocks: ContentBlockDTO[];
  options: OptionDraftDTO[];
  answer: {
    correct_option_ids: string[];
    status: string;
    provenance: string | null;
  };
  source: {
    file_sha256: string;
    filename: string;
    anchors: string[];
    raw_preview: string;
  };
  warnings: string[];
  confidence: Record<string, number>;
  status: string;
  approved_version_id: string | null;
}

export interface ImportJobResponse {
  job_id: string;
  status: string;
  parser_version: string;
  summary: {
    total_questions: number;
    warnings_count: number;
    unknown_key_count: number;
    filename: string;
    sha256: string;
  };
  drafts: QuestionDraftDTO[];
}

export interface ApprovedQuestionDTO {
  question_id: string;
  version_id: string;
  bank_name: string;
  version_number: number;
  blocks: ContentBlockDTO[];
  options: { option_id: string; label: string; blocks: ContentBlockDTO[] }[];
  correct_option_ids: string[];
  approved_at: string;
}

export const questionApi = {
  importDocx(file: File): Promise<ImportJobResponse> {
    const form = new FormData();
    form.append("file", file);
    return fetchJson<ImportJobResponse>(
      "/api/v1/questions/import",
      { method: "POST", body: form },
      "teacher"
    );
  },
  getImportJob(jobId: string): Promise<ImportJobResponse> {
    return fetchJson<ImportJobResponse>(`/api/v1/questions/import/${jobId}`, undefined, "teacher");
  },
  updateDraft(
    draftId: string,
    payload: { correct_option_ids?: string[]; blocks?: ContentBlockDTO[]; options?: OptionDraftDTO[] }
  ): Promise<QuestionDraftDTO> {
    return fetchJson<QuestionDraftDTO>(
      `/api/v1/questions/drafts/${draftId}`,
      { method: "PATCH", body: JSON.stringify(payload) },
      "teacher"
    );
  },
  approveDraft(draftId: string, bank_name: string): Promise<{ question_id: string; version_id: string }> {
    return fetchJson<{ question_id: string; version_id: string }>(
      `/api/v1/questions/drafts/${draftId}/approve`,
      { method: "POST", body: JSON.stringify({ bank_name }) },
      "teacher"
    );
  },
  approveReadyInJob(jobId: string, bank_name: string): Promise<{ approved_count: number; skipped_count: number }> {
    return fetchJson<{ approved_count: number; skipped_count: number }>(
      `/api/v1/questions/import/${jobId}/approve-ready`,
      { method: "POST", body: JSON.stringify({ bank_name }) },
      "teacher"
    );
  },
  listBank(): Promise<ApprovedQuestionDTO[]> {
    return fetchJson<ApprovedQuestionDTO[]>("/api/v1/questions/bank", undefined, "teacher");
  },
};

export interface ExamDetailDTO {
  exam_id: string;
  classroom_id: string;
  room_code: string;
  title: string;
  duration_s: number;
  status: string;
  question_count: number;
  shuffle_questions: boolean;
  shuffle_options: boolean;
  remaining_s: number;
  is_paused: boolean;
  start_at: string | null;
  deadline_at: string | null;
  closed_at: string | null;
  policy: Record<string, number>;
}

export interface CreateExamResponse {
  exam: ExamDetailDTO;
  invites: IssuedInviteResponse[];
}

export interface StudentPaperOptionDTO {
  option_id: string;
  display_label: string;
  blocks: ContentBlockDTO[];
}

export interface StudentPaperQuestionDTO {
  position: number;
  question_version_id: string;
  blocks: ContentBlockDTO[];
  options: StudentPaperOptionDTO[];
}

export interface SavedAnswerEntryDTO {
  selected_option_ids: string[];
  server_revision: number;
  committed_at: string;
}

export interface StudentPaperResponse {
  attempt_id: string;
  exam_id: string;
  exam_title: string;
  room_code: string;
  exam_status: string;
  attempt_state: string;
  presence_state?: string;
  extra_time_s?: number;
  heartbeat_s?: number;
  is_paused: boolean;
  remaining_s: number;
  server_time_utc: string;
  deadline_at: string | null;
  latest_revision: number;
  questions: StudentPaperQuestionDTO[];
  saved_answers: Record<string, SavedAnswerEntryDTO>;
}

export interface SaveAnswerAckResponse {
  status: string;
  attempt_id: string;
  question_version_id: string;
  selected_option_ids: string[];
  server_revision: number;
  idempotency_key: string;
  committed_at: string;
  duplicate: boolean;
}

export interface CanonicalSyncResponse {
  attempt_id: string;
  exam_id: string;
  exam_status: string;
  attempt_state: string;
  presence_state?: string;
  extra_time_s?: number;
  is_paused: boolean;
  remaining_s: number;
  server_time_utc: string;
  latest_revision: number;
  saved_answers: Record<string, SavedAnswerEntryDTO>;
  submitted_at: string | null;
  snapshot_hash: string | null;
  incident_reason?: string | null;
}

export interface SubmitAttemptResponse {
  submission_id: string;
  attempt_id: string;
  snapshot_hash: string;
  submitted_at: string;
  submission_mode: string;
  already_submitted: boolean;
}

export const examApi = {
  listExams(): Promise<ExamDetailDTO[]> {
    return fetchJson<ExamDetailDTO[]>("/api/v1/exams", undefined, "teacher");
  },
  getExam(examId: string): Promise<ExamDetailDTO> {
    return fetchJson<ExamDetailDTO>(`/api/v1/exams/${examId}`, undefined, "teacher");
  },
  createExam(payload: {
    classroom_id: string;
    title: string;
    duration_s: number;
    question_version_ids: string[];
    shuffle_questions: boolean;
    shuffle_options: boolean;
    policy?: Record<string, number>;
    open_waiting?: boolean;
  }): Promise<CreateExamResponse> {
    return fetchJson<CreateExamResponse>(
      "/api/v1/exams",
      { method: "POST", body: JSON.stringify(payload) },
      "teacher"
    );
  },
  startExam(examId: string): Promise<ExamDetailDTO> {
    return fetchJson<ExamDetailDTO>(`/api/v1/exams/${examId}/start`, { method: "POST" }, "teacher");
  },
  pauseExam(examId: string, reason: string): Promise<ExamDetailDTO> {
    return fetchJson<ExamDetailDTO>(
      `/api/v1/exams/${examId}/pause`,
      { method: "POST", body: JSON.stringify({ reason }) },
      "teacher"
    );
  },
  resumeExam(examId: string): Promise<ExamDetailDTO> {
    return fetchJson<ExamDetailDTO>(`/api/v1/exams/${examId}/resume`, { method: "POST" }, "teacher");
  },
  closeExam(examId: string, reason: string): Promise<ExamDetailDTO> {
    return fetchJson<ExamDetailDTO>(
      `/api/v1/exams/${examId}/close`,
      { method: "POST", body: JSON.stringify({ reason }) },
      "teacher"
    );
  },
};

export const studentExamApi = {
  getPaper(studentToken: string): Promise<StudentPaperResponse> {
    return fetchJson<StudentPaperResponse>("/api/v1/attempts/me/paper", undefined, "student", studentToken);
  },
  saveAnswer(
    studentToken: string,
    attemptId: string,
    payload: {
      question_version_id: string;
      selected_option_ids: string[];
      idempotency_key: string;
      client_timestamp: string;
    }
  ): Promise<SaveAnswerAckResponse> {
    return fetchJson<SaveAnswerAckResponse>(
      `/api/v1/attempts/${attemptId}/answers`,
      { method: "POST", body: JSON.stringify(payload) },
      "student",
      studentToken
    );
  },
  syncAttempt(studentToken: string, attemptId: string): Promise<CanonicalSyncResponse> {
    return fetchJson<CanonicalSyncResponse>(
      `/api/v1/attempts/${attemptId}/sync`,
      undefined,
      "student",
      studentToken
    );
  },
  submitAttempt(studentToken: string, attemptId: string): Promise<SubmitAttemptResponse> {
    return fetchJson<SubmitAttemptResponse>(
      `/api/v1/attempts/${attemptId}/submit`,
      { method: "POST" },
      "student",
      studentToken
    );
  },
  sendHeartbeat(studentToken: string, attemptId: string): Promise<Record<string, unknown>> {
    return fetchJson<Record<string, unknown>>(
      `/api/v1/attempts/${attemptId}/heartbeat`,
      { method: "POST" },
      "student",
      studentToken
    );
  },
  sendClientEvent(
    studentToken: string,
    attemptId: string,
    event_type: "APP_HIDDEN" | "PAGE_UNLOADED" | "NETWORK_LOST" | "CLIENT_RELOAD",
    details: Record<string, unknown> = {}
  ): Promise<{ event_id: string; event_type: string; server_time_utc: string }> {
    return fetchJson<{ event_id: string; event_type: string; server_time_utc: string }>(
      `/api/v1/attempts/${attemptId}/events`,
      { method: "POST", body: JSON.stringify({ event_type, details }) },
      "student",
      studentToken
    );
  },
  refreshToken(
    studentToken: string,
    attemptId: string
  ): Promise<{ attempt_token: string; expires_in_s: number }> {
    return fetchJson<{ attempt_token: string; expires_in_s: number }>(
      `/api/v1/attempts/${attemptId}/refresh-token`,
      { method: "POST" },
      "student",
      studentToken
    );
  },
};

export interface MonitoringPolicyDTO {
  heartbeat_s: number;
  suspected_s: number;
  disconnect_s: number;
  lock_after_s: number;
  grace_submit_s: number;
}

export interface MonitoringRosterEntryDTO {
  student_id: string;
  roster_code: string;
  full_name: string;
  attempt_id: string | null;
  attempt_state: string;
  presence_state: string;
  device_bound: boolean;
  latest_revision: number;
  answered_count: number;
  last_heartbeat_at: string | null;
  heartbeat_age_s: number | null;
  reconnect_count: number;
  hidden_event_count: number;
  extra_time_s: number;
  open_incident_id: string | null;
  open_incident_summary: string | null;
  submitted_at: string | null;
}

export interface IncidentDTO {
  id: string;
  attempt_id: string;
  roster_code: string;
  full_name: string;
  state: string;
  trigger_type: string;
  summary: string;
  opened_at: string;
}

export interface RoomMonitoringSnapshotDTO {
  exam_id: string;
  room_code: string;
  title: string;
  status: string;
  is_paused: boolean;
  remaining_s: number;
  question_count: number;
  server_time_utc: string;
  policy: MonitoringPolicyDTO;
  summary: {
    total_students: number;
    active_count: number;
    submitted_count: number;
    pending_count: number;
    suspected_count: number;
    disconnected_count: number;
    locked_count: number;
    open_incidents_count: number;
  };
  open_incidents: IncidentDTO[];
  roster: MonitoringRosterEntryDTO[];
}

export interface AttemptTimelineResponse {
  attempt_id: string;
  exam_id: string;
  roster_code: string;
  full_name: string;
  attempt_state: string;
  presence_state: string;
  extra_time_s: number;
  reconnect_count: number;
  hidden_event_count: number;
  events: {
    id: string;
    event_type: string;
    server_time: string;
    details: Record<string, unknown>;
  }[];
  incidents: {
    id: string;
    state: string;
    trigger_type: string;
    summary: string;
    opened_at: string;
    resolved_at: string | null;
    resolution_reason: string | null;
  }[];
}

export const monitoringApi = {
  getSnapshot(examId: string): Promise<RoomMonitoringSnapshotDTO> {
    return fetchJson<RoomMonitoringSnapshotDTO>(
      `/api/v1/monitoring/exams/${examId}`,
      undefined,
      "teacher"
    );
  },
  updatePolicy(examId: string, policy: MonitoringPolicyDTO): Promise<MonitoringPolicyDTO> {
    return fetchJson<MonitoringPolicyDTO>(
      `/api/v1/monitoring/exams/${examId}/policy`,
      { method: "PATCH", body: JSON.stringify(policy) },
      "teacher"
    );
  },
  getTimeline(examId: string, attemptId: string): Promise<AttemptTimelineResponse> {
    return fetchJson<AttemptTimelineResponse>(
      `/api/v1/monitoring/exams/${examId}/attempts/${attemptId}/timeline`,
      undefined,
      "teacher"
    );
  },
  lockAttempt(
    examId: string,
    attemptId: string,
    reason: string
  ): Promise<{ attempt_id: string; attempt_state: string; incident_id: string }> {
    return fetchJson<{ attempt_id: string; attempt_state: string; incident_id: string }>(
      `/api/v1/monitoring/exams/${examId}/attempts/${attemptId}/lock`,
      { method: "POST", body: JSON.stringify({ reason }) },
      "teacher"
    );
  },
  resolveIncident(
    examId: string,
    attemptId: string,
    payload: { action: "unlock" | "extend_time" | "terminate"; reason: string; extend_minutes?: number }
  ): Promise<{ attempt_id: string; attempt_state: string; extra_time_s: number }> {
    return fetchJson<{ attempt_id: string; attempt_state: string; extra_time_s: number }>(
      `/api/v1/monitoring/exams/${examId}/attempts/${attemptId}/resolve`,
      { method: "POST", body: JSON.stringify(payload) },
      "teacher"
    );
  },
};

export interface BackupManifestDTO {
  id: string;
  created_at: string;
  schema_version: string;
  sha256: string;
  location: string;
  record_counts: Record<string, number>;
  verified_at: string | null;
}

export interface VerifyBackupResponse {
  manifest_id: string | null;
  archive_name: string;
  schema_version: string;
  checksum_valid: boolean;
  sqlite_integrity_ok: boolean;
  record_counts: Record<string, number>;
  dry_run: boolean;
}

export const backupApi = {
  listBackups(): Promise<BackupManifestDTO[]> {
    return fetchJson<BackupManifestDTO[]>("/api/v1/system/backups", undefined, "teacher");
  },
  createBackup(): Promise<BackupManifestDTO> {
    return fetchJson<BackupManifestDTO>("/api/v1/system/backups", { method: "POST" }, "teacher");
  },
  verifyBackupDryRun(backupId: string): Promise<VerifyBackupResponse> {
    return fetchJson<VerifyBackupResponse>(
      `/api/v1/system/backups/${backupId}/verify`,
      { method: "POST" },
      "teacher"
    );
  },
};
