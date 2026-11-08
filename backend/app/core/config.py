"""ExamGuard core configuration using Pydantic v2 Settings."""

import sys
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _default_data_dir() -> Path:
    """Resolve ExamGuardData beside the frozen executable or current workspace."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "ExamGuardData"
    return Path.cwd() / "ExamGuardData"


class Settings(BaseSettings):
    """Application settings loaded from environment or .env (never commit secrets)."""

    model_config = SettingsConfigDict(
        env_prefix="EXAMGUARD_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "ExamGuard"
    app_version: str = "0.1.0"
    host: str = "0.0.0.0"
    port: int = 8000
    data_dir: Path = Field(default_factory=_default_data_dir)
    log_level: str = "INFO"
    sqlite_busy_timeout_ms: int = 5000
    static_dir: Path | None = None
    allow_lan_teacher_console: bool = False

    @property
    def db_path(self) -> Path:
        return self.data_dir / "examguard.db"

    @property
    def assets_dir(self) -> Path:
        return self.data_dir / "assets"

    @property
    def sources_dir(self) -> Path:
        return self.data_dir / "sources"

    @property
    def backups_dir(self) -> Path:
        return self.data_dir / "backups"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def receipts_dir(self) -> Path:
        return self.data_dir / "receipts"

    @property
    def paper_dir(self) -> Path:
        return self.data_dir / "paper"

    @property
    def scans_dir(self) -> Path:
        return self.data_dir / "scans"

    @property
    def database_url(self) -> str:
        return f"sqlite:///{self.db_path.as_posix()}"

    def ensure_data_dirs(self) -> None:
        """Create required data directories and verify write permission explicitly."""
        try:
            for directory in (
                self.data_dir,
                self.assets_dir,
                self.sources_dir,
                self.backups_dir,
                self.logs_dir,
                self.receipts_dir,
                self.paper_dir,
                self.scans_dir,
            ):
                directory.mkdir(parents=True, exist_ok=True)
            probe = self.data_dir / ".write_probe"
            probe.write_text("ok", encoding="utf-8")
            probe.unlink(missing_ok=True)
        except OSError as exc:
            raise PermissionError(
                f"Thư mục dữ liệu '{self.data_dir}' không có quyền ghi hoặc đầy dung lượng. "
                "Vui lòng chọn thư mục khác có quyền ghi hoặc kiểm tra dung lượng ổ đĩa."
            ) from exc


def get_settings() -> Settings:
    return Settings()
