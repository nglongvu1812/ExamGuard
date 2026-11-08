# Data Model và bất biến dữ liệu

## 1. Bounded contexts

- `Roster`: TeacherProfile, Classroom, Student, ClassMembership.
- `Content`: SourceDocument, ImportJob, QuestionDraft, QuestionVersion, Asset, AnswerKeyVersion.
- `Exam`: Exam, ExamQuestion, ExamPermutation, Room, StudentInvite, Attempt, AnswerRevision, Submission.
- `Monitoring`: PresenceEvent, Incident, TeacherAction, DeviceBinding.
- `Grading`: RubricVersion, GradeRun, ScoreVersion, ReceiptVersion.
- `Audit`: AuditEvent, ExternalAnchor (future), BackupManifest.

## 2. Bảng khởi tạo tối thiểu

| Table | Columns quan trọng | Constraint/invariant |
| --- | --- | --- |
| `teacher_profiles` | id, display_name, settings_json | local profile; sau này nhiều teacher chỉ nếu thiết kế riêng |
| `classrooms` | id, teacher_id, name, academic_year, archived_at | soft-delete, unique teacher/year/name |
| `students` | id UUID, roster_code, name, metadata | stable ID, không reuse roster_code trong scope |
| `class_memberships` | classroom_id, student_id, active_from/to | lịch sử chuyển lớp, không sửa điểm cũ |
| `source_documents` | id, sha256, relpath, MIME, uploaded_at | immutable source; relative path sanitized |
| `import_jobs` | id, document_id, status, parser_version, error_json | resumable, fail report |
| `questions` | id, bank_id, active_version_id | stable logical ID |
| `question_versions` | id, question_id, content_blocks_json, option_ids, provenance, approved_at | immutable after approved |
| `answer_key_versions` | id, question_version_ids, key_mapping, approved_by, approved_at | never modify after use |
| `assets` | id digest, MIME, bytes, relpath | content-addressed; no external URL |
| `exams` | id, classroom_id, title, duration_s, status, start_at, deadline_at, policy_version | lifecycle constrained |
| `exam_questions` | exam_id, question_version_id, weight, position | frozen when READY |
| `exam_permutations` | exam_id, student_id, seed, question_order, option_order | frozen mapping, unique per student |
| `student_invites` | exam_id, student_id, code_hash, issued_at, used_at, revoked_at | random code/expiry, not plaintext |
| `attempts` | id, exam_id, student_id, session_id, state, last_seen, latest_revision | unique active attempt per (exam, student) |
| `device_bindings` | exam_id, attempt_id, device_public_key_or_token_hash, revoked_at | browser-scope best effort; optional signals |
| `answer_revisions` | id, attempt_id, question_version_id, selected_option_ids, revision, idempotency_key, committed_at | unique attempt/idempotency; monotonic revision |
| `submissions` | id, attempt_id, answer_snapshot_json, snapshot_hash, submitted_at | immutable once submitted, one per attempt |
| `presence_events` | id, attempt_id, event_type, server_time, details | event evidence, no disciplinary inference |
| `incidents` | id, attempt_id, state, opened_at, resolved_at, resolution_reason | teacher review |
| `grade_runs` | id, exam_id, key_version_id, rubric_version_id, code_version, created_at | pure scoring provenance |
| `score_versions` | id, submission_id, grade_run_id, score, version, reason, supersedes_id | immutable version record |
| `receipt_versions` | id, score_version_id, document_sha256, published_at, supersedes_id | only after publish |
| `audit_events` | id, actor_type, actor_id, action, target_type/id, before_hash, after_hash, prev_hash, event_hash, created_at | append only in app, hash chain |
| `backup_manifests` | id, created_at, schema_version, sha256, location | verify restore |

## 3. CSDL và concurrency

SQLite WAL cho nhiều readers, một writer; giữ transaction ngắn, busy timeout, retry bounded, tránh long-running OCR trong transaction. Background jobs không giữ DB connection lâu. Mọi answer ACK sau COMMIT. Unique constraints và serialized transition chống double submit, duplicate join, race open/close. Migrations Alembic có downgrade khi hợp lý nhưng không xoá dữ liệu production; backup trước upgrade.

## 4. Phân quyền và dữ liệu JSON

- `teacher`: local admin; server bảo vệ credential của teacher session, chỉ bind trusted loopback hoặc authenticate đúng.
- `student`: token scope `attempt_id` + expiration. Student GET chỉ lọc theo authenticated student; không dùng ID từ query làm quyền.
- Dữ liệu ContentBlock là tagged union strict validation. Không render arbitrary HTML; sanitize MathML/LaTeX/Markdown; CSP local assets only.

## 5. Dữ liệu chấm và minh bạch

`Submission` snapshot là bằng chứng về đáp án server nhận, không phải bằng chứng ai cầm điện thoại. `GradeRun` lưu code version/algorithm/key; `ScoreVersion` chỉ append. Sửa key ảnh hưởng tất cả attempt liên quan phải tạo run mới, không overwrite. Event hash chain giúp phát hiện sửa thiếu đồng bộ, **không thể chống đối thủ có quyền viết mọi file và tính lại chain**; muốn đối chứng độc lập cần lưu hash tại nơi thứ hai/chữ ký với key riêng.

## 6. Dữ liệu nhạy cảm

Chỉ lưu trường roster tối thiểu (mã, tên, lớp). Không yêu cầu CCCD, số điện thoại, email học sinh, tọa độ, camera, microphone, sinh trắc học. User data khi backup có mã hóa tùy chọn và mật khẩu được giáo viên tự lưu. Log phải redact key và token. Mẫu test luôn dữ liệu giả.

## 7. Di trú và export

Export Excel phải không thể bị formula injection (`=`, `+`, `-`, `@` ở cell nhập user). Filename sanitize; CSV UTF-8 BOM nếu cần; PDF embedded font. `BackupManifest` lưu source hashes, schema version, record counts, tested checksum; restore có dry-run và bản sao dự phòng.
