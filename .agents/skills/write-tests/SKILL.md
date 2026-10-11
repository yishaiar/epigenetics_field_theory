---
name: write-tests
description: |
  Write unit or integration tests for existing or new code.
  Use when the user asks to add tests, increase coverage, or
  test a specific function, class, or scientific workflow. Also invoked
  internally by /execute-new-feature's "write tests" phase, not only
  on direct user request.
---

# Test Writer

## Before Writing

1. **Read the code under test** — understand inputs, outputs, and side effects
2. **Identify the test type**:
   - Unit — single function or class in isolation (mock all dependencies)
   - Integration — multiple public operations together with only external dependencies mocked
   - Schema validation — Pydantic request, configuration, or result model validation
3. **Check existing tests** — follow the patterns already used in that test module

## Test Structure (per test)

1. **Arrange** — set up inputs, mocks, and initial state
2. **Act** — call the public function or method
3. **Assert** — verify the outcome

## Required Coverage Per Function

- Happy path — expected input, expected output
- Edge cases — empty, `None`, boundary values
- Failure case — what happens when it raises or returns an error
- **Optional fields** (e.g. a new AnnData metadata or Pydantic schema field): cover (1) field present + truthy value, (2) field present + falsy value, (3) field absent → `None`

## This Repo's Test Conventions

- Test classes inherit from `unittest.TestCase` (sync) or `unittest.IsolatedAsyncioTestCase` (asynchronous package code) — not pytest fixtures or `pytest-asyncio`
- No `conftest.py` — shared setup lives in the test class itself (`setUp`)
- Use `unittest.mock.patch` / `AsyncMock` / `MagicMock` to mock external dependencies — never require a network service or external dataset in a unit test
- Test files live beside their owner: `scbatch/<member>/tests/test_<module>.py`.
- For scientific functions, cover AnnData metadata validation and sparse or
  dense matrices whenever the public contract supports them.

## Rules

- One test class per class/module under test
- One test method per scenario — no multiple assertions testing different behaviors
- Never test private methods directly
- Mock external data providers and file-system boundaries — never require external resources in unit tests
- Prefer descriptive test method names (`test_high_phone_social_media_score`), not numbered ones (`test1`)
