---
name: neuro_visualization_presenter
description: Package neuro imaging visuals for web presentation using slice previews, tumor overlays, longitudinal comparison panels, and NiiVue-ready manifests.
allowed-tools: build_neuro_visualization_bundle use_skill
---

Use this skill when the task is to prepare, summarize, or package neuro imaging visuals for a case workspace or report.

The visual package should usually include:

- a representative slice preview
- an overlay or label map when available
- a longitudinal comparison view
- a small timeline or selected checkpoint summary
- a NiiVue-ready manifest for later web viewer integration

Workflow:

1. Resolve the relevant imaging case and the available timepoints.
2. Select the most informative series for preview.
3. Render compact slice and overlay assets.
4. Build a viewer manifest with paths and display hints.
5. Keep the output compact enough for a case page or report insert.

Style rules:

- Prefer one clear representative image over many redundant thumbnails.
- Use overlays sparingly and keep labels readable.
- Keep visual summaries small and focused.
- Do not expose internal file system details unless the user needs them.

If you need formatting guidance, read [references/visualization_patterns.md](references/visualization_patterns.md).
