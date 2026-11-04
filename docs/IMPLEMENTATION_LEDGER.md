# AI Review Studio — implementation ledger

Date: 2026-11-04. Full mission: [PRODUCT_REQUIREMENTS.md](PRODUCT_REQUIREMENTS.md).
**Overall: PARTIAL. This is not a production-complete delivery.**

## Repository baseline and preservation

Started from remote main ac1802a; local changes in README, app and startup script were byte-identical to that commit before syncing the local pointer. No user databases, environment files, credentials or media were removed. Existing visual work/evidence from 18b2e31 retained. Repository is local React/TypeScript + FastAPI + SQLite + FFmpeg, not a hosted SaaS.

## Implemented in this checkpoint

- Windows startup creates a missing venv, installs requirements using its Python, validates backend imports before frontend build, checks npm, and runs that same Python. Fixes the reported missing uvicorn module. Native Windows execution still NOT VERIFIED here.
- Persistent SQLite render queue, atomic claim, one leased running render, heartbeat/fencing, shutdown cancellation, expired-worker recovery, explicit retry cap, queued/running cancellation. Refresh does not cancel a render. Failed retries preserve the previous completed render.
- Schema v3 adds queue/audit/media-assets tables. Existing database gets a consistent SQLite backup before migration. Legacy approvals without content bindings are invalidated and retained in audit; their artifacts remain intact. Legacy stuck render states become recoverable FAILED/CANCELLED without deleting content.
- SHA-256 approval binding covers job/render identity, MP4, artifact bundle, editorial and metadata. Approval rejects absent/tampered files and stale content. Audit trail records editorial invalidation, queue/start/end/recovery/cancel/approval events.
- UI remembers selected project/tab, polls pending renders, warns before closing unsaved edits, exposes audit history.
- Two fixed official RSS providers: OpenAI and Google AI. Bounded 2 MB downloads, no redirects or arbitrary fetch URLs, DTD/entity rejection, sanitized excerpts, persistent timestamped snapshots, per-provider failure reporting. Keyword filtering is feed-local; ranking is explicitly a freshness heuristic, demand/competition remain missing.
- Research cards have verification status and explanation. Retrieved claims stay UNVERIFIED and block QC until manually reviewed. No claim of automated fact checking.
- Persisted validated non-secret settings: Ollama model, Vietnamese voice/provider, rate, volume, encoder. Render snapshots settings; UI changes blocked while queued/running. Actual TTS preview endpoint with bounded text/timeouts and mutual exclusion.
- Existing CPU/NVENC fallback, atomic MP4 finalization, subtitles, real FFmpeg validation and motion features preserved.

## Files

Backend: factory/assets.py, factory/app.py, foundation.py, queue.py, integrity.py, research.py, settings.py, drafting.py, media.py, tts.py.
Frontend: main.tsx, MediaLibrary.tsx, Workspace.tsx, editors.tsx, api.ts, style.css; tests/studio.spec.ts.
Operations/tests: Start-Factory.ps1, requirements.txt, tests/test_factory.py, test_recovery.py, test_research_settings.py, test_assets.py, README.

## Evidence and test scope

Baseline: 12 backend tests. Updated queue/integrity suite: 20 passed on Linux, including real FFmpeg with mock or tone fixtures; not real narration acceptance.
Research/settings focused tests: 4 passed (mock HTTP fixtures, no fake live success).
Browser initial regression: 4 passed on Linux software Chromium, including actual vegetation pixel movement, rooted stability, reduced motion, planet/context loss, and backend render/QC workflow.
Final regression counts recorded below after completion.

Live RSS: OpenAI returned 40 items. Google original URL redirected; canonical fixed URL verified HTTP 200 and adopted. Final two-provider result recorded below.
Live Edge TTS: attempt failed with CalledProcessError. **LIVE NOT VERIFIED**; no genuine voiceover/video acceptance claimed.
Windows/GTX 1650/NVENC: NOT VERIFIED. PowerShell runtime absent in this Linux environment.
No YouTube OAuth credentials used. No external publishing performed.

Commands: `.venv/bin/python -m pytest -q`; `npm --prefix frontend run build`; `STUDIO_CHROMIUM=/tmp/studio-chromium npm run test:e2e -- --workers=1` (frontend directory); direct bounded RSS and Edge TTS probes.
Visual baseline and recordings: docs/LIVING_UNIVERSE.md and evidence/living. No new visual-parity claim in this checkpoint.

## Acceptance matrix

| Requirement group | Status | Remaining |
|---|---|---|
| P0 setup/data recovery | PARTIAL | Native Windows install/upgrade smoke, full dependency lock |
| P1 living cinematic environment | PARTIAL | Existing motion proven; repeated flower sprites/static lake/canopy quality and native GPU performance remain |
| P2 complete UI | PARTIAL | Full routing and publishing/analytics workspaces; project search/status filters and media import now implemented |
| P3 discovery/research | PARTIAL | Only two feeds and manual claim review; general search, comparison/conflict engine, provider integrations/history UI |
| P4 script/demo/voice | PARTIAL | Full draft and per-scene rewrite implemented; real demo import/attestation implemented; script templates and real Ollama/voice/demo acceptance remain |
| P5 renderer/orchestration | PARTIAL | Queue/cancel/recovery exist; per-scene cache/resume, licensed music/mixing/transitions, richer media assembly |
| P6 approval | PARTIAL | Checksums/audit exist; publication settings version and fourth exact-settings confirmation not yet integrated |
| P7 YouTube/analytics | NOT IMPLEMENTED | OAuth/token protection, resumable private upload, exact authorized scheduling, authentic analytics/affiliate |
| P8 hardening | PARTIAL | Native Windows, real narrated end-to-end example, security/stress/accessibility review |

## Exact continuation order

1. Keep backend/motion regression green; do not rebuild working visuals or reset user data. Inspect current git status before edits.
2. Media import/provenance/license/dedup and demo attestation are implemented. Next connect general imported images/audio to scene assembly and add explicit retention UI; preserve immutable demo copies.
3. Per-scene rewrite is implemented as an unsaved draft. Add content formats; real Ollama/voice demonstration when services are available. Do not substitute silent/tone fixtures for acceptance.
4. Add immutable publication-settings revision and explicit fourth approval check, then official OAuth/resumable PRIVATE upload adapter with durable idempotency and mock API tests. Missing credentials block only live verification, not adapter implementation. Never publish publicly without exact user authorization.
5. Implement actual authorized analytics/manual affiliate records, then finish complete navigation and production timeline/audio workflow.
6. Complete real-sources Vietnamese-narration example, Windows Unicode/installation run, target GPU profiling and fresh visual evidence. Until then keep overall PARTIAL.

## Operational notes

Settings are non-secret JSON; secrets still belong in the operator environment. Research endpoints cannot fetch user-supplied URLs. Data root stays FACTORY_DATA/workspace; output and prior media are retained. Stop server before manual full-directory backup/restore. Restore only with matching schema/application version; do not overwrite a live database. Stale render directories need a future explicit retention policy; no automatic deletion of user artifacts is implemented.

Final live RSS check: PASS, 60 items (40 OpenAI + 20 Google), zero provider errors. Edge TTS remains NOT VERIFIED.
Browser rerun initially hit timing failures in the planet pixel test. Test now waits for model loading, a real simulation-time advance and the reduced-motion pause signal before comparing unchanged pixel criteria. No production wind/render logic was changed to satisfy this test.

## Continuation — media/editor integration

Implemented bounded raw uploads (100 MB), signature + ffprobe validation, per-project SHA-256 deduplication, immutable provenance, typed previews, project isolation and actual UI upload flow. Demo verification uses the selected real video, checks its import checksum and creates an independent copy; legacy recording.webm remains supported. Added per-scene Ollama rewrite with source-index validation and no automatic save. Projects now offer topic search/status filters. Edge TTS is installed by the standard requirements; live service remains unverified.

Added tests for upload rights/traversal/size/corruption, real FFmpeg MP4 import/dedup/range preview, tampered media rejection, cross-project access, render-time import lock, and unsaved scene rewrite. Browser tests include actual PNG import and refresh persistence.

## Final validation for this checkpoint

- Backend: **31 passed** on Linux, real FFmpeg plus isolated mock/tone fixtures; 1 dependency deprecation warning.
- Production TypeScript/Vite build: **PASS**. Lazy Three.js chunk still emits the >500 kB advisory; not concealed or suppressed.
- Browser: **3 motion tests passed** (planet, vegetation pixels/reduced motion, asset failure fallback), then **3 studio tests passed** after narrowing the status locator to the visible project status instead of newly added filter options. Includes actual backend queued render after page refresh, settings persistence and imported-media persistence.
- One intermediate browser run could not launch because temporary Chromium was absent after the environment changed. Reinstalled the test browser and reran; not counted as successful validation.
- Actual UI evidence: `evidence/workflow/media-library.png`, `evidence/workflow/studio.jpg` (isolated fixture content).
- Native Windows, physical GTX 1650, real Ollama, real Vietnamese TTS and YouTube upload remain NOT VERIFIED. OAuth/upload and analytics implementation still remain, as listed above. Overall product status stays PARTIAL.
