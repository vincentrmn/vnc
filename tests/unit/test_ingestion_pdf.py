"""Tests ingestion PDF vectoriel → géométrie (déterministe, zéro vision).

On fabrique un PDF vectoriel (lignes + textes réels) avec PyMuPDF, on le parse,
et on vérifie l'extraction des vecteurs et la reconstruction des pièces depuis
les libellés. Un PDF scanné (image seule) doit être refusé.
"""

from __future__ import annotations

from pathlib import Path

import pytest

fitz = pytest.importorskip("fitz")  # PyMuPDF (extra pdf)
pytest.importorskip("shapely")  # build_building (extra cao)

from zephyr.geometry import build_building  # noqa: E402
from zephyr.ingestion import parse_cpe, parse_pdf  # noqa: E402


def _make_vector_pdf(path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    page.draw_line((10, 10), (200, 10))
    page.draw_line((200, 10), (200, 200))
    page.insert_text((50, 60), "Bedroom 15.10 m2")
    page.insert_text((50, 120), "Kitchen 12.0 m2")
    doc.save(str(path))


def test_parse_pdf_extracts_vectors_and_text(tmp_path: Path) -> None:
    p = tmp_path / "plan.pdf"
    _make_vector_pdf(p)
    raw = parse_pdf(p)
    assert raw.lines  # segments vectoriels extraits
    assert any("Bedroom" in t.text for t in raw.texts)  # texte réel lisible


def test_pdf_rooms_from_labels(tmp_path: Path) -> None:
    p = tmp_path / "plan.pdf"
    _make_vector_pdf(p)
    b = build_building(parse_pdf(p)).building
    labels = {r.label.value for r in b.rooms}
    assert "chambre" in labels and "cuisine" in labels
    areas = sorted(round(r.area_m2, 1) for r in b.rooms)
    assert 15.1 in areas and 12.0 in areas


def test_parse_cpe_extracts_text(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=400)
    page.insert_text((40, 60), "Coefficient U mur 0,18 W/(m2.K)")
    page.insert_text((40, 90), "n50 = 1,5 1/h")
    p = tmp_path / "cpe.pdf"
    doc.save(str(p))
    cpe = parse_cpe(p)
    assert "n50" in cpe.text and "0,18" in cpe.text
    assert len(cpe.pages) == 1


def test_parse_cpe_rejects_scan(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60))
    pix.clear_with(220)
    page.insert_image(fitz.Rect(0, 0, 60, 60), pixmap=pix)
    p = tmp_path / "scan_cpe.pdf"
    doc.save(str(p))
    with pytest.raises(ValueError, match="scanné"):
        parse_cpe(p)


def test_parse_pdf_rejects_scan(tmp_path: Path) -> None:
    doc = fitz.open()
    page = doc.new_page(width=100, height=100)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 60, 60))
    pix.clear_with(220)
    page.insert_image(fitz.Rect(0, 0, 60, 60), pixmap=pix)
    p = tmp_path / "scan.pdf"
    doc.save(str(p))
    with pytest.raises(ValueError):
        parse_pdf(p)
