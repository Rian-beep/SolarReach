"""PPTX → PDF via headless LibreOffice.

The Dockerfile installs `libreoffice` so the binary is on PATH. Locally a dev
without LibreOffice will see a clear RuntimeError.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


LIBREOFFICE_TIMEOUT_S = 60  # spec: ≤ 60s


def _resolve_libreoffice_bin() -> str:
    for candidate in ("libreoffice", "soffice"):
        path = shutil.which(candidate)
        if path:
            return path
    # macOS app bundle fallback for local dev
    mac = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if Path(mac).exists():
        return mac
    return "libreoffice"  # let subprocess.run fail naturally with a clear message


def pptx_to_pdf(pptx_path: Path | str, out_dir: Path | str | None = None) -> Path:
    pptx_path = Path(pptx_path)
    if not pptx_path.exists():
        raise FileNotFoundError(f"pptx not found: {pptx_path}")
    out_dir = Path(out_dir) if out_dir is not None else pptx_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    bin_ = _resolve_libreoffice_bin()
    cmd = [
        bin_,
        "--headless",
        "--convert-to",
        "pdf",
        str(pptx_path),
        "--outdir",
        str(out_dir),
    ]
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=LIBREOFFICE_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(
            f"LibreOffice conversion timed out after {LIBREOFFICE_TIMEOUT_S}s for {pptx_path.name}"
        ) from exc
    except FileNotFoundError as exc:
        raise RuntimeError(
            "LibreOffice not found on PATH. Install via apt-get or brew, "
            "or run inside the codex Dockerfile."
        ) from exc

    if result.returncode != 0:
        stderr = (result.stderr or b"").decode("utf-8", errors="replace")[:1000]
        raise RuntimeError(f"LibreOffice conversion failed: {stderr}")

    pdf_path = out_dir / (pptx_path.stem + ".pdf")
    if not pdf_path.exists():
        raise RuntimeError(f"LibreOffice claimed success but PDF missing at {pdf_path}")
    return pdf_path
