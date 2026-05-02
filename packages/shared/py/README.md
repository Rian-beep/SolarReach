# solarreach-shared

Shared Python package: Pydantic v2 models, financial math, compliance helpers.

## Install (uv)

```bash
cd packages/shared/py
uv pip install -e ".[dev]"
```

## Smoke test

```bash
python -m solarreach_shared.financial
pytest
```
