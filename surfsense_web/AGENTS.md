# surfsense_web

Next.js App Router, `pnpm`, Biome. Root `AGENTS.md` owns organization and TDD.

Package manager is **pnpm**, not npm or yarn.

Next.js docs for this installed version: `node_modules/next/dist/docs/`.

## Commands

```bash
pnpm install
pnpm dev
pnpm format
pnpm test:unit
pnpm test:e2e
```

## Do

- New UI: vertical slice, one responsibility per file. See root `AGENTS.md`.
- React/Next, colors, UI polish, motion: `frontend-workflow` skill.
- shadcn components (`components.json`): `shadcn` skill after `frontend-workflow`, not instead of it — separate, and it inspects the project live.
- New behavior: `tdd` skill.

## Do not

- Do not add npm lockfiles.
- Do not rewrite existing routes to the new layout unless that is the task.

<!-- BEGIN:nextjs-agent-rules -->

# This is NOT the Next.js you know

This version has breaking changes — APIs, conventions, and file structure may all differ from your training data. Read the relevant guide in `node_modules/next/dist/docs/` (resolved from this file's directory; in monorepos the `next` package may not be visible from the repo root) before writing any code. Heed deprecation notices.

This block is written and re-added by `next dev` — verify at `node_modules/next/dist/server/lib/generate-agent-files.js`. Removing it from a diff only re-creates the uncommitted change; committing it with your work keeps the tree clean.

<!-- END:nextjs-agent-rules -->
