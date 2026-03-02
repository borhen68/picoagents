# Contributing to picoagent

Thanks for contributing.

## Ways to Contribute

- Report bugs
- Propose features
- Improve documentation
- Add tests and fixes
- Improve provider/channel/tool integrations

## Before You Start

- Search existing issues and pull requests first
- Keep changes focused and small
- For security vulnerabilities, follow `SECURITY.md` instead of opening a public issue

## Development Setup

```bash
git clone https://github.com/borhen68/picoagents.git
cd picoagents
uv sync
```

If you do not use `uv`, editable install also works:

```bash
pip install -e .
```

## Run Tests

```bash
uv run pytest -q
```

## Pull Request Guidelines

1. Create a branch for your change.
2. Add or update tests for behavior changes.
3. Update docs when user-facing behavior changes.
4. Keep commit messages clear and specific.
5. Open a PR with:
   - What changed
   - Why it changed
   - How you validated it
   - Any follow-up work

## Coding Expectations

- Prefer clear and readable code over clever code
- Preserve backward compatibility where possible
- Keep safety constraints in place for shell/file tools
- Avoid unrelated refactors in the same PR

## Review Process

Maintainers may request revisions before merge. Priority is correctness, safety, and test coverage.
