# OpenLVM Website

This Next.js app is the OpenLVM website + workbench UI.

## Run Locally

From repo root:

```bash
npm --prefix website install
npm --prefix website run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Page Map

- `/` - Main landing page
- `/runs` - Run workflow index page that deep-links to workbench sections
- `/solana` - Solana arena + readiness flow overview
- `/workbench` - Full OpenLVM workbench UI

## Workbench Section Anchors

Use these deep links for demos/submission:

- `/workbench#quick-run`
- `/workbench#workspace-members`
- `/workbench#run-and-compare`
- `/workbench#run-inspection`
- `/workbench#compare-results`
- `/workbench#compare-history`
- `/workbench#solana-arena`
- `/workbench#compare-artifacts`
- `/workbench#audit-events`

## Solana Readiness APIs

- `GET /api/workbench/arena/readiness`
- `GET /api/workbench/arena/readiness-plan`
- `GET /api/workbench/arena/release-readiness`
- `GET /api/workbench/arena/integrations`

## Build Check

```bash
npm --prefix website run lint
npm --prefix website run build
```
