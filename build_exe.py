"""
build_exe.py — One-command PyInstaller build script for Comau Sim-Sequence Studio.

Usage:
    python build_exe.py

Output:
    dist/SimSequenceStudio.exe   ← single-file standalone executable

Requirements:
    pip install pyinstaller pillow
"""

from __future__ import annotations

import os
import sys
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.resolve()
DIST_DIR = ROOT / "dist"
BUILD_DIR = ROOT / "build"
LOGO_PNG = ROOT / "resources" / "Logo-COMAU.png"
LOGO_ICO = ROOT / "resources" / "Logo-COMAU.ico"
APP_NAME = "SimSequenceStudio"


def _make_icon():
    """Convert Logo-COMAU.png → Logo-COMAU.ico (multi-size) if not already done."""
    if LOGO_ICO.exists():
        return str(LOGO_ICO)
    if not LOGO_PNG.exists():
        print("[build] No logo found — skipping icon conversion.")
        return None
    try:
        from PIL import Image
        img = Image.open(LOGO_PNG).convert("RGBA")
        sizes = [(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)]
        icon_frames = [img.resize(s, Image.LANCZOS) for s in sizes]
        icon_frames[0].save(
            str(LOGO_ICO),
            format="ICO",
            sizes=sizes,
            append_images=icon_frames[1:],
        )
        print(f"[build] Icon created: {LOGO_ICO}")
        return str(LOGO_ICO)
    except Exception as exc:
        print(f"[build] Icon conversion failed ({exc}), using PNG fallback.")
        return str(LOGO_PNG)


def _run_pyinstaller(icon_path: str | None):
    """Invoke PyInstaller as a subprocess."""
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--onefile",
        "--windowed",
        "--name", APP_NAME,
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(ROOT),
        # Data files bundled into the exe
        "--add-data", f"{ROOT / 'resources' / 'Logo-COMAU.png'}{os.pathsep}resources",
        "--add-data", f"{ROOT / 'inputs' / 'sample_weld_sequence.cseq'}{os.pathsep}inputs",
        # Hidden imports PyInstaller may miss
        "--hidden-import", "PyQt6.sip",
        "--hidden-import", "networkx.algorithms",
        "--hidden-import", "networkx.classes",
        "--hidden-import", "networkx.generators",
        "--hidden-import", "yaml",
        # Strip unused heavy libs
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "scipy",
        "--exclude-module", "numpy",
        "--exclude-module", "IPython",
    ]
    if icon_path:
        cmd += ["--icon", icon_path]

    cmd.append(str(ROOT / "studio_app.py"))

    print("[build] Running PyInstaller…")
    print("  " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(ROOT))
    return result.returncode


def _write_register_script():
    """Write a Windows .reg file to associate .cseq with the built exe."""
    exe_path = DIST_DIR / f"{APP_NAME}.exe"
    # Escape backslashes for .reg format
    exe_str = str(exe_path).replace("\\", "\\\\")

    reg_content = f"""Windows Registry Editor Version 5.00

; Associate .cseq files with Comau Sim-Sequence Studio
; Double-click any .cseq file to open it directly in the studio.
;
; Instructions:
;   1. Build the exe first: python build_exe.py
;   2. Double-click register_cseq.reg and confirm the UAC prompt.

[HKEY_CLASSES_ROOT\\.cseq]
@="ComauSimSequence"
"Content Type"="application/x-comau-sequence"

[HKEY_CLASSES_ROOT\\ComauSimSequence]
@="Comau Sequence File"

[HKEY_CLASSES_ROOT\\ComauSimSequence\\DefaultIcon]
@="{exe_str},0"

[HKEY_CLASSES_ROOT\\ComauSimSequence\\shell\\open\\command]
@="\\"{exe_str}\\" \\"%1\\""

[HKEY_CLASSES_ROOT\\ComauSimSequence\\shell\\open]
@="Open in Sim-Sequence Studio"
"Icon"="{exe_str},0"
"""
    reg_path = ROOT / "register_cseq.reg"
    reg_path.write_text(reg_content, encoding="utf-8")
    print(f"[build] File association registry script written: {reg_path}")
    return reg_path


def main():
    print(f"[build] Comau Sim-Sequence Studio — Build Script")
    print(f"[build] Root: {ROOT}")
    print()

    icon_path = _make_icon()
    rc = _run_pyinstaller(icon_path)

    if rc != 0:
        print(f"\n[build] ❌ PyInstaller exited with code {rc}.")
        sys.exit(rc)

    exe = DIST_DIR / f"{APP_NAME}.exe"
    if exe.exists():
        size_mb = exe.stat().st_size / 1_048_576
        print(f"\n[build] ✅ Build complete!")
        print(f"[build]    Executable : {exe}")
        print(f"[build]    Size       : {size_mb:.1f} MB")
    else:
        print(f"\n[build] ⚠  Executable not found at expected path: {exe}")

    reg_path = _write_register_script()
    print()
    print("[build] Next steps:")
    print(f"  1. Run the app:              {exe}")
    print(f"  2. Register .cseq extension: double-click {reg_path}")
    print()


if __name__ == "__main__":
    main()
