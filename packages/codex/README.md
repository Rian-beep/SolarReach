# codex_brain

AI content-generation services for SolarReach.

- `anthropic_client.py` — async Anthropic wrapper with prompt caching + cost tracking
- `generators/deck.py` — Sonnet 4.6 pitch deck JSON spec generator
- `generators/pptx_renderer.py` — python-pptx renderer (11 slides, 16:9)
- `generators/pdf_converter.py` — libreoffice headless PPTX → PDF
- `generators/charts.py` — matplotlib ROI cumulative cash-flow chart
- `generators/email.py` — Sonnet 4.6 A/B email variants
- `generators/org_chart.py` — Opus 4.7 decision-maker inferer
- `embeddings.py` — Voyage AI 1024-dim wrapper
- `celery_app.py` + `tasks.py` — async-bridged Celery worker

Run smoke test: `python -m codex_brain.generators.deck`
Run tests: `pytest`
