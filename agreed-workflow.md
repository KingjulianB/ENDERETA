# Agreed Workflow — ENDERETA

Living reference for how the human and the AI agent divide the work on
this project. Edit directly whenever the agreed convention changes —
this is the source of truth, not a one-time setup doc.

## Base workflow: ECC plan-first, confirm-before-code

This project explicitly follows ECC's `/plan`-style discipline
(requested at project start): before any code is written for a new
piece of work, restate requirements, propose architecture/files/risks/
tests, and wait for explicit confirmation. Once approved, work proceeds
step by step with verification after each step (tests run, output
inspected) rather than a single large batch of unverified changes.
This planning-doc set (`project_log.md`, `discrepancies.md`,
`dayX_objectives.md`, this file) is the cross-session memory layer on
top of that per-task discipline — it doesn't replace it.

This environment does not expose ECC's `TaskCreate`/`TaskUpdate`
tools, so live in-session progress is instead communicated via short
inline status updates after each real step (not a single silent block
followed by a wall of results) plus the honest "tested vs. scaffolded"
distinction kept in `DOCS.md`/`CHANGELOG.md` inside `enderata/`. If
those tools ever become available in this environment, prefer them for
any 3+-step task per this skill's default guidance.

## Division of responsibility

| What | How it's done | Who touches it |
|---|---|---|
| Architecture/plan for new work | ECC `/plan`-style: requirements, risks, files, tests, then wait | Agent proposes, human approves before code |
| Code/file changes | Read → Edit/Write, verified (tests, compile, or a real run) after each step | Agent, within an approved plan |
| Version bump in `enderata/config.yaml` | Bumped on every fix so HA Supervisor offers an "Update" | Agent, automatically, no need to ask each time |
| git commit | Descriptive message, `Co-Authored-By` trailer included | Agent, once a change is verified |
| git push (normal) | Straight push to `main` | Agent, once the user has asked for the repo to reflect current work |
| Destructive/hard-to-reverse git ops (`push --force`, history rewrite, `rm -rf`) | Explicit per-instance confirmation, facts presented first (what's touched, rollback, verbatim instruction) | Human approves each time; agent never does this on its own judgment |
| Confidential/sensitive files (e.g. the business plan PDF) | Kept out of the public repo via `.gitignore`, flagged to the human rather than silently included or silently excluded without saying so | Agent flags, human can override |
| Real build/runtime verification (Docker build, add-on start) | No Docker available in the agent's environment — every build/run fix is derived from real logs the human pastes back, never guessed speculatively | Human runs it on real HA hardware, agent fixes from the actual error |

## Environment / tooling gotchas

- **GateGuard fact-forcing hook**: the first `Edit`/`Write` to any file
  in a session, and any Bash command matching a "destructive" pattern
  (even inert text like `rm -rf` inside a Dockerfile heredoc, which
  never actually executes here), requires presenting a short fact
  block (what's touched, rollback, the user's verbatim instruction)
  before the call succeeds. Just answer it and retry the same call —
  it's not a real blocker, just an extra confirmation step.
- **No Docker in the agent's environment**: `docker --version` fails
  here. All Docker build/run verification happens on the user's real HA
  instance — the agent iterates from pasted-back real logs, and
  explicitly avoids guessing unverifiable specifics (a package name, an
  install-script URL) when a real log can settle it instead. (The
  bashio 404 was exactly this lesson learned mid-project — see incident
  log.)
- **Git Credential Manager** is already configured and authenticates
  pushes to `https://github.com/KingjulianB/ENDERETA.git` without any
  extra login step.
- **Windows Git Bash path translation**: `/tmp/...` paths don't
  resolve the same way for native Windows Python invoked from Git Bash
  as they do for Bash itself — use a relative path or a Windows-style
  path when a Python subprocess needs to read what Bash just wrote.

### Home Assistant add-on / geospatial-specific gotchas

- HA Supervisor's `build.yaml` validates `build_from` image names
  against a strict `namespace/image[:tag]` regex — an unqualified
  official image name (e.g. `python:3.12-slim-bookworm`, no namespace)
  silently fails validation and Supervisor falls back to its own Alpine
  base image with no warning surfaced to the build log's top-level
  error. Hardcode `FROM` directly in the Dockerfile instead of relying
  on `build.yaml`.
- Debian's plain `postgis` apt package is client tools/loaders only —
  it does **not** ship `postgis.control`. The actual server extension
  for a given PostgreSQL major version needs the versioned package
  (`postgresql-15-postgis-3` for PG 15 / Debian bookworm).
- Running `initdb`/`pg_ctl` by hand (bypassing Debian's
  `pg_createcluster` wrapper) means nothing else creates
  `/var/run/postgresql` (the compiled-in default unix socket dir) or
  chowns anything outside the explicitly-chowned `PGDATA` — both must
  be handled manually in `run.sh`.
- OpenStreetMap's tile usage policy explicitly forbids using
  `tile.openstreetmap.org` from a distributed/packaged application
  without prior OSMF sysadmin approval — this isn't a rate limit that
  clears up, it's policy-as-designed. Don't point a shipped product's
  default basemap at it.

## Why `push --force` / history rewrite needs explicit approval

Used once so far: a `git add -A` accidentally committed a personal
screenshot (browser tabs, local network IP) to the **public** repo.
Fixing it required rewriting git history (`git filter-branch`) and
force-pushing over the public `main` branch — an operation that, if
anyone had already cloned in the narrow window, cannot be un-done for
them, and is irreversible on the remote from the agent's side. The
agent proposed the fix and explained the risk, then only executed it
after the human said so explicitly (turn: "fait le push --force").

## Task tracking for multi-step work

`TaskCreate`/`TaskUpdate` are not available in this environment (see
gotchas above). In their place: for any 3+-step task, work proceeds
step-by-step with a short inline status line before/after each real
step (what's being tried, what the result was), and cross-session state
lives in this doc set rather than a live task list. If `TaskCreate`/
`TaskUpdate` become available, switch to them per this skill's default
guidance rather than continuing the inline-narration substitute.

## Incident log

- **2026-09-20**: `git add -A` after a documentation-only commit swept
  up a newly-created `Capture_ecran/` folder containing a personal
  screenshot (browser tabs, local IP, bookmarks) and pushed it to the
  public repo. Caught immediately when reviewing the commit's file
  list. Fixed by untracking the folder, adding it to `.gitignore`,
  rewriting history with `git filter-branch --index-filter` across all
  9 commits, deleting the filter-branch backup refs, running
  `git gc --prune=now`, and force-pushing — only after the human
  explicitly confirmed the force-push. **Change going forward:** stage
  files explicitly (`git add <path>...`) instead of `git add -A` when
  a new, unreviewed top-level folder could plausibly contain anything
  outside the intended change set.
- **2026-09-20**: Guessed a `bashio` install script URL
  (`raw.githubusercontent.com/.../bashio/master/install.sh`) while
  offline/without Docker to verify it; it 404'd on the user's real
  build. Root cause on inspection: bashio wasn't even used anywhere in
  the codebase — it was spontaneously added "just in case" rather than
  because something needed it. **Change going forward:** don't add a
  dependency (especially one fetched from a guessed URL) unless the
  code actually calls it; when a real error surfaces from something
  speculative, prefer removing the speculation over patching it with
  another guess.
