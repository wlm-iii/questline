# Contributing to Questline

These guidelines apply to all contributors, including coding agents.

## Branch workflow

- Make changes on an individual development or feature branch, never directly on `main`.
- Use descriptive branch names, such as `feat/quest-editor`, `fix/login-redirect`, or `docs/setup`.
- Keep branches and pull requests focused on a single change. Avoid unrelated cleanup.
- Discuss significant architectural changes in an issue before implementing them.
- Open a pull request to merge into `main`. Use a draft PR for unfinished work.

## Conventional Commits

Use the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) format:

```text
<type>[optional scope][!]: <description>
```

Common types are `feat`, `fix`, `docs`, `refactor`, `test`, and `chore`. Write concise, descriptive summaries.

Examples:

```text
feat(quests): add quest creation
fix(auth): handle expired sessions
docs: add local setup instructions
```

Mark breaking changes with `!` after the type or scope, or with a `BREAKING CHANGE:` footer. Explain the impact and migration steps in the commit body or PR description.

## Pull requests and review

Include the following in each PR:

- What changed and why.
- Links to related issues, when applicable.
- How the change was tested, including any checks that could not be run.
- Screenshots for visible UI changes.
- Any breaking changes, new dependencies, or configuration requirements.

Before merging:

- Obtain at least one approval from a reviewer other than the author.
- Resolve review feedback and pass all applicable checks.
- Use a Conventional Commit PR title, since PRs should be squash-merged into `main`.
- Delete the source branch after merging when it is no longer needed.

Keep feedback respectful and constructive. Authors should respond to review comments and explain any tradeoffs.

## Quality and testing

- Follow existing code style and project conventions.
- Add or update tests for behavior changes and bug fixes when test infrastructure is available.
- Run applicable formatting, linting, build, and test checks before requesting review.
- Record the commands run and their results in the PR. If a check is unavailable or cannot be run, say so rather than claiming it passed.

See [README.md](README.md#checks) for setup and validation commands. Backend changes should pass Ruff, Pyright, and pytest; database changes should also pass PostgreSQL integration tests and `alembic check`. Keep these instructions and CI current as tooling evolves. Never run destructive integration tests against shared or demo data.

## Documentation and dependencies

- Update documentation when setup, usage, behavior, or configuration changes.
- Explain why new dependencies are needed and include corresponding lockfile changes when applicable.
- Do not commit generated files or local development artifacts unless the project explicitly tracks them.

## Security

- Never commit credentials, tokens, private data, or local secret files.
- Use placeholders in configuration examples.
- If a secret is accidentally committed, notify the maintainers promptly and rotate or revoke it; deleting the file alone is not sufficient.
- Do not disclose sensitive vulnerability details in public issues or PRs. Coordinate privately with the maintainers.
