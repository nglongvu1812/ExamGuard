# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller onedir build spec for ExamGuard Windows Portable."""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND_DIST = ROOT / "frontend" / "dist"
ICON_PATH = ROOT / "frontend" / "public" / "favicon.ico"

hiddenimports = [
    *collect_submodules("app"),
    *collect_submodules("alembic"),
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.http.httptools_impl",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.protocols.websockets.websockets_impl",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "websockets",
    "sqlalchemy.dialects.sqlite",
    "multipart",
    "python_multipart",
]

datas = [
    (str(FRONTEND_DIST), "frontend/dist"),
    (str(BACKEND / "alembic.ini"), "."),
    (str(BACKEND / "alembic"), "alembic"),
    (str(BACKEND / "app" / "assets" / "fonts"), "app/assets/fonts"),
]

excludes = [
    "tkinter",
    "_tkinter",
    "pytest",
    "ruff",
    "mypy",
    "matplotlib",
    "IPython",
    "scipy",
]

a = Analysis(
    [str(ROOT / "desktop" / "launcher.py")],
    pathex=[str(ROOT), str(BACKEND)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="ExamGuard",
    icon=str(ICON_PATH) if ICON_PATH.exists() else None,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="ExamGuard",
)
