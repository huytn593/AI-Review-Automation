# Living Creative Universe — 4 November 2026

## Reference analysis

The supplied recordings were inspected as frame sequences, not treated as production assets.

| Reference | Observed composition | Motion evidence | Design response |
| --- | --- | --- | --- |
| A, 16:37:40 (6.21 s) | Viewport landscape; pink/ivory flowers frame reflective water, hills and large clouds; centered italic serif headline | Short sequence with subtle scene differences; insufficient evidence to separate plant deformation from camera/plate motion confidently | Continuous landscape and editorial headline, layered foreground framing, readable central sky |
| B, 16:40:05 (1.22 s) | Dark botanical surround, restrained copy/CTA and crisp software panel | Too short to establish a full animation cycle | Quiet dark studio panels below the cinematic entry; real application controls preserved |
| C, 16:41:10 (2.01 s) | Bordered card, boxed headline left, oversized high-contrast green sphere right | Planet surface/orientation changes; independent botanical motion not convincingly visible at recording scale | Remove nested hero card; make planet a distant supporting element; separately animate foreground plants |

## Implementation and visual blueprint

1. Original nocturnal valley plate: midnight teal, ivory moonlight, violet clouds, blush flowers, lake and layered hills. It is static scenery, not claimed as animated foliage or water.
2. Centered serif headline directly over the environment, with compact primary/secondary actions. Sidebar and working sections remain functional.
3. Smaller distant planet with a new geographic surface, subdued rough material, reduced bump, separate cloud rotation and cooler atmospheric rim. This is a textured globe, **not** a fully modeled forest-canopy globe like the user's botanical sphere reference.
4. Nine separately instanced flower sprigs: original transparent image on a 6×24 segmented mesh. Each stem bends with squared height, so the root stays anchored. Spatial phase and slower gusts avoid synchronized motion.
5. Existing CC0 fern/grass meshes use the same anchored wind principle. The old grass GLB has an RGB black-matte atlas without alpha; a shader discards its black background. Mossy rocks are scaled down into the foreground.
6. Separate drifting petals, pollen and translating fog texture. These animate independently of pointer parallax. No whole-image movement is presented as plant motion.
7. The studio receives consistent spacing, typography, timeline and panel materials. Project/editor/render/approval APIs, SQLite and backend code are unchanged. No automatic publishing was added.

## Assets

See [living-assets.json](living-assets.json) for sizes, hashes and provenance, and the existing [botanical manifest](../frontend/src/botanical-manifest.json) for model sources. Poly Haven's [license](https://polyhaven.com/license) was checked: model assets are CC0, including commercial use; attribution is optional. Existing credited assets were reused instead of downloading duplicate models. Generated assets are not labelled CC0. No frames, footage or artwork copied from the reference websites are shipped.

Original assets were produced with built-in image generation, then encoded as WebP:

- `living-valley.webp`: original 16:9 photoreal nocturnal botanical valley, reflective lake, mossy hills, pink/ivory cosmos and flowering branches; midnight teal sky and violet clouds; broad central negative space; no text/UI or sphere.
- `living-surface.webp`: 2:1 equirectangular fictional planet map, coherent sage/olive forest continents, jade lakes and dark teal oceans; no baked lighting, atmosphere, text or high-contrast random speckles.
- `cosmos-sprig.webp`: isolated pale blush cosmos blossom, slender full stem, finely divided green leaves, transparent background, upper-left soft moonlight; no pot, soil or additional flowers.

The three new runtime textures total approximately 583 KB. The unused legacy dandelion GLB is no longer requested, saving about 3.1 MB of scene downloads.

## Verification

- **PASS:** `npm run build` (TypeScript and production Vite build).
- **PASS:** `npm run test:e2e -- --workers=1`, 4/4 tests. Uses the real FastAPI application with isolated temporary project data. Includes project creation, research/storyboard edits, FFmpeg render and approval gating.
- **PASS:** planet pointer response, changed rendered pixels, reduced motion, context-loss fallback.
- **PASS:** flower-tip motion with fixed camera, anchored roots, zero-wind freeze and byte-identical isolated reduced-motion captures.
- **PASS:** missing/corrupt GLB handling; remaining scene continues.
- **PASS:** backend `python -m pytest -q`, 12/12.
- **PASS:** capture console/network inspection; see diagnostics for errors and renderer.
- **NOT TESTED:** physical GTX 1650/i5 performance, long-duration memory soak, live Ollama and live TTS services. Tests use mock voice and isolated project data.

Chromium was provided through an isolated serverless Chromium package because the normal Playwright browser download returned invalid archives. The project dependency lockfile was not changed. Video capture uses system FFmpeg. Parallel software-rendered browser tests exhausted the short polling budget, so the complete suite was run serially. A full-stage screenshot comparison permits only 1/255 channel rounding in fewer than 0.01% of channels; this addresses observed compositor rounding (110 channels), not visible movement. The separate vegetation freeze test still requires identical PNG bytes.

## Evidence and limits

Evidence is under [evidence/living](../evidence/living): baseline, desktop 1920×1080 and 1366×768, mobile, isolated foliage frames, a normal-speed recording and frames at 0/3/6/10/15 seconds. `pixel-measurements.json` contains measured tip/root displacements. `diagnostics.json` contains actual renderer and timed samples.

The capture host uses **SwiftShader software rendering**, not the target GPU. Its frame-rate samples must not be represented as GTX 1650 measurements. Heavy rendering stays in one lazy-loaded canvas and stops submitting frames when outside the viewport, hidden, reduced-motion, or paused for Video Studio/render work. DPR is capped and reduced after slow frames; all created textures, geometries, instanced meshes and observers are disposed.

Visual review: composition, color range and environmental depth differ materially from the previous green sphere/card. Foreground flower animation is measurable and visible. Remaining gaps against the references: the lake and baked blossom branches are static; flower sprites repeat one specimen and are 2.5D; the fern silhouettes remain less detailed than the photographic plate; the planet has no protruding canopy geometry. This is **partial reference fidelity**, not a claim of photoreal 3D parity or final user-approved visual acceptance.

### Measured motion and review links

Fixed-camera flower tip displacement: **19.59 px**; root displacement: **0.34 px** (subpixel/rasterization range).

- [Before](../evidence/living/before.jpg)
- [After, 1920×1080](../evidence/living/after.jpg)
- [After, 1366×768](../evidence/living/after-1366.jpg)
- [Mobile](../evidence/living/after-mobile.jpg)
- [Normal-speed motion recording](../evidence/living/production-motion.mp4)
- [Isolated vegetation, first frame](../evidence/living/foliage-t0.png)

The recording starts with page load, so its earliest frame may precede lazy asset readiness. Subsequent 3/6/10/15-second frames document the composed scene.
