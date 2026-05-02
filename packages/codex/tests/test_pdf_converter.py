"""PDF converter tests — uses subprocess; we monkeypatch to avoid LibreOffice dep."""

import subprocess
from pathlib import Path

import pytest


def test_pptx_to_pdf_invokes_libreoffice(monkeypatch, tmp_path):
    from codex_brain.generators import pdf_converter

    captured: dict = {}

    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        captured["timeout"] = kw.get("timeout")
        # Simulate libreoffice writing the pdf
        out_dir = Path(cmd[cmd.index("--outdir") + 1])
        pptx = Path(cmd[-1] if "--outdir" not in cmd else cmd[cmd.index("--outdir") - 1])
        pdf_out = out_dir / (pptx.stem + ".pdf")
        pdf_out.write_bytes(b"%PDF-1.4 fake\n%%EOF\n")

        class _R:
            returncode = 0
            stdout = b""
            stderr = b""
        return _R()

    monkeypatch.setattr(subprocess, "run", fake_run)

    pptx = tmp_path / "deck.pptx"
    pptx.write_bytes(b"fake")
    result = pdf_converter.pptx_to_pdf(pptx, out_dir=tmp_path)
    assert result.exists()
    assert result.suffix == ".pdf"
    assert captured["timeout"] is not None
    assert captured["timeout"] <= 60
    assert "libreoffice" in captured["cmd"][0] or captured["cmd"][0].endswith("libreoffice")
    assert "--headless" in captured["cmd"]
    assert "--convert-to" in captured["cmd"]
    assert "pdf" in captured["cmd"]


def test_pptx_to_pdf_raises_on_failure(monkeypatch, tmp_path):
    from codex_brain.generators import pdf_converter

    def fake_run(cmd, **kw):
        class _R:
            returncode = 1
            stdout = b"err"
            stderr = b"libreoffice exploded"
        return _R()

    monkeypatch.setattr(subprocess, "run", fake_run)
    pptx = tmp_path / "bad.pptx"
    pptx.write_bytes(b"fake")
    with pytest.raises(RuntimeError):
        pdf_converter.pptx_to_pdf(pptx, out_dir=tmp_path)
