# docs/ — GitHub Pages Deploy Directory

## Overview
This is the static website served by GitHub Pages. Files here are copies from `wiki/` (HTML, JS, JSON only — not Python scripts).

GitHub Pages is configured to serve from the `docs/` folder on the `main` branch.

## Structure
```
docs/
├── index.html      # Gallery page (copy of wiki/index.html)
├── viewer.html     # 3D viewer page (copy of wiki/viewer.html)
├── catalog.json    # Object metadata (copy of wiki/catalog.json)
└── js/
    └── viewer.js   # Viewer logic (copy of wiki/js/viewer.js)
```

## Deployment
After making changes in `wiki/`, copy the updated files here:
```bash
cp wiki/index.html wiki/viewer.html wiki/catalog.json docs/
cp wiki/js/viewer.js docs/js/
```
Then commit and push. GitHub Pages will auto-deploy.

## Key Design Decisions
- Static files only — no build step, no bundler, no framework
- Babylon.js loaded from CDN (no local copy)
- All mesh data hosted on HuggingFace (not in this repo) to keep repo small
- GLB fetched as blob before passing to Babylon.js to work around HuggingFace redirect issues
