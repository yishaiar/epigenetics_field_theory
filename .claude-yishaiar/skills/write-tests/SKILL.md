---
name: write-tests
description: |
  Write unit or integration tests for existing or new code.
  Use when the user asks to add tests, increase coverage, or
  test a specific function, service, or pipeline stage. Also invoked
  internally by /execute-new-feature's "write tests" phase, not only
  on direct user request.
---

# Test Writer

## Before Writing

1. **Read the code under test** — understand inputs, outputs, and side effects
2. **Identify the test type**:
   - Unit — single function or class in isolation (mock all dependencies)
   - Integration — multiple pipeline stages together (partial mocking), e.g. the full flow exercised in `test_pipeline.py`
   - Endpoint — FastAPI route via `TestClient`
3. **Check existing tests** — follow the patterns already used in that test module

## Test Structure (per test)

1. **Arrange** — set up inputs, mocks, and initial state
2. **Act** — call the function or hit the endpoint
3. **Assert** — verify the outcome

## Required Coverage Per Function

- Happy path — expected input, expected output
- Edge cases — empty, `None`, boundary values
- Failure case — what happens when it raises or returns an error
- **Optional fields** (e.g. a new field added to a pipeline stage or schema): cover (1) field present + truthy value, (2) field present + falsy value, (3) field absent → `None`

## This Repo's Test Conventions

- Test classes inherit from `unittest.TestCase` (sync) or `unittest.IsolatedAsyncioTestCase` (async pipeline/service code) — not pytest fixtures or `pytest-asyncio`
- No `conftest.py` — shared setup lives in the test class itself (`setUp`)
- Use `unittest.mock.patch` / `AsyncMock` / `MagicMock` to mock dependencies — never hit a real database or storage backend in a unit test
- For model-dependent code, use `MockModelLoader` from `apps/contactability/tests/mock_model_management.py` in place of the real model loader
- FastAPI endpoints: use `fastapi.testclient.TestClient` against the app instance, and `patch()` the pipeline method under test
- Test file lives in `tests/`, next to the module it covers: `apps/contactability/tests/test_<module>.py`

## Rules

- One test class per class/module under test
- One test method per scenario — no multiple assertions testing different behaviors
- Never test private methods directly
- Mock external calls (HTTP, database, storage) — never hit real services in unit tests
- Prefer descriptive test method names (`test_high_phone_social_media_score`), not numbered ones (`test1`)
