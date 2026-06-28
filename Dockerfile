# Image de déploiement de la plateforme web Zéphyr (FastAPI).
# Build reproductible via uv + extras (app = FastAPI/uvicorn/multipart,
# cao = ezdxf/shapely, viz = matplotlib, pdf = pymupdf, llm = SDK Anthropic pour
# l'extraction CPE — actif si ANTHROPIC_API_KEY est défini). Pas de WeasyPrint.
# Chromium est installé pour l'export PDF (impression de la page de résultats
# telle quelle, graphes inclus — cf. zephyr.report.pdf_chrome).
FROM python:3.11-slim

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    ZEPHYR_CHROMIUM=/usr/bin/chromium

RUN pip install --no-cache-dir uv

# Chromium headless + polices pour le rendu PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends chromium fonts-liberation fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 1) Dépendances d'abord (couche de cache) : pyproject + lock + sources du paquet.
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --extra app --extra cao --extra viz --extra pdf --extra llm

# 2) Code applicatif (change souvent → couche séparée).
COPY app ./app
COPY examples ./examples

EXPOSE 8000
# Railway fournit $PORT ; bind 0.0.0.0 obligatoire.
CMD ["sh", "-c", ".venv/bin/uvicorn app.web:app --host 0.0.0.0 --port ${PORT:-8000}"]
