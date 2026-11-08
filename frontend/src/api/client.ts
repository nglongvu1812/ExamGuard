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
  importFile(file: File, profile: string = "auto"): Promise<ImportJobResponse> {
    const form = new FormData();
    form.append("file", file);
    form.append("profile", profile);
    return fetchJson<ImportJobResponse>(
      "/api/v1/questions/import",
      { method: "POST", body: form },
      "teacher"
    );
  },
  importDocx(file: File): Promise<ImportJobResponse> {
    return questionApi.importFile(file, "auto");
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
  getActiveExam(): Promise<ExamDetailDTO | null> {
    return fetchJson<ExamDetailDTO | null>("/api/v1/exams/active", undefined, "teacher");
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
  cancelExam(examId: string, reason: string): Promise<ExamDetailDTO> {
    return fetchJson<ExamDetailDTO>(
      `/api/v1/exams/${examId}/cancel`,
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

async function fetchAuthenticatedBlob(
  url: string,
  authMode: "teacher" | "student",
  studentToken?: string
): Promise<{ blob: Blob; filename: string | null }> {
  const headers = new Headers();
  if (authMode === "teacher") {
    const token = await ensureTeacherToken();
    headers.set("Authorization", `Bearer ${token}`);
  } else if (authMode === "student" && studentToken) {
    headers.set("Authorization", `Bearer ${studentToken}`);
  }

  let response = await fetch(url, { headers });
  if (response.status === 401 && authMode === "teacher") {
    cachedTeacherToken = null;
    const retryToken = await ensureTeacherToken();
    headers.set("Authorization", `Bearer ${retryToken}`);
    response = await fetch(url, { headers });
  }

  if (!response.ok) {
    let detail = `Lỗi tải tệp (${response.status})`;
    try {
      const data = (await response.json()) as { detail?: string };
      if (data.detail) detail = data.detail;
    } catch {
      // ignore non-json body
    }
    throw new Error(detail);
  }

  const cd = response.headers.get("Content-Disposition") ?? "";
  const match = cd.match(/filename="?([^"]+)"?/i);
  const blob = await response.blob();
  return { blob, filename: match?.[1] ?? null };
}

export interface ExamResultsStatsDTO {
  total_students: number;
  graded_count: number;
  unsubmitted_count: number;
  mean_score: number;
  median_score: number;
  max_score: number;
  min_score: number;
  bins: {
    excellent: number;
    good: number;
    average: number;
    below_average: number;
  };
}

export interface TeacherStudentGradeRowDTO {
  student_id: string;
  roster_code: string;
  full_name: string;
  attempt_id: string | null;
  attempt_state: string;
  status_label: string;
  submission_id: string | null;
  submitted_at: string | null;
  snapshot_hash: string | null;
  raw_correct: number | null;
  total_questions: number | null;
  earned_points: number | null;
  max_points: number | null;
  score_10: number | null;
  score_version: number;
  regrade_count: number;
  receipt_code: string | null;
  receipt_version: number;
  open_incidents: number;
}

export interface GradeRunSummaryDTO {
  id: string;
  run_number: number;
  code_version: string;
  reason: string;
  created_at: string;
}

export interface ExamQuestionKeyDTO {
  position: number;
  question_version_id: string;
  weight: number;
  blocks: ContentBlockDTO[];
  options: OptionDraftDTO[];
  correct_option_ids: string[];
  key_version_number: number;
  key_history: {
    id: string;
    version_number: number;
    correct_option_ids: string[];
    reason: string;
    approved_at: string;
  }[];
}

export interface TeacherResultsOverviewDTO {
  exam: {
    exam_id: string;
    classroom_id: string;
    classroom_name: string;
    room_code: string;
    title: string;
    status: string;
    closed_at: string | null;
    reviewed_at: string | null;
    published_at: string | null;
    unresolved_attempts: number;
    question_count: number;
  };
  stats: ExamResultsStatsDTO;
  students: TeacherStudentGradeRowDTO[];
  grade_runs: GradeRunSummaryDTO[];
  questions: ExamQuestionKeyDTO[];
}

export interface StudentPhucKhaoTraceDTO {
  exam: {
    exam_id: string;
    room_code: string;
    title: string;
    status: string;
    seed: number;
  };
  student: {
    student_id: string;
    roster_code: string;
    full_name: string;
  };
  attempt: {
    attempt_id: string;
    state: string;
    started_at: string | null;
    submitted_at: string | null;
    latest_revision: number;
    reconnect_count: number;
    hidden_event_count: number;
    extra_time_s: number;
  } | null;
  submission: {
    submission_id: string;
    submission_mode: string;
    snapshot_hash: string;
    submitted_at: string;
    answer_snapshot: Record<string, string[]>;
  } | null;
  permutation_seed: number | null;
  questions: {
    seen_position: number;
    question_version_id: string;
    blocks: ContentBlockDTO[];
    options: {
      option_id: string;
      seen_label: string;
      original_label: string;
      blocks: ContentBlockDTO[];
      selected: boolean;
      is_correct_option: boolean;
    }[];
    selected_option_ids: string[];
    correct_option_ids: string[];
    key_version_number: number;
    is_correct: boolean;
  }[];
  answer_revisions: {
    revision: number;
    question_version_id: string;
    selected_option_ids: string[];
    idempotency_key: string;
    committed_at: string;
  }[];
  score_versions: {
    id: string;
    version: number;
    score_10: number;
    raw_correct: number;
    total_questions: number;
    earned_points: number;
    max_points: number;
    reason: string;
    supersedes_id: string | null;
    is_current: boolean;
    created_at: string;
  }[];
  receipt_versions: {
    id: string;
    receipt_code: string;
    version: number;
    document_sha256: string;
    supersedes_id: string | null;
    is_current: boolean;
    published_at: string;
  }[];
  presence_events: {
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
  audit_events: {
    id: number;
    actor_type: string;
    actor_id: string;
    action: string;
    target_type: string;
    target_id: string;
    before_hash: string;
    after_hash: string;
    event_hash: string;
    created_at: string;
    details: Record<string, unknown>;
  }[];
}

export interface AuditVerifyResponse {
  valid: boolean;
  event_count: number;
  broken_event_id: number | null;
  limitation_note: string;
  recent_events: {
    id: number;
    actor_type: string;
    actor_id: string;
    action: string;
    target_type: string;
    target_id: string;
    before_hash: string;
    after_hash: string;
    event_hash: string;
    created_at: string;
    details: Record<string, unknown>;
  }[];
}

export interface StudentPublishedResultDTO {
  exam_id: string;
  exam_title: string;
  room_code: string;
  exam_status: string;
  attempt_id: string;
  student_name: string;
  roster_code: string;
  score_10: number;
  raw_correct: number;
  total_questions: number;
  earned_points: number;
  max_points: number;
  score_version: number;
  regrade_reason: string | null;
  receipt_code: string;
  receipt_version: number;
  superseded_previous: boolean;
  document_sha256: string;
  snapshot_hash: string;
  submitted_at: string;
  published_at: string | null;
  questions: {
    position: number;
    question_version_id: string;
    blocks: ContentBlockDTO[];
    options: StudentPaperOptionDTO[];
    selected_option_ids: string[];
    correct_option_ids: string[];
    is_correct: boolean;
    earned_points: number;
    weight: number;
  }[];
}

export const resultsApi = {
  getExamResults(examId: string): Promise<TeacherResultsOverviewDTO> {
    return fetchJson<TeacherResultsOverviewDTO>(
      `/api/v1/results/exams/${examId}`,
      undefined,
      "teacher"
    );
  },
  gradeOrRegrade(
    examId: string,
    payload: { reason: string; updated_keys?: Record<string, string[]> }
  ): Promise<{
    grade_run_id: string;
    run_number: number;
    scored_count: number;
    receipts_updated: number;
    reason: string;
  }> {
    return fetchJson(
      `/api/v1/results/exams/${examId}/grade`,
      { method: "POST", body: JSON.stringify(payload) },
      "teacher"
    );
  },
  reviewExam(
    examId: string,
    reason: string
  ): Promise<{ exam_id: string; status: string; reviewed_at: string | null }> {
    return fetchJson(
      `/api/v1/results/exams/${examId}/review`,
      { method: "POST", body: JSON.stringify({ reason }) },
      "teacher"
    );
  },
  publishExam(
    examId: string
  ): Promise<{
    exam_id: string;
    status: string;
    published_at: string | null;
    receipts_issued: number;
  }> {
    return fetchJson(
      `/api/v1/results/exams/${examId}/publish`,
      { method: "POST", body: JSON.stringify({ confirm: true }) },
      "teacher"
    );
  },
  downloadExcel(examId: string): Promise<{ blob: Blob; filename: string | null }> {
    return fetchAuthenticatedBlob(`/api/v1/results/exams/${examId}/export.xlsx`, "teacher");
  },
  getStudentTrace(examId: string, studentId: string): Promise<StudentPhucKhaoTraceDTO> {
    return fetchJson<StudentPhucKhaoTraceDTO>(
      `/api/v1/results/exams/${examId}/students/${studentId}/trace`,
      undefined,
      "teacher"
    );
  },
};

export const auditApi = {
  verifyChain(): Promise<AuditVerifyResponse> {
    return fetchJson<AuditVerifyResponse>("/api/v1/audit/verify", undefined, "teacher");
  },
};

export const studentResultApi = {
  getMyResult(studentToken: string): Promise<StudentPublishedResultDTO> {
    return fetchJson<StudentPublishedResultDTO>(
      "/api/v1/attempts/me/result",
      undefined,
      "student",
      studentToken
    );
  },
  downloadReceiptPdf(studentToken: string): Promise<{ blob: Blob; filename: string | null }> {
    return fetchAuthenticatedBlob("/api/v1/attempts/me/receipt.pdf", "student", studentToken);
  },
  downloadShareCardPng(studentToken: string): Promise<{ blob: Blob; filename: string | null }> {
    return fetchAuthenticatedBlob("/api/v1/attempts/me/share-card.png", "student", studentToken);
  },
};

export interface PaperVersionDTO {
  id: string;
  version_code: string;
  question_count: number;
  answer_key_map: Record<string, string[]>;
  created_at: string;
}

export interface OmrScanSubmissionDTO {
  scan_id: string;
  exam_id: string;
  student_id: string | null;
  student_name: string | null;
  roster_code: string | null;
  paper_version_id: string | null;
  version_code: string | null;
  roster_code_detected: string;
  version_code_detected: string;
  source_sha256: string;
  detected_answers: Record<string, string | null>;
  confirmed_answers: Record<string, string | null>;
  confidence: {
    fiducial_found?: boolean;
    questions?: Record<
      string,
      { status: string; confidence: number; scores?: Record<string, number> }
    >;
  };
  ambiguous_flags: string[];
  overall_confidence: number;
  status: "NEEDS_REVIEW" | "CONFIRMED";
  linked_submission_id: string | null;
  confirmed_at: string | null;
  reason: string;
  created_at: string;
}

export const paperApi = {
  generateVersions(
    examId: string,
    count: number = 4,
    start_code: number = 101
  ): Promise<{ exam_id: string; versions: PaperVersionDTO[] }> {
    return fetchJson(
      `/api/v1/paper/exams/${examId}/versions`,
      { method: "POST", body: JSON.stringify({ count, start_code }) },
      "teacher"
    );
  },
  listVersions(examId: string): Promise<{ exam_id: string; versions: PaperVersionDTO[] }> {
    return fetchJson(`/api/v1/paper/exams/${examId}/versions`, undefined, "teacher");
  },
  downloadBookletPdf(examId: string): Promise<{ blob: Blob; filename: string | null }> {
    return fetchAuthenticatedBlob(`/api/v1/paper/exams/${examId}/booklet.pdf`, "teacher");
  },
  downloadOmrSheet(
    examId: string,
    fmt: "pdf" | "png" = "pdf"
  ): Promise<{ blob: Blob; filename: string | null }> {
    return fetchAuthenticatedBlob(
      `/api/v1/paper/exams/${examId}/omr-sheet.pdf?fmt=${fmt}`,
      "teacher"
    );
  },
  uploadScan(examId: string, file: File): Promise<OmrScanSubmissionDTO> {
    const form = new FormData();
    form.append("file", file);
    return fetchJson<OmrScanSubmissionDTO>(
      `/api/v1/paper/exams/${examId}/scans`,
      { method: "POST", body: form },
      "teacher"
    );
  },
  listScans(examId: string): Promise<OmrScanSubmissionDTO[]> {
    return fetchJson<OmrScanSubmissionDTO[]>(
      `/api/v1/paper/exams/${examId}/scans`,
      undefined,
      "teacher"
    );
  },
  fetchScanImage(scanId: string, aligned: boolean = false): Promise<Blob> {
    return fetchAuthenticatedBlob(
      `/api/v1/paper/scans/${scanId}/image?aligned=${aligned ? "true" : "false"}`,
      "teacher"
    ).then((res) => res.blob);
  },
  confirmScan(
    scanId: string,
    payload: {
      student_id: string;
      version_code: string;
      confirmed_answers: Record<string, string | null>;
      reason: string;
    }
  ): Promise<OmrScanSubmissionDTO & { submission_id: string; regraded: boolean }> {
    return fetchJson(
      `/api/v1/paper/scans/${scanId}/confirm`,
      { method: "POST", body: JSON.stringify(payload) },
      "teacher"
    );
  },
};
