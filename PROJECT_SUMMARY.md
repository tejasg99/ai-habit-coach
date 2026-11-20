# AI Habit Coach — Project Summary

Repository: [tejasg99/ai-habit-coach](https://github.com/tejasg99/ai-habit-coach)

AI Habit Coach is a production-oriented REST backend for a mobile habit and fitness application. Users create an account, complete onboarding, receive an AI-generated seven-day workout and habit plan, log completed activities, track streaks and progress, and receive Expo push reminders.

The repository is primarily Python: **99.6% Python** and **0.4% Mako** for Alembic templates.

## Key Features

- Email/password signup and login
- Argon2 password hashing
- JWT access and refresh authentication
- Fitness, diet, equipment and timezone onboarding
- Gemini-based personalized weekly plan generation
- Strict validation of LLM-generated plans
- Daily habit completion and same-day undo
- Idempotent completion logging
- Derived streak and progress calculations
- Local-time push reminders
- Login throttling
- Complete account and user-data deletion
- Request tracing and structured logging
- Exported, committed OpenAPI contract
- Docker and CI/CD support

## Repository Structure

```text
ai-habit-coach/
├── app/
│   ├── api/routes/          # FastAPI HTTP endpoints
│   ├── core/                # Configuration, security, logging and middleware
│   ├── db/                  # SQLAlchemy and database setup
│   ├── jobs/                # Reminder scheduler and scheduled jobs
│   ├── models/              # SQLAlchemy persistence models
│   ├── schemas/             # Pydantic request and response schemas
│   ├── services/            # Domain and application logic
│   └── main.py              # FastAPI application and router registration
├── alembic/
│   ├── versions/            # Database migrations
│   └── env.py
├── tests/                   # API, service, integration and configuration tests
├── .github/workflows/       # CI and reminder scheduling
├── docs/openapi.json         # Generated API contract
├── scripts/export_openapi.py
├── dockerfile
├── docker-compose.yml
├── requirements.in
├── requirements.txt
├── requirements-dev.in
├── requirements-dev.txt
└── README.md
```

## Technologies Used

| Area | Technology |
|---|---|
| Language | Python 3.12 |
| API framework | FastAPI, Uvicorn |
| Validation | Pydantic v2 |
| Database | PostgreSQL |
| ORM | SQLAlchemy 2.0 |
| Migrations | Alembic |
| Authentication | PyJWT, pwdlib/Argon2 |
| HTTP client | HTTPX |
| AI | Gemini through an OpenAI-compatible API |
| Scheduling | APScheduler and GitHub Actions cron |
| Push notifications | Expo Push Service |
| Testing | pytest |
| Linting/formatting | Ruff |
| Containers | Docker and Docker Compose |
| Hosting | Render, Neon and GitHub Actions |
| API documentation | OpenAPI and Swagger |

## Architectural Flow

```text
Mobile application
       |
       | HTTPS, JWT bearer authentication
       v
FastAPI route
       |
       v
Pydantic validation
       |
       v
Service/domain logic
       |
       v
SQLAlchemy and PostgreSQL
```

### Request Flow

1. A mobile client calls an API endpoint.
2. Request-context middleware adds a traceable request ID.
3. Pydantic validates request bodies and response schemas.
4. Authentication dependencies extract and verify JWT credentials.
5. Routes remain thin and delegate work to service modules.
6. Services execute business rules and database operations.
7. SQLAlchemy persists or retrieves domain data.
8. Pydantic serializes the final response.

### AI Plan Flow

1. The authenticated user submits a plan-generation request.
2. Their profile is loaded from PostgreSQL.
3. A versioned prompt is constructed.
4. The Gemini-compatible endpoint is called using HTTPX.
5. The raw response is cleaned and parsed as JSON.
6. Pydantic validates the result against a strict plan schema.
7. Invalid responses are retried.
8. The plan, plan items and generation metadata are persisted.
9. Any earlier active plan is changed to inactive.
10. The API returns the newly generated plan.

### Reminder Flow

1. GitHub Actions invokes the reminder job every 15 minutes.
2. The job compares reminder settings with each user's local timezone.
3. The database ledger claims the reminder for that local date.
4. The user is notified only if reminders are enabled, the local time is in the reminder window, and no plan work is already logged for that day.
5. Expo receives the push payload.
6. A unique database constraint prevents duplicate sends.

## Main API Areas

| Area | Responsibilities |
|---|---|
| `/auth` | Signup, login, refresh tokens |
| `/users` | Account retrieval, update and deletion |
| `/onboarding` | User goals and fitness preferences |
| `/plan` | AI plan generation and weekly checklist |
| `/logs` | Completion logging and undo |
| `/progress` | Streak and chart data |
| `/notifications` | Expo push-token registration |
| `/health` | Application and database health |

## Data Models

### `User`

- Unique email
- Optional display name
- Argon2 password hash
- Creation timestamp
- Owns profile, plans, logs, push tokens and reminder sends
- Relationships use cascading deletion

### `Profile`

- User identity
- Goal
- Fitness level
- Dietary preference
- Available equipment
- Timezone
- Preferred reminder time
- Reminder opt-in status
- Onboarding completion status

### `Plan`

- Belonging user
- Active or inactive status
- Generation timestamp
- Prompt version
- LLM model name
- Raw LLM response for debugging
- Seven-day ordered plan items
- Database partial unique index ensures only one active plan per user

### `PlanItem`

- Parent plan
- Day from Monday (`0`) through Sunday (`6`)
- Position within the day
- Item type
- Title
- Description
- Optional target metric

### `Log`

- User
- Plan item
- User-local completion date
- Actual metric value, if present
- Completion timestamp
- Unique constraint prevents duplicate completion for the same item and date

### `PushToken`

- Registered Expo push token
- Owning user
- Registration timestamp
- Tokens are unique across accounts

### `ReminderSend`

- User
- Local date
- Claim timestamp
- Unique user/date constraint makes reminder delivery idempotent

### `LoginFailure`

- Email
- Failure timestamp
- No foreign key, allowing attempts against nonexistent accounts
- Used for login throttling without enabling account enumeration

## Database and Consistency Decisions

The project relies heavily on database constraints rather than application-only checks:

- Unique email addresses
- One profile per user
- One active plan per user
- One completion per plan item per user per local day
- One reminder claim per user per local day
- Unique Expo push tokens
- Cascading deletion for account removal
- Enums and day-of-week constraints
- Indexed queries for streak and progress calculations

Streaks are derived from completion logs rather than stored. A completion is associated with a plan item, allowing historical progress to remain correct even if a plan is regenerated.

## Design Highlights

- **Layered architecture:** routes, schemas, services and models have separate responsibilities.
- **User-scoped authorization:** every query is tied to the authenticated user.
- **No user-ID guessing:** unrelated resources return 404 rather than revealing existence.
- **Timezone-aware dates:** the user's local date drives streaks and reminder logic.
- **Idempotency:** database constraints support retries and accidental duplicate requests.
- **LLM as untrusted input:** AI output is cleaned, validated and retried.
- **Traceable requests:** every request receives an `X-Request-ID`.
- **Configuration validation:** production refuses unsafe or incomplete configuration.
- **Tests at external boundaries:** LLM and Expo integrations are replaced with fakes.
- **Committed API contract:** CI verifies that the exported OpenAPI file matches the application.
- **Reproducible dependencies:** direct dependencies are separate from universal locked dependencies.

## Testing and CI

The test suite covers authentication and refresh tokens, login throttling, onboarding, plan generation and schema validation, progress and streak calculations, logs and idempotency, push notifications, reminder scheduling, configuration validation, OpenAPI contract consistency, database migrations, observability and health endpoints.

GitHub Actions performs pytest and Ruff checks, migration upgrade/downgrade testing against PostgreSQL, model/migration consistency checks, Docker image builds, dependency vulnerability audits, OpenAPI contract validation and scheduled reminder execution.

## Deployment

- **Render** runs the FastAPI container.
- The Docker startup command applies Alembic migrations before launching Uvicorn.
- **Neon** provides PostgreSQL.
- **GitHub Actions** executes reminder sweeps because the web instance may sleep.
- The application runs as a non-root container user.
- Production configuration guards reject weak secret keys.

## Interview Questions and Answers

### 1. How does the project separate HTTP handling from business logic?

**Answer:** FastAPI routes in `app/api/routes` handle authentication, request extraction and HTTP responses. Pydantic schemas validate inputs and outputs. Domain operations live in `app/services`, while `app/models` represent database entities. This keeps route methods small and makes business logic reusable and testable.

### 2. Why did you use Pydantic to validate LLM output?

**Answer:** LLM output is non-deterministic and should be treated as untrusted input. Pydantic validates required fields, types and constraints. The raw response is cleaned and parsed, invalid plans trigger retries, and only a validated plan is written to PostgreSQL.

### 3. How does the system ensure one active plan per user?

**Answer:** The `plans` table has a PostgreSQL/SQLite partial unique index that is active only when `status = 'active'`. Database-level enforcement prevents two active plans even if concurrent requests reach the service.

### 4. How does completion logging prevent duplicates?

**Answer:** The `logs` table has a unique constraint over `(user_id, plan_item_id, log_date)`. This makes completion creation idempotent. Double clicks or retried requests cannot create duplicate records.

### 5. How are streaks calculated?

**Answer:** Streaks are derived from completion rows, not stored in a separate mutable counter. The service retrieves the user's logs and calculates consecutive active local dates. This prevents streak counters from drifting away from actual completion data.

### 6. What problem does timezone-aware date handling solve?

**Answer:** The server determines the user's current date using their profile timezone. This prevents clients with incorrect clocks from creating or undoing completions on the wrong date and ensures reminders operate against local dates.

### 7. Why does every plan item belong to a plan?

**Answer:** This preserves history. Completion logs reference plan items, so regenerating or replacing a plan does not rewrite previously completed history. Historical progress can be evaluated against the plan that was active for that day.

### 8. How does the reminder system avoid duplicate notifications?

**Answer:** The system creates a `ReminderSend` ledger row for the user and their local date. A unique database constraint enforces one claim per user and date. Concurrent or late cron executions fail safely when claiming an already-used row.

### 9. How is authentication implemented?

**Answer:** The application hashes passwords with Argon2 through pwdlib. Login returns short-lived access JWTs and refresh JWTs signed using the configured secret and HS256. Protected routes verify the access token and derive the user from the JWT subject.

### 10. How is login throttling designed?

**Answer:** Failed login attempts are recorded for email addresses, including nonexistent emails. Once five failures occur in 15 minutes, additional attempts receive HTTP 429 with a `Retry-After` response. Recording nonexistent accounts prevents username enumeration, and blocked attempts are not counted as permanent lockouts.

### 11. How does account deletion work?

**Answer:** Deleting a user cascades through SQLAlchemy relationships and foreign keys. Profiles, plans, items, logs, push tokens and reminder records are removed, preventing orphaned personal data.

### 12. Why can users receive 404 instead of 403 for another user's resource?

**Answer:** The API scopes every database query to the authenticated user and does not accept arbitrary user IDs. Returning 404 avoids confirming whether a particular resource or identifier exists, which reduces information disclosure.

### 13. How does the database deployment migration work?

**Answer:** The Docker startup command runs `alembic upgrade head` before starting Uvicorn. CI separately verifies upgrades, downgrade/upgrade cycles and agreement between SQLAlchemy models and migration state.

### 14. How would you improve plan generation for scale?

**Answer:** I would move generation to an asynchronous job: return HTTP 202 immediately, create a task with `pending` status, process it through a queue or worker, store the result and status, and let the client poll or use WebSockets/SSE. I would also add provider timeouts, exponential backoff, circuit-breaking and appropriate caching.

### 15. What is missing for production-grade push delivery?

**Answer:** Expo push tickets are sent, but delivery receipts are not yet polled. A receipt worker should process delivery failures and remove invalid or inactive push tokens. The system should also enforce provider rate limits and use exponential backoff.

### 16. How do you prevent secrets from leaking?

**Answer:** Configuration is read from environment variables. The repository includes only `.env.example`, while actual secrets are supplied at runtime. The Docker image does not copy the local environment file, and production startup rejects an insufficient secret key.

### 17. How does request tracing help debugging?

**Answer:** Middleware assigns or reads a request identifier and returns it as `X-Request-ID`. The identifier is attached to application logs, allowing operators to correlate an API response with database or external-service actions associated with that request.

### 18. How would you test this system?

**Answer:** pytest provides isolated in-memory SQLite databases for unit and integration tests. External dependencies such such as Gemini and Expo are replaced with fakes. PostgreSQL-specific behavior is additionally verified by CI migrations and database checks. Ruff provides linting and formatting validation.

### 19. How are dependencies made reproducible?

**Answer:** `requirements.in` and `requirements-dev.in` contain direct dependencies. Universal lock files contain pinned transitive dependencies. CI audits pinned versions for known vulnerabilities.

### 20. What are the largest known limitations?

**Answer:** Plan generation is synchronous, which can cause a slow HTTP request. Push delivery receipts are not processed. The free hosting tier can have cold starts, and there is currently no in-process queue or dedicated worker infrastructure for long-running AI work.

## Project Summary for a CV or Interview

> Developed a Python/FastAPI backend for an AI-powered habit and fitness coach. Implemented JWT authentication with Argon2 password hashing, SQLAlchemy/PostgreSQL persistence, Alembic migrations, strict Pydantic schemas, and Gemini-based personalized plan generation. Designed timezone-aware streak and progress calculations, database-level idempotency, login throttling, Expo push reminders, account deletion, structured request tracing and scheduled jobs. Added Docker deployment, GitHub Actions CI/CD, PostgreSQL migration testing, OpenAPI contract validation and an extensive pytest suite.
