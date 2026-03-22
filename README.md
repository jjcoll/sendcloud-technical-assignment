# Rate Limiter Service

A small FastAPI service that enforces per-user request rate limits using a rolling 1-minute window.

## How to run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

fastapi dev
```

API docs available at `http://127.0.0.1:8000/docs`

## How to package

```bash
zip -r submission.zip . -x "*.pyc" -x "*/__pycache__/*" -x ".venv/*" -x ".pytest_cache/*" -x "*.pdf" -x ".git/*" -x "*.zip"
```

## How to test

```bash
pytest -v
```

The test suite covers:

- User creation and auto-incrementing IDs
- Request recording, remaining decrement, and independent quotas per user
- Rate limiting at the 10 request limit with `Retry-After` header validation
- Input validation: missing body, invalid types, and non-existent users
- Quota endpoint covering fresh users, partial usage, and exhausted quota
- Window reset behaviour: rather than sleeping 60 seconds, the `time` module inside `store.py` is patched to return a future timestamp, verifying the rolling window resets correctly without slowing the test suite down by using something like `time.sleep()`

## Design Decisions

### Why FastAPI

The assignment gave the choice between Django and FastAPI. I went with FastAPI because it's lighter and faster to set up. I also noticed from the job description that Sendcloud uses FastAPI, so it felt like the right fit. FastAPI's integration with Pydantic gives input validation and auto-generated OpenAPI docs out of the box, with the interactive docs available at `/docs` without any extra configuration. If the API grew, I'd add `summary`, `description`, and `tags` to each endpoint to keep the docs readable and useful.

### Rolling Window Algorithm

Each user has a `deque` of request timestamps. When checking quota, I remove any timestamps older than 60 seconds from the front, then count what's left. If there are fewer than 10, the request goes through and the new timestamp gets appended.

I used a `deque` instead of a regular list because removing from the front is O(1) with `popleft()` vs O(n) with `list.pop(0)`. At max 10 entries this doesn't really matter performance-wise, but it's the right data structure for the job.

### Keeping User as a plain dataclass

I considered moving the window eviction logic into the `User` class itself, which would be more of a DDD approach. I decided against it because I wanted `User` to stay a simple data container and keep the business logic in the `Store`. For a service this small, mixing data and behaviour in the same class felt like unnecessary complexity.

### User lookup at the endpoint layer

I call `get_user` in the endpoint rather than inside the store methods like `record_request` or `get_quota`. This keeps the store focused purely on business logic. Its methods assume they receive a valid `User` and don't need to handle the not-found case. The endpoint layer is the right place for HTTP concerns like returning a 404. If user lookup were inside the store, it would need to decide what to return when the user doesn't exist, which leaks HTTP-level concerns into the data layer.

### get_quota reuse and \_resets_in utility

The `get_quota` method handles timestamp eviction and quota counting. `record_request` calls it internally so both the `GET /users/{id}/quota` and `POST /requests` endpoints share the same logic without duplication.

`_resets_in` is extracted as a private utility function because both `get_quota` and `record_request` need to calculate time until reset. In `record_request` specifically, `_resets_in` is called again after appending the new timestamp. This is necessary to handle the case where the request log was empty before the request. Without recalculating, a user's first request would return `resets_in_seconds = 0` since `get_quota` would have seen an empty log. After appending, `_resets_in` correctly returns ~60 seconds. The underscore prefix signals it is an internal implementation detail, not part of the public interface.

## Trade-offs

### In-memory storage

All data lives in Python dicts and deques, nothing persists if the server restarts. This is fine for the assignment scope as in-memory storage was explicitly specified.

### No authentication

The `POST /requests` endpoint trusts the caller to send the correct `user_id`. In production you'd derive the user from an auth token or API key instead.

### Thread safety

The race condition where two concurrent requests for the same user both pass the quota check can't happen here as we only run a single process. In a multi-process or multi-node deployment this would become a real problem, but at that point the in-memory store wouldn't be shared across processes anyway, which is the bigger issue. Both problems would need to be solved together by moving to a shared data store.

### Integration tests over unit tests

I tested the API layer directly rather than writing separate unit tests for the `Store` class. The store logic (rolling window eviction, quota counting, and resets) is fully tested through the endpoint tests. Adding unit tests for the store would largely duplicate that coverage without adding value. At this scale, the integration tests give more confidence with less code.

### Read side effects

`GET /users/{id}/quota` mutates state. It evicts expired timestamps from the request log during the quota check. Ideally reads have no side effects, but the eviction is necessary to return an accurate count. Alternative would be a background cleanup job for example.

### No rate-limit headers

A production API could include `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset` headers on every response. I kept it simple and only included a `Retry-After` header on 429 responses.
