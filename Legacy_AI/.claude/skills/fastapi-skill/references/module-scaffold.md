# Rate Limiting Reference

Package: `slowapi` (wraps `limits` library). Install: `uv add slowapi`.

---

## Setup — app/middleware/rate_limit.py

This file owns the `Limiter` singleton. It is the only place the limiter is instantiated.

Rules:
- Key function: always use `get_remote_address` (from `slowapi.util`) as the default key.
  This keys limits per client IP. If the project has auth, optionally key by user ID instead.
- The `Limiter` instance is imported into `main.py` and into any route file that needs per-route limits.
- Default global limit set here (e.g. `"100/minute"`). Per-route limits override per endpoint.

---

## Registration — app/main.py

Three things to add to `main.py` when registering the limiter:

1. Attach `limiter` to `app.state`: `app.state.limiter = limiter`
2. Add the slowapi exception handler: `app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)`
3. Add `SlowAPIMiddleware` via `app.add_middleware(SlowAPIMiddleware)`

The `_rate_limit_exceeded_handler` returns a `429` JSON response with a clear error message.

---

## Per-route limits — routes.py

Decorate individual endpoints with `@limiter.limit("N/period")`:
- Period options: `second`, `minute`, `hour`, `day`.
- The route function must accept `request: Request` as its first parameter for slowapi to extract the key.
- Stack multiple decorators for burst + sustained limits (e.g. `"10/second"` + `"200/hour"`).
- Sensitive endpoints (login, password reset, OTP) get aggressive limits: `"5/minute"`.
- Read endpoints get generous limits; write/mutate endpoints get strict limits.

---

## Global vs Per-route

| Scope | Where defined | Example |
|---|---|---|
| Global default | `Limiter(default_limits=["100/minute"])` in `rate_limit.py` | All routes |
| Per-route override | `@limiter.limit("10/minute")` on the route function | That route only |
| Per-route strict | `@limiter.limit("5/minute")` on auth/sensitive routes | Login, signup |

---

## No loopholes

- Rate limits apply before auth checks — an unauthenticated flood is still rate-limited.
- `X-Forwarded-For` trust: only trust the proxy header if the app sits behind a known reverse proxy. Set `FORWARDED_ALLOW_IPS` accordingly in the environment — never blindly trust client-supplied headers.
- All 429 responses include a `Retry-After` header (slowapi adds this automatically).
