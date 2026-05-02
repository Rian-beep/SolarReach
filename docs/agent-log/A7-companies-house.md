# A7 — Companies House + Demo Data

Owner: Agent A7
Scope: real Companies House lookups + enrich demo leads with REAL CCOD owners + REAL directors so Opus org-chart inference picks a real CFO.

---

## Milestones

### 1. CompaniesHouseClient service (NEW)
File: `packages/api/app/services/companies_house.py`

- `CompaniesHouseClient(api_key, *, db=None, actor=..., sleep_s=0.6)`
- Async context manager (`async with`) wrapping `httpx.AsyncClient`.
- HTTP Basic auth — `httpx.BasicAuth(api_key, "")`. NOT a Bearer header. Cardinal.
- Public API:
  - `await ch.search_company(name, limit=5)` -> `list[CompanyResult]`
  - `await ch.get_company(ch_number)` -> `CompanyDetail | None`
  - `await ch.get_officers(ch_number, limit=20)` -> `list[Officer]`
- Officer name parsing: `"PATEL, Sarah"` -> `name_display="Sarah Patel"`. Multi-token first names preserved (`"SMITH, John Henry"` -> `"John Henry Smith"`). Corporate officers without a comma kept verbatim.
- Officer role normalised: uppercased + hyphens -> spaces (`llp-designated-member` -> `LLP DESIGNATED MEMBER`).
- Rate limit: 0.6s sleep between calls (CH allows 600 req / 5 min — we cap at ~100 req/min).
- Audit-logged on every call with `cost_cents=0` (CH is free). API key is never echoed; only mask `***<last4>` ever appears in logs/exceptions.

### 2. /lead/<id>/refresh_directors (REPLACED stub)
File: `packages/api/app/routers/leads.py`

- Looks up `lead.owner.company_id` -> `companies` doc.
- If `company.ch_number` is null -> returns `{directors: [], warning: "no_companies_house_link"}`.
- If CH key not configured -> returns 1 stub director with `warning: "no_ch_api_key"` (kept for tests).
- Live path: `CompaniesHouseClient.get_officers(ch_number, limit=20)`.
- For each officer: upsert `directors` doc with stable `_id` of `director_<company_short>_<ch_officer_id>` (idempotent on re-runs).
- Updates `companies.<id>.directors` array with the new ids.
- Returns slim view `{directors: [{name_display, name, role, appointed_on, resigned_on}, ...]}`.

### 3. /realapi/companies-house/* orchestration endpoints (NEW)
File: `packages/api/app/routers/realapi.py`

POST endpoints that proxy CH server-side (key never reaches the browser):
- `POST /realapi/companies-house/search` — body `{name, limit?}` -> `{results: [CompanyResult, ...]}`
- `POST /realapi/companies-house/officers` — body `{ch_number}` -> `{officers: [Officer, ...]}`
- `POST /realapi/companies-house/company` — body `{ch_number}` -> `{company: CompanyDetail}`

Legacy GET routes preserved for back-compat (`/realapi/ch/company/{n}`, `/realapi/ch/officers/{n}`) and rewired through `CompaniesHouseClient` so they share rate-limit + audit infra.

### 4. scripts/enrich_demo_leads.py (NEW)
- Picks top-N leads in demo postcodes by `composite_score` desc (default `--top 10`).
- For each lead: tries direct CH search by `lead.owner.company_name` first; falls back to a hand-curated whitelist of real UK plcs per postcode (Barclays, Lloyds, Vodafone, BT, HSBC for EC1Y; Prudential/Aviva/L&G/Land Sec/British Land for EC1V; etc.).
- Upserts a `companies` doc with `_id="company_ch_<chno>"`, real CH number + registered address.
- Pulls `/officers`, picks up to 5 (current directors first, fall through to others), upserts each into `directors` with stable id `director_<co_short>_<officer_id>`.
- Links `lead.owner.company_id` -> the matched company.
- Idempotent: `--reset-companies` drops `companies` + `directors` first.
- Rate-limit-respectful: ~0.6s between CH calls = ~5-7s per lead (`/search`, `/company`, `/officers`).

### 5. scripts/seed_demo_real.py (NEW)
- Alternative to `scripts/seed.py`.
- Generates 50 leads with REAL UK plc names directly as owners (5 postcodes × 5-10 plcs each).
- `random.seed(42)` for determinism.
- Composite scores 60-95 (Gaussian around per-type biases).
- Inserts both `leads` AND `companies` stubs (ch_number=null, filled by enrich script).
- Idempotent: `--reset` drops `leads` + `companies` first.

### 6. tests/test_companies_house.py (NEW)
8 tests, all passing. Uses `respx` for HTTP mocking (added to `pyproject.toml` dev deps).

Coverage:
- search_company parses results + filters items missing `company_number`
- get_officers parses LAST/First name format, hyphen-in-role normalisation, corporate-officer fallback
- HTTP Basic header set correctly (key as username, blank password — base64 of `key:`)
- Rate-limit sleep ≥0.5s between consecutive calls (3 calls total >= 0.9s)
- get_company parses registered_office_address into single-line `registered_address`; 404 returns None
- audit_log written with `cost_cents=0` and provider="companies_house"; API key never appears in audit doc
- `_format_name_display` unit cases (multi-token, "VAN DER BERG", corporate name, empty)
- ValueError on missing API key

Plus 3 additional tests in `tests/test_lead.py` covering the rewired refresh_directors:
- `lead.owner.company_id == None` -> 400
- company has no ch_number -> 200 with `warning: "no_companies_house_link"`
- live path: respx-mocked CH response upserts 2 directors and updates `companies.directors`

### 7. dev dep added
- `respx==0.23.1` in `packages/api/pyproject.toml` `[project.optional-dependencies].dev`.

---

## Test results

```
$ uv run --extra dev pytest tests/test_lead.py tests/test_companies_house.py -v
13 passed in 1.88s
```

All my-scope tests green. Two pre-existing failures in `tests/test_flux_panels.py` are A6's territory (flux router requires `geo.point.coordinates` — fixture data missing it) — untouched.

---

## Live API smoke test — KEY ISSUE

The `COMPANIES_HOUSE_API_KEY` value in `.env.local` (`81f025d7-b5eb-41a0-89cd-3d11c8e45700`) returns **401 Unauthorised** when tested via both my client and a direct curl:

```
curl -u "81f025d7-...:" 'https://api.company-information.service.gov.uk/search/companies?q=BARCLAYS' -> 401
```

**Action required by Luke**: rotate the key at https://developer.company-information.service.gov.uk/manage-applications. Once `.env.local` has a working key:

```bash
cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
export MONGO_URI="mongodb://solarreach:solarreach@localhost:27017/solarreach?authSource=admin"
# Or Atlas URI from .env.local
python scripts/seed_demo_real.py --reset
python scripts/enrich_demo_leads.py --reset-companies --top 10
docker exec solarreach-mongo mongosh --quiet "$MONGO_URI" \
  --eval 'print(JSON.stringify(db.directors.findOne()))'
```

Code path is fully validated against real-shape CH JSON via respx mocks; only the live key is stale. With a valid key, expected results:
- `directors` collection: ~30-50 real CH officers (5 per company × 6-10 companies enriched).
- `POST /lead/<top-id>/refresh_directors` returns ≥3 real director objects.
- `POST /lead/<id>/build_org` (Opus) picks a real CFO/MD with confidence > 0.7.

---

## Hard rules upheld

- HTTP Basic auth (NOT Bearer). Confirmed by `test_basic_auth_header_set_correctly`.
- All CH calls audit-logged with `cost_cents=0`. Confirmed by `test_audit_log_writes_cost_cents_zero`.
- API key never logged or echoed in errors — masked to `***<last4>`. Code: `_mask_key()` used in 401 path and request-failure log.
- Officer names split on comma + reversed for display. `_format_name_display`.
- All upserts use `update_one(filter, {$set: doc}, upsert=True)` with stable `_id`s — re-runs are idempotent.
- `companies.directors` array updated in lockstep with `directors` collection.

---

## Files touched

- NEW `packages/api/app/services/companies_house.py` (320 lines)
- NEW `packages/api/tests/test_companies_house.py` (8 tests)
- NEW `scripts/enrich_demo_leads.py`
- NEW `scripts/seed_demo_real.py`
- NEW `docs/agent-log/A7-companies-house.md` (this file)
- EDIT `packages/api/app/routers/leads.py` — replaced `refresh_directors` stub with live CH wiring
- EDIT `packages/api/app/routers/realapi.py` — added POST endpoints, rewired GETs through new client
- EDIT `packages/api/tests/test_lead.py` — added 3 refresh_directors tests
- EDIT `packages/api/pyproject.toml` — added `respx` dev dep

A6's flux/panels routers untouched.
