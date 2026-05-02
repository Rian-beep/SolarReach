# Teammate Onboarding — SolarReach Hackathon

> **You're a non-AI human teammate joining mid-build. Read this top-to-bottom and you'll be productive in 5 minutes.**

Last updated: 2026-05-02 ~11:35

---

## 0. The 30-second pitch

Operations cockpit for the UK commercial solar industry. Type a postcode → 3D Photorealistic map of London → markers per building → click → drawer shows real Land Registry owner + AI-inferred decision-maker + per-pixel solar radiance overlay + AI-generated pitch deck + AI voice rehearsal. **All on MongoDB Atlas.** Theme: **Multi-Agent Collaboration**.

## 1. Where things live

```
SolarReach/
├── docs/
│   ├── CONTRACTS.md          ← READ THIS FIRST. Every interface between teams.
│   ├── RUNBOOK-DEMO.md       ← The verbatim 7-min demo path
│   ├── THEME-NARRATIVE.md    ← How we frame for judges
│   └── agent-log/            ← Live status from each parallel build agent
│       ├── A1-foundation.md
│       ├── A2-api.md
│       ├── A3-frontend.md
│       ├── A4-codex.md
│       └── A5-infra.md
├── packages/
│   ├── shared/               ← schemas + types (DON'T EDIT WITHOUT TELLING A1)
│   ├── api/                  ← FastAPI gateway (A2)
│   ├── scoring/              ← Celery worker for ingest+score (A1)
│   ├── codex/                ← Anthropic content gen (A4)
│   ├── voice/                ← ElevenLabs voice service (A5/A4)
│   └── web/                  ← React frontend (A3 — and YOU for Google Maps)
├── infra/                    ← docker-compose + Mongo init (A5)
├── scripts/                  ← seed, ingest, validate (A1)
└── data/raw/                 ← govt zips extracted here (gitignored)
```

## 2. Who's doing what (parallel agents)

The 5 agents are running simultaneously in Claude orchestration. You can read their live progress in `docs/agent-log/<name>.md`.

| Agent | Owns | Read their log to see |
|---|---|---|
| **A1 Foundation** | Mongo schema, validators, indexes, seed (50 leads), INSPIRE/CCOD ingest | `agent-log/A1-foundation.md` |
| **A2 API Gateway** | FastAPI scaffold, all routers, SSE, change streams | `agent-log/A2-api.md` |
| **A3 Frontend Shell** | React + Vite + Tailwind v4, Drawer, Header, Calculator, stores | `agent-log/A3-frontend.md` |
| **A4 Codex Brain** | Anthropic wrapper, pitch deck (PPTX→PDF), email A/B, decision-maker inference | `agent-log/A4-codex.md` |
| **A5 Integration** | docker-compose, .env, Makefile, CI, merge sheriff | `agent-log/A5-infra.md` |
| **You + Luke (Lead)** | `<MapSlot />` Google 3D map + Solar API + flux overlay + panel layout | — |

## 3. Your lane (Luke's lane)

**You own**: `packages/web/src/components/map3d/MapSlot.tsx` and the backend Solar API integration.

The frontend agent (A3) builds **everything else** in `packages/web/` and reserves a `<MapSlot />` component slot. You fill it in with:

```tsx
// packages/web/src/components/map3d/MapSlot.tsx
import { Lead, FluxOverlay, PanelLayout } from "@/lib/types";

export interface MapSlotProps {
  leads: Lead[];
  selectedLeadId: string | null;
  onLeadClick: (id: string) => void;
  fluxOverlay: FluxOverlay | null;
  panelLayout: PanelLayout | null;
}

export function MapSlot(props: MapSlotProps) {
  // YOUR Google <gmp-map-3d> implementation here
  // Lazy-load the SDK via dynamic import to keep main bundle small
  // ...
}
```

The contract is in [`docs/CONTRACTS.md` § 4](CONTRACTS.md#4-frontend-component-contracts). Changing it requires updating that doc + telling A3.

## 4. How to run locally

### Prereqs (one-time)
```bash
brew install docker pnpm
curl -LsSf https://astral.sh/uv/install.sh | sh    # Python tooling
```

### Boot
```bash
cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
cp .env.example .env.local
# fill in: ANTHROPIC_API_KEY, GOOGLE_MAPS_API_KEY, ELEVENLABS_API_KEY, MONGO_URI (Atlas)
make dev          # docker-compose up (mongo + redis + api + codex + web)
make seed         # populate ~50 demo leads from CCOD subset
open http://localhost:5173
```

### Verify
```bash
make verify       # health check all services
curl localhost:8000/health
```

### Common fixes
| Symptom | Fix |
|---|---|
| `403 API_KEY_HTTP_REFERRER_BLOCKED` | Set Google API key Application restrictions to **None**, not HTTP referrer. |
| Mongo `auth failed` | URI must include `?authSource=admin` |
| HMR not picking up changes | Container needs bind-mount; check `infra/docker-compose.yml` `volumes:` |
| `error_max_turns` on Write | TDD-Guard hook blocking. Rename `.claude/tdd-guard/` to disable. |
| Black screen in browser | Likely React hooks-after-conditional-return. Check console; refactor hooks above any early `return`. |

## 5. The 7-minute demo path (you'll run this)

See `docs/RUNBOOK-DEMO.md` for the exact narration. Summary:

1. Open app → Photorealistic 3D London
2. Type `EC1Y 8AF` → markers stream in (SSE + change streams)
3. Click highest-score marker → camera flies to building
4. Drawer "Intel" tab — real Land Registry owner + Companies House officers + AI decision-maker
5. Drawer "Pitch" → click Generate → real Sonnet 4.6 PPTX in ~10s
6. Drawer "Voice" → click Rehearse → ElevenLabs ConvAI in browser
7. Closer: "9 Atlas features. £0.40 spent. Built today by 5 agents + 2 humans."

## 6. Cardinal rules (DO NOTs — these cost hours when broken)

1. **DO NOT** commit `.env` or any file with real API keys.
2. **DO NOT** set Google API key restrictions to HTTP referrer (breaks server calls).
3. **DO NOT** overwrite INSPIRE polygons with Solar API axis-aligned bbox.
4. **DO NOT** auto-fire paid APIs without spend tracker + user click.
5. **DO NOT** filter panels frontend-only — server-side ray-cast clip in API.
6. **DO NOT** call React hooks after any conditional `return`.
7. **DO NOT** name custom Tailwind colors `base|sm|lg` (collides with utility shortcuts → invisible text).
8. **DO NOT** push to `main` directly. Branch: `feat/<your-name>-<scope>`.
9. **DO NOT** demo any code dated before 2026-05-02. Hackathon "new work only" rule.
10. **DO NOT** flip `SOLARREACH_LIVE_OUTBOUND=true` without explicit review.

## 7. Communication during the hackathon

- **Status check**: read `docs/agent-log/<name>.md` — agents append timestamped entries
- **Contract changes**: open a one-line note in the relevant agent log + update `docs/CONTRACTS.md` in the same commit
- **Blockers**: ping Luke; he'll ping the agent or course-correct
- **API keys**: Luke holds; provided to agents via `.env.local` (never committed)

## 8. Submission deadline

**5:00 PM TODAY** (Saturday May 2 2026). Submission portal: https://cerebralvalley.ai/e/mongo-db-london-hackathon/hackathon/submit

Required at submit:
- Public GitHub repo URL (will be created at integration phase)
- 1-minute demo video (recorded after demo dry-run)
- Team list

## 9. If you're picking this up cold

Run this:
```bash
cd "/Users/lukedudley/Downloads/SolarReach Mongo Hackathon"
cat docs/CONTRACTS.md | less   # the schemas + endpoints
cat docs/agent-log/A3-frontend.md   # what's been built on frontend
make dev                       # start everything
```
You're now productive.
