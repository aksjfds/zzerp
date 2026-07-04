# Development baseline

## Runtime

- Backend: Python 3.10 or newer, with packages from `backend/requirements.txt` available in the active environment.
- Frontend: Node.js and pnpm versions compatible with `frontend/package.json`.
- This project does not require or manage a Python virtual environment.

## Checks

- Backend import and route check: `pnpm run b:check`
- Frontend type check: `pnpm --dir frontend type-check`

The backend check imports the application but does not start a server or connect to the database.

## Database policy

During the current development phase, database schema changes use a destructive rebuild from `zzerp.sql`.
Existing database data is not migrated or preserved. Rebuilding a database is an explicit manual operation and is
not performed by application startup or check commands.

## Deferred tooling

Automated tests, lint configuration, migrations, and isolated PostgreSQL validation are intentionally deferred.
