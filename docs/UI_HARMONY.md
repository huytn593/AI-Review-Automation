# Continuous landscape and readable studio

Implemented 2026-11-05 in `frontend/src/living.css`.

The landscape is one fixed, cover-sized layer behind the entire application, including navigation, the top bar and working sections. The hero has no separate background plate. The image is neither stretched to document height nor tiled. Existing WebGL plants/planet remain in the hero and keep their existing pause and reduced-motion behavior.

A soft radial dark layer behind hero copy separates typography from scenery without a visible rectangular card. Working panels use a 94%-opaque dark green surface; navigation/top bar use translucent dark surfaces. Background detail remains visible in the margins. Text sizes use rem values: body/input/textarea 16px, buttons/navigation/labels 14px, supporting labels 12px. Serif typography is limited to the hero; workspace headings use the same sans-serif family as controls. Focus outlines and minimum 44px button targets are retained.

Working content is centered and capped at 1440px. Mobile uses a horizontally scrollable navigation rail, single-column panels and 16px form text.

Browser inspection on Linux Chromium:

| Viewport | Horizontal overflow | Body text | Panel width |
|---|---|---|---|
| 1920 × 1080 | None | 16px | 1440px |
| 1366 × 768 | None | 16px | 1094px |
| 390 × 844 | None | 16px | 358px |

No page JavaScript errors during viewport inspection. Production TypeScript/Vite build passes; the existing large Three.js chunk warning remains. No backend, project data or publishing behavior changed.

Screenshots (actual browser, reduced motion):

- [Overview 1920](../evidence/harmony/overview-1920.jpg)
- [Overview 1366](../evidence/harmony/overview-1366.jpg)
- [Overview mobile](../evidence/harmony/overview-390.jpg)
- [Workspace 1920](../evidence/harmony/workspace-1920.jpg)
- [Workspace 1366](../evidence/harmony/workspace-1366.jpg)
- [Workspace mobile](../evidence/harmony/workspace-390.jpg)

Regression: all 6 Playwright browser tests passed (motion, reduced motion, context loss, render/QC after refresh, settings persistence and media import).
