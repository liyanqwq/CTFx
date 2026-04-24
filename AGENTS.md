# Repository Guidelines

## Project Structure & Module Organization
`ctfx/` contains the Python package. Keep CLI wiring in `ctfx/cli.py`, command entrypoints in `ctfx/commands/`, business logic in `ctfx/managers/`, server code in `ctfx/server/`, and shared helpers in `ctfx/utils/`. The React WebUI lives in `frontend/src/` with page components under `frontend/src/pages/` and shared UI in `frontend/src/components/`. Tests live in `tests/`. Built frontend assets are emitted to `ctfx/server/static/` and included in package builds.

## Build, Test, and Development Commands
Use `make dev` to install editable Python deps plus test/lint tooling. Use `make test` for the full pytest suite, `make test-quick` for a fast stop-on-failure run, and `make lint` or `make lint-fix` for Ruff checks. Build the WebUI with `make frontend`, then package everything with `make build`. Run the local server with `ctfx serve`; open the browser flow with `ctfx webui`.

## Coding Style & Naming Conventions
Target Python 3.11+ and keep Python lines within Ruff’s 100-character limit. Follow the existing separation of concerns: command modules should stay thin and delegate to managers. Use `snake_case` for Python modules, functions, and test names. In the frontend, use TypeScript with React function components, `PascalCase` for component/page files such as `Dashboard.tsx`, and keep shared browser API code in `frontend/src/lib/`. Match the repository’s existing quote and import style in each language rather than reformatting unrelated files.

## Testing Guidelines
Write pytest tests under `tests/` with names like `test_api.py` and `test_workspace.py`. Prefer real temporary directories and fixtures from `tests/conftest.py` over heavy mocking. Run tests with `PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION=python` when invoking pytest directly, for example `python -m pytest tests/test_api.py -v`, to avoid the documented global `web3` plugin issue.

## Commit & Pull Request Guidelines
Recent history mixes generic messages like `update` with clearer subjects like `feat: add personal attacker toolkit (v0.2.4)`. Prefer the clearer style: short, imperative, and scoped when possible, such as `feat: add ctfd scoreboard caching` or `fix: reject escaped workspace paths`. PRs should state the behavior change, list validation commands run, and include screenshots for WebUI changes. Link related issues or competition workflow context when relevant.

## Security & Configuration Notes
Do not weaken path validation or token handling. Keep workspace-bound path checks intact, treat `~/.config/ctfx/config.json` as user state, and never commit real tokens, cookies, or competition data. When changing auth, API, or MCP behavior, verify both bearer-token and WebUI session flows.
