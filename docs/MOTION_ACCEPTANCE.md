# Motion recovery and planet replacement — 2026-11-04

Status: real motion verified; visual parity with Emerald Bio-Cosmos NOT accepted. No commit/push.

## Confirmed findings

- The initial local build had no `botanical-manifest.json`. `import.meta.glob` therefore compiled an empty asset list. The baseline browser requested no GLBs. The visible meadow/ferns were part of `emerald-meadow.webp`.
- The downloaded Poly Haven GLBs are specimen libraries. For example, Dandelion 01 has five top-level models translated by approximately 0, -1, -2, -3 and -4 metres. The old loader normalized the whole library by its longest dimension. This shrank each plant and its wind displacement drastically. The new loader selects an individual specimen before normalization.
- The old wind used each mesh's local Y bounds, rather than a common transformed plant root. This is not a reliable whole-plant deformation origin. Node transforms are now baked before anchored deformation.
- The old animation clock capped every frame at 45 ms. Below 22 FPS it advanced slower than elapsed wall time, further obscuring motion. Vegetation now uses elapsed time (with a one-second guard); hidden tabs reset the clock baseline.
- The old pause expression accepted any stored RENDERING/CANCELLING job. A stale state could freeze the hero indefinitely. This condition was removed; the local in-flight render request and Video Studio selection still pause it. No Windows stale-job incident was directly observed. Cross-client renderer activity is not exposed by the backend, so this is NOT a machine-wide load detector.
- The old planet really was the same noise fragment shader. It has been replaced, not tuned.

## Layer inventory

| Layer | Before | Now |
|---|---|---|
| Nebula/meadow/background ferns | Static generated WebP | Preserved; still static imagery, not individually bending foliage |
| Duplicate meadow lip | CSS background over scene | Restricted to bottom 6%; does not cover the live plant tips |
| GLBs | Empty in initial build; library normalized as one model when present | Four verified GLBs; individual specimens, instanced at selected positions |
| Wind | Local per-mesh bounds, tiny normalized specimens | Root-anchored vertex bending, quadratic tip weight, coherent gust plus per-position secondary phase |
| Planet | Procedural green/black noise shader | Generated albedo, MeshStandardMaterial, modest bump variation, directional light, separate rotating cloud sphere, thin atmosphere shell |
| Mist | CSS radial gradients | Existing soft CSS layer plus alpha-textured moving WebGL veil |
| Pollen | WebGL points | Preserved slow spatial motion |
| BotanicalEnvironment / BotanicalDetails | Not imported by Planet | Still dormant; not substituted as low-poly final assets |

## Assets

The four Poly Haven GLBs total **7,610,036 bytes**. Source metadata, author, license URL, bytes and SHA-256 are in `frontend/src/botanical-manifest.json`. All four local hashes and byte counts were verified. Live browser requests returned HTTP 200.

- Fern 02 — `fern_02`
- Dandelion 01 — `dandelion_01`
- Bermuda Grass 01 — `grass_bermuda_01`
- Mossy Rock Set 01 — `rock_moss_set_01`

Poly Haven's asset license page states CC0 and commercial use: https://polyhaven.com/license . The API attribution remains visible.

New surface and cloud maps were generated with the built-in image generator, then encoded as WebP. They are fictional illustration assets, not scientific maps, and are not labelled CC0 downloads. Prompts/checksums are in `planet-texture-provenance.json`. Added encoded texture transfer: 463,162 + 63,614 bytes (approximately 527 KB).

## Browser evidence

`evidence/motion/` contains:

- `before.png`: 1920×1080 baseline build, no GLB requests.
- `after.png`, `after-1366.png`: real updated FastAPI build.
- `planet.png`: new planet material in browser.
- `production-motion.webm`: 16-second normal-speed browser capture; normal wind, no debug exaggeration. Software-rendered footage has low FPS, not smooth hardware acceptance.
- `foliage-t0.png`, `foliage-t2.png`, `foliage-t5.png`: same real plant and shader, camera fixed; other layers excluded.
- `plant-comparison-t0-t2-t5.png`: exact crops of those frames side by side; no generated or retouched evidence.
- `diagnostics.json`, `after-debug.png`, `capture-trace.zip`: requests, renderer, animation time, pause reasons, geometry/texture counters.

The isolated real dandelion pixel test measured tip-band centroid displacement **19.111 px**, versus **0.446 px** at the root band in one recorded run. Thresholds: tip >1 px and root <1 px, with nonempty pixel mass checks. Wind=0 and reduced-motion both produced identical subsequent plant screenshots. Debug text is excluded from screenshot measurements; planet, pollen, fog and background are hidden only in isolation mode. Production video keeps all layers.

## Performance and limitations

- One canvas, capped DPR, no realtime shadows or postprocessing.
- Final scene: **10 draw calls**, **122,590 triangles**, **8 geometries**, **15 textures**; three instanced animated mesh batches (10 plant instances), plus rocks.
- Initial first-pass library rendering was 127 draw calls / 328,046 triangles; selection and instancing reduced both.
- Renderer: **ANGLE / Vulkan SwiftShader Device (Subzero)**, software rendering on Linux, not NVIDIA.
- Ten diagnostic FPS samples: 3.6, 6.8, 6.9, 3.6, 1.2, 3.2, 4.8, 3.8, 5.3, 5.1. Mean 4.43 FPS. This capture overlapped browser testing; it is a constrained software-renderer measurement, not a GTX 1650 benchmark.
- GPU VRAM and total process memory were not measured. Three.js resource counts are not memory usage in bytes.
- No console errors or failed HTTP requests in the normal capture. SwiftShader emitted ReadPixels stall warnings during screenshots.
- Windows 11, native Chrome, GTX 1650 and smooth 60 FPS: **NOT TESTED**.

## Honest visual gap

The planet is visibly different and has fine coast/river detail rather than large noise holes. Real flowers now move and remain rooted. Nevertheless:

- Most of the lush meadow in the reference remains a static background plate. Its individual leaves cannot bend.
- Live GLB foliage still has harsher silhouettes and less harmonious lighting than the painted meadow, and only frames the right-hand WebGL stage.
- The planet's lower edge is still too clearly separated from the meadow. The new moving mist helps but does not fully embed it.
- The cloud layer and thin atmospheric rim are restrained; this is not the reference's rich cinematic lighting/scattering.
- The live plants are not yet a fully cohesive ecosystem. No visual parity or production-ready claim is made.

## Debug mode

Debug UI is compiled only for Vite development or an explicitly instrumented build (`VITE_MOTION_DEBUG=1`). Production `npm run build` without that variable ignores the query.

- `/?motionDebug=1`: current time, running/paused, pause reason, loaded assets, visible animated batches, wind, WebGL, resource counters and asset failures.
- `&wind=0`: negative control; `&wind=3`: temporary exaggerated test wind.
- `&isolate=foliage&specimen=flower`: isolate the actual first flower instance; no replacement fixture geometry.

## Windows commands

Run from the repository root (code is still uncommitted in this workspace):

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python scripts/fetch_botanical_assets.py
if ($LASTEXITCODE -ne 0) { throw 'Asset acquisition failed' }
npm --prefix frontend ci
npm --prefix frontend run build
python -m pytest -q
Push-Location frontend
npx playwright install ffmpeg
$env:STUDIO_CHANNEL = 'chrome'
$env:STUDIO_HEADED = '1'
npm run test -- --workers=1
npm run test -- --workers=1
Pop-Location
```

Playwright now selects the project `.venv` interpreter automatically (Windows path included), with optional `STUDIO_PYTHON` override. It rebuilds the real frontend with debug instrumentation before launching FastAPI in an isolated temporary database. It does not reuse the production SQLite database or fake API responses for the workflow test. The missing/corrupt-asset test deliberately intercepts only the fern download and labels that injected failure.

To view debug mode manually:

```powershell
$env:VITE_MOTION_DEBUG = '1'
npm --prefix frontend run build
.\.venv\Scripts\python.exe -m uvicorn factory.app:app --host 127.0.0.1 --port 8001
# Open http://127.0.0.1:8001/?motionDebug=1
```

For the regular build, stop uvicorn, remove `VITE_MOTION_DEBUG` and run the build again. Existing localhost:8000 on the user's machine was not inspected.


## Final test results

| Check | Result |
|---|---|
| TypeScript + Vite build | PASS; existing >500 KB planet chunk warning remains |
| Browser E2E, run 1 | 4 PASS, 0 FAIL (55.0 seconds) |
| Browser E2E, run 2 | 4 PASS, 0 FAIL (54.9 seconds) |
| Backend pytest regression | 12 PASS, 0 FAIL; 1 upstream Starlette deprecation warning |
| Four local GLB hashes / sizes | PASS |
| Production capture console errors / failed requests | None observed |
| Windows / NVIDIA / 60 FPS | NOT TESTED |
| Visual parity with supplied concept | NOT ACCEPTED |

E2E covers existing planet rotation/pointer return/reduced-motion/context-loss assertions unchanged, actual foliage pixels and anchored roots, zero-wind and reduced-motion negative controls, deliberately injected missing/corrupt GLB failures, and existing create/edit/render/QC-block workflow against FastAPI. Render workflow uses the existing mock narration test fixture; this is not production TTS acceptance.

Earlier failed attempts are documented: missing browser/venv in the resumed environment, GLB load polling deadline too short under software rendering (extended from 5 to 15 seconds with the same assertions), and browser renaming the SRT download to TXT. The download anchor now explicitly supplies its existing artifact name. No backend, renderer, database or approval code changed.

## Files changed

- `frontend/src/BotanicalAssets.ts`: individual variant extraction, normalization, shared-root shader deformation, instancing, asset diagnostics, disposal.
- `frontend/src/Planet.tsx`: texture-driven planet, cloud sphere, WebGL mist, wall-time wind, debug instrumentation and cleanup.
- `frontend/src/main.tsx`: remove pause based solely on persisted job state.
- `frontend/src/style.css`: keep the meadow overlay away from live plant tips; debug/isolation styles.
- `frontend/src/Video.tsx`: explicit `download={name}` only, preserving the SRT filename.
- `frontend/src/assets/emerald-surface.webp`, `emerald-clouds.webp`: generated planet textures.
- `frontend/public/assets/bio-*.glb`, `frontend/src/botanical-manifest.json`: four downloaded assets and provenance.
- `frontend/tests/vegetation.spec.ts`: actual pixel-motion and asset-failure tests.
- `frontend/playwright.config.ts`: project-venv interpreter and fresh instrumented build for tests.
- `frontend/package.json`, `package-lock.json`: PNG decoding test dependency.
- `frontend/capture-motion.cjs`: isolated real-server screenshot/video/diagnostic capture.
- `.gitignore`: exclude local downloaded test browser cache.
- `docs/planet-texture-provenance.json`, this report and `evidence/motion/`: provenance and measured evidence.
