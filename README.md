# 대신고 (Daesingo)

Dashcam evidence preparation for traffic violation reports.

A driver who witnessed a dangerous traffic violation usually intends to report it — but rarely wrote down the exact time and place. Daesingo takes the fuzzy cues they *do* remember (roughly when, what kind of car, what happened, where) in natural language, then locates candidate incidents and their surrounding evidence intervals in hours of dashcam footage. The user only confirms and corrects, instead of scrubbing through video by hand.

> Status: **prototype**. The interactive prototype in `apps/prototype` is a UI/flow study driven by mock data — there is no backend or real video pipeline yet.

## Repository layout

A monorepo: `apps/` holds runnable applications, `docs/` holds the living documents, and `src/` + `eval/` hold the code skeleton that the module boundaries in `docs/architecture/` describe. Today the only runnable thing is the prototype; the skeleton folders contain READMEs only.

| Path | Contents |
|---|---|
| `apps/prototype/` | Interactive flow prototype (React 19 + Vite 6, mock data) |
| `apps/web/` | Placeholder for the real web app — README only; the `web` owner decides whether to grow the prototype or start fresh |
| `src/daesingo/` | Python modular-monolith skeleton: five domain modules + `common` runtime + `api`/`worker` composition roots — README per folder, no code yet |
| `eval/` | Offline evaluation harness skeleton (runners / scorers / manifests / results) — README per folder, no code yet |
| `scripts/`, `tests/` | Placeholders for team scripts and tests |
| `docs/product/` | Target user, problem, product promise, scope, user flow, validation plan |
| `docs/architecture/` | Module boundaries (v4) and contract principles |
| `docs/modules/` | Per-module research, experiments, decisions, contracts |
| `docs/management/` | Ownership, operating plan, cross-cutting decisions, security and trajectory reviews |
| `docs/design/` | Design system, the stage-1 mockups the UI was ported from, prototype spec |
| `docs/archive/` | Superseded submissions and closed meeting agendas — not current documents |

Documents are written in Korean; directory and file names are in English.

Start at [`docs/README.md`](docs/README.md) for how the docs are meant to be used — it is a set of working rules, not a project summary.

## Getting started

Requires Node.js 20+. This is an npm workspace, so install once at the repository root — not inside `apps/*`.

```bash
npm install            # once, at the root
npm run dev:prototype  # then open the URL Vite prints (default http://localhost:5173)
```

Other root scripts:

```bash
npm run build              # build every workspace that defines a build script
npm run preview:prototype  # serve the prototype's production build
```

## About the prototype

`apps/prototype` is a **flow prototype**, not product code: 10 screens driven entirely by mock data, with no backend, no video pipeline, and no AI calls. It ships a `ScenarioBar` demo control for jumping between flow states (no result, failed search, widened scope, …) without real data.

Whether the real web app extends this code or starts fresh is **not decided** — that call belongs to the `web` module owner. See [`apps/prototype/README.md`](apps/prototype/README.md) for the facts that decision needs.

## Archive

Research source material — reference PDFs, OCR output, scanned books, earlier drafts, and the Notion export — is **not** in this repository. It is large and includes third-party copyrighted work, so it stays local:

```
../대신고-자료아카이브/아카이브/
```

That archive repository must never be pushed to a remote. See its `읽어보기-아카이브전용.md` for details.

## License

[MIT](LICENSE). The copyright line names the team; adjust it if the competition or your institution requires specific attribution.
