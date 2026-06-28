"""Rendu HTML → PDF par **Chromium headless** (fidélité totale à la page web).

On ne réécrit pas un rapport à part : on imprime *la page de résultats elle-même*
(même CSS, mêmes graphes Chart.js, dépliants ouverts) via le moteur de rendu du
navigateur. C'est la seule techno qui garantit « le PDF = la page à l'identique »
(WeasyPrint a son propre moteur CSS et ne fait pas tourner le JS / les canvas).

Aucune dépendance Python : on pilote le binaire Chromium en sous-processus
(`--headless --print-to-pdf`). Le binaire est localisé via `ZEPHYR_CHROMIUM` ou
une liste de chemins usuels (image Docker : paquet `chromium`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

# Chemins candidats du binaire Chromium (le 1er existant gagne).
_CANDIDATES = [
    os.environ.get("ZEPHYR_CHROMIUM", ""),
    "/usr/bin/chromium",
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/google-chrome-stable",
    "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
]


def find_chromium() -> str | None:
    """Premier binaire Chromium disponible, ou None."""
    for c in _CANDIDATES:
        if c and Path(c).exists():
            return c
    for name in ("chromium", "chromium-browser", "google-chrome", "google-chrome-stable"):
        found = shutil.which(name)
        if found:
            return found
    return None


def html_to_pdf(html: str, *, timeout_s: int = 60) -> bytes | None:
    """Rend `html` (document complet) en PDF via Chromium headless.

    Retourne les octets du PDF, ou None si Chromium est introuvable / échoue
    (l'appelant peut alors retomber sur un autre rendu). Le JS de la page tourne
    (graphes Chart.js) et un budget de temps virtuel laisse le rendu se stabiliser.
    """
    chrome = find_chromium()
    if not chrome:
        return None
    with tempfile.TemporaryDirectory(prefix="zephyr-pdf-") as d:
        page = Path(d) / "page.html"
        out = Path(d) / "out.pdf"
        page.write_text(html, encoding="utf-8")
        cmd = [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--hide-scrollbars",
            f"--user-data-dir={d}/profile",
            "--no-pdf-header-footer",
            "--run-all-compositor-stages-before-draw",
            "--virtual-time-budget=6000",
            f"--print-to-pdf={out}",
            page.as_uri(),
        ]
        try:
            subprocess.run(  # noqa: S603 - binaire de confiance, arguments contrôlés
                cmd, timeout=timeout_s, check=True,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            )
        except (subprocess.SubprocessError, OSError):
            return None
        if out.exists() and out.stat().st_size > 0:
            return out.read_bytes()
    return None
