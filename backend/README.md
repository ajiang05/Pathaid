# Pathaid backend

The first feature provides student sign-up, login/logout, editable profiles, account deletion, and profile-field metadata. It has no frontend. Scholarship evaluation and recommendation generation are later features.

## Local setup

From `backend/`:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./pathaid.db
.venv/bin/alembic upgrade head
.venv/bin/uvicorn app.main:app --reload
```

Use PostgreSQL in deployed environments by setting `DATABASE_URL` to a `postgresql+psycopg://` URL. Set `PATHAID_PUBLIC_ORIGIN` to the frontend origin and `PATHAID_SECURE_COOKIES=true` under HTTPS. The API does not enable cross-origin browser requests; a same-origin proxy should expose `/api` to the frontend.

## API

- `GET /api/profile-fields` returns field metadata.
- `POST /api/auth/signup` and `POST /api/auth/login` accept `{ "email": "...", "password": "..." }`, set an HttpOnly session cookie, and return a CSRF token.
- `GET /api/auth/session` returns a fresh CSRF token after page reload.
- `POST /api/auth/logout` requires the `X-CSRF-Token` header.
- `GET /api/profile`, `PATCH /api/profile`, and `DELETE /api/profile` access only the signed-in account. PATCH accepts `{ "fields": { ... }, "ai_opt_in": false }`; send `null` for a field to remove its saved answer. PATCH and DELETE require `X-CSRF-Token`.

All profile fields remain optional. The account opt-in flag is stored but no student data is sent to OpenAI in this feature. Passwords are hashed with scrypt; session and CSRF tokens are stored as SHA-256 hashes. The rate limit uses the direct peer address and is shared through the database. Behind a reverse proxy, configure a trusted peer address policy before public deployment.

Run tests with `.venv/bin/pytest -q`.
