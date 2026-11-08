# Next Actions

1. Tạo Alembic migration `0004_exam_engine_and_answers.py` và ORM models cho `Exam` (mở rộng), `ExamQuestion`, `ExamPermutation`, `AnswerRevision`, `Submission`, `BackupManifest`.
2. Xây dựng `exam_service.py` (state machine + deterministic permutation + server timer/pause/resume + zero answer_key leak), `answer_service.py` (commit-before-ACK idempotent revision + atomic submission), `backup_service.py` (SQLite backup + checksum + restore dry-run).
3. Triển khai API `/api/v1/exams/*`, `/api/v1/attempts/me/*`, `/api/v1/system/backups/*` và kiểm thử concurrent race + server restart persistence.
4. Xây dựng UI `ExamConfigPage.tsx` (`T4`), nâng cấp `WaitingRoomPage.tsx`, xây `StudentExamPage.tsx` (`S4/S6`) có hàng đợi pending local khi rớt Wi-Fi, trạng thái đồng bộ trung thực và Backup UI (`T9`).