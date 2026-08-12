# Preprint Bot – Django Web Interface

A Django conversion of the Streamlit-based Preprint Bot frontend.  
Connects to the **same PostgreSQL database** used by the FastAPI backend.

## Architecture

```
                         ┌─────────────────────┐
                         │   PostgreSQL         │
                         │   (preprint_bot DB)  │
                         └──────┬──────┬────────┘
                                │      │
                 ┌──────────────┘      └──────────────┐
                 │                                    │
        ┌────────▼────────┐                 ┌─────────▼────────┐
        │  FastAPI Backend │                 │  Django Website   │
        │  (pipeline, API) │                 │  (this project)   │
        └─────────────────┘                 └──────────────────┘
```

Both the FastAPI backend (which runs the recommendation pipeline) and this
Django site read/write the same tables. Django models are fully managed
and create the schema via `makemigrations` / `migrate`.

> **Important:** The initial migration is designed for a **fresh database**.
> If you have an existing database from the pre-Django Streamlit/FastAPI setup,
> you have two options:
> 1. **Fresh start** — create a new database with `setup_database.sh` and
>    run `python manage.py migrate`. Re-create users via `createsuperuser`.
> 2. **Adopt existing** — run `python manage.py migrate --fake-initial` to
>    tell Django the tables already exist. You may need to manually reconcile
>    schema differences (e.g. the `users.password` column replacing
>    `users.password_hash`).

## Prerequisites

- **Python 3.10+**
- **PostgreSQL 16** with the **pgvector** extension

### Installing PostgreSQL (Ubuntu / WSL)

If you don't already have PostgreSQL installed:

```bash
# Add the official PostgreSQL apt repository
sudo apt install -y curl ca-certificates
sudo install -d /usr/share/postgresql-common/pgdg
sudo curl -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
    --fail https://www.postgresql.org/media/keys/ACCC4CF8.asc

echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] \
    https://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" \
    | sudo tee /etc/apt/sources.list.d/pgdg.list

# Install PostgreSQL 16 + pgvector
sudo apt update
sudo apt install -y postgresql-16 postgresql-16-pgvector

# Start the service (WSL doesn't use systemctl)
sudo pg_ctlcluster 16 main start

# Set a password for the postgres superuser
sudo -u postgres psql -c "ALTER USER postgres WITH PASSWORD 'your-pg-password';"
```

### macOS

```bash
brew install postgresql@16
brew services start postgresql@16
brew install pgvector
```

## Quick Start

```bash
# 1. Set up the database (run from the project root)
chmod +x setup_database.sh
./setup_database.sh
#    → prompts for DB name, user, password, etc.
#    → creates the database, user, and extensions
#    → writes django_site/.env

# 2. Create a virtual environment and install dependencies
cd django_site
python3 -m venv venv
source venv/bin/activate          # On Windows WSL this is the same
pip install -r requirements.txt

# 3. Run migrations (creates all tables)
python manage.py migrate

# 4. Create an admin/site account (one login for both /admin/ and the site)
python manage.py createsuperuser

# 5. Start the dev server
python manage.py runserver 0.0.0.0:8001
```

Visit http://localhost:8001 to use the site, or http://localhost:8001/admin/
to browse data.

> **Note:** The initial migration is shipped in `core/migrations/0001_initial.py`.
> You only need to run `makemigrations core` if you change `models.py` later.

> **WSL note:** PostgreSQL won't auto-start when you open a new terminal.
> Run `sudo pg_ctlcluster 16 main start` each time, or add it to your
> `~/.bashrc`.

## Environment Variables

| Variable             | Default              | Description                         |
|----------------------|----------------------|-------------------------------------|
| `DATABASE_NAME`      | `preprint_bot`       | PostgreSQL database name            |
| `DATABASE_USER`      | `postgres`           | PostgreSQL user                     |
| `DATABASE_PASSWORD`  | (empty)              | PostgreSQL password                 |
| `DATABASE_HOST`      | `localhost`          | PostgreSQL host                     |
| `DATABASE_PORT`      | `5432`               | PostgreSQL port                     |
| `DJANGO_SECRET_KEY`  | (dev fallback)       | Set a real key in production        |
| `DJANGO_DEBUG`       | `True`               | Set to `False` in production        |
| `PDF_DATA_DIR`       | `../pdf_data`        | Root of the PDF storage tree        |
| `PAPER_STORAGE_DIR`  | `{PDF_DATA_DIR}/papers` | Hash-based deduplicated paper storage |
| `SUPPORT_EMAIL`      | `support@example.com`| Shown on the help page              |
| `SITE_NAME`          | `Preprint Bot`       | Site display name                   |
| `SHOW_BETA_BANNER`   | `True`               | Dismissable beta feedback banner    |
| `ARXIV_SEARCH_MAX_RESULTS` | `500`          | Max papers returned by arXiv search |
| `ARXIV_SEARCH_PER_PAGE`    | `50`           | Results per page in arXiv search    |
| `ACCENT_COLOR`             | (empty)        | CSS accent color override, e.g. `#e65100` |
| `NAV_COLOR`                | (empty)        | Navbar background color override, e.g. `#1b5e20` |
| `REGISTRATION_OPEN`        | `True`         | Set to `False` to block new account creation |
| `REQUIRE_EMAIL_VERIFICATION` | `False`      | Require email verification on registration |
| `DEFAULT_FROM_EMAIL` | `noreply@localhost`  | Sender address for verification/reset emails |
| `EMAIL_HOST`         | (none)               | SMTP host — enables SMTP backend when set |
| `EMAIL_PORT`         | `587`                | SMTP port                                   |
| `EMAIL_USER`         | (empty)              | SMTP login username                         |
| `EMAIL_PASSWORD`     | (empty)              | SMTP login password                         |
| `EMAIL_FROM_ADDRESS` | `noreply@localhost`  | Sender address (shared with FastAPI config) |
| `EMAIL_FROM_NAME`    | value of `SITE_NAME` | Sender display name                         |
| `ORCID_CLIENT_ID`    | (empty)              | ORCID OAuth2 app ID — enables ORCID sign-in when set |
| `ORCID_CLIENT_SECRET`| (empty)              | ORCID OAuth2 app secret                     |
| `ORCID_SANDBOX`      | `False`              | Use sandbox.orcid.org for development       |

## Local Settings

For production or per-developer overrides, copy the example file:

```bash
cp preprint_bot_web/local_settings.py.example preprint_bot_web/local_settings.py
```

Edit `local_settings.py` to set `SECRET_KEY`, `DEBUG = False`,
`ALLOWED_HOSTS`, database credentials, etc. This file is imported last
in `settings.py` and overrides anything above it. It is excluded from
version control via `.gitignore`.

## Project Structure

```
django_site/
├── manage.py
├── requirements.txt
├── .gitignore
├── preprint_bot_web/          # Django project package
│   ├── settings.py
│   ├── local_settings.py.example
│   ├── urls.py
│   └── wsgi.py
└── core/                      # Main application
    ├── models.py              # ORM models (fully managed by Django)
    ├── views.py               # All view functions
    ├── urls.py                # URL routing
    ├── forms.py               # Django forms
    ├── tests/                 # Unit test package (run with `manage.py test core`)
    ├── auth_backend.py        # Auth helper wrappers around Django's built-in auth
    ├── orcid.py               # ORCID OAuth2 helpers
    ├── arxiv_categories.py    # Category tree data + helpers
    ├── context_processors.py  # Template context helpers
    ├── admin.py               # Django admin registration
    ├── management/commands/cleanup_orphan_papers.py
    ├── static/core/style.css  # Site-wide styles
    └── templates/
        ├── base.html          # Shared layout, nav, CSS
        ├── dashboard.html
        ├── settings.html
        ├── help.html
        ├── auth/
        │   ├── login.html
        │   ├── register.html
        │   ├── forgot_password.html
        │   └── reset_password.html
        ├── profiles/
        │   ├── list.html      # Profile list + paper management
        │   └── create.html    # Create / edit form + category tree
        └── recommendations/
            └── list.html      # Filtered, paginated, date-grouped
```

## Key Differences from Streamlit

| Aspect              | Streamlit version               | Django version                    |
|---------------------|---------------------------------|-----------------------------------|
| Auth                | Cookie-based API tokens         | Django sessions + ModelBackend    |
| State               | `st.session_state`              | Django sessions + GET params      |
| Category picker     | `st_ant_tree` widget            | Pure JS checkbox tree             |
| Pagination          | `st.rerun()` loop               | Standard `?page=N` GET params     |
| File uploads        | Streamlit `file_uploader`       | Standard `<form enctype=…>`       |
| Real-time progress  | SSE polling                     | Not implemented (use pipeline CLI)|

## Testing

```bash
cd django_site
python manage.py test core -v 2
```

Tests are in the `core/tests/` package. The current suite includes the following:

- **`ParseArxivIdsTests`** — arXiv ID extraction from bare IDs, URLs, versioned
  PDFs, legacy IDs, query strings, comma/newline separation, deduplication.
- **`PaperStorageTests`** — SHA-256 hashing correctness, determinism, and
  hash-based file path format.
- **`CleanCategoriesTests`** — leaf-only category validation, parent group
  rejection, whitespace handling, XSS injection rejection.
- **`AuthFlowTests`** — registration, duplicate/case-insensitive email rejection,
  weak password rejection, login, logout (POST-only), inactive user blocked,
  access control redirects with `?next=` preservation.
- **`ProfileCRUDTests`** — create, edit, delete, duplicate name rejection
  (case-insensitive), category/threshold storage, ownership enforcement (404 on
  another user's profile).
- **`RegisterFormValidationTests`** — password mismatch and Django password
  validator enforcement at the form level.
- **`EmailVerificationOffTests`** — default behavior: register auto-logs in,
  no verification emails sent, unverified users can log in.
- **`EmailVerificationOnTests`** — with `REQUIRE_EMAIL_VERIFICATION=True`:
  registration sends email, blocks auto-login, login rejects unverified users,
  verification link works, invalid tokens rejected, resend flow works.
- **`OrcidDisabledTests`** — button hidden, views redirect when unconfigured.
- **`OrcidLoginTests`** — redirect to ORCID, state token CSRF protection,
  callback with mocked token exchange (existing user login, new user with
  email auto-creates account, email-taken falls through to completion,
  no-email falls through to completion, failed exchange handling).
- **`OrcidCompleteTests`** — email collection, user creation with orcid_id
  and email_verified=True, duplicate email rejection, session cleanup.
- **`PaperUploadDedupTests`** — upload creates Paper + corpus link, duplicate
  hash reuses existing row, same paper shared across profiles, hash-based
  file storage on disk, invalid PDF rejection.
- **`PaperDeleteTests`** — delete removes corpus link but preserves Paper row,
  ownership enforcement.
- **`PaperViewTests`** — serves linked papers, 404 for unlinked or missing.

CI runs these automatically via GitHub Actions (`.github/workflows/test.yml`,
`django-tests` job) using a PostgreSQL + pgvector service container.

## Notes

- The Django site does **not** run the recommendation pipeline itself.
  The FastAPI backend + `preprint_bot` CLI still handle fetching, embedding,
  and generating recommendations. The pipeline processes user papers in a
  paper-centric way (each paper is processed once regardless of how many
  profiles reference it) and queries the database for unprocessed papers
  rather than scanning the filesystem.

- Django's `migrate` creates **all** tables — both the application tables
  (users, profiles, papers, etc.) and Django's own tables (sessions, admin).
  The `database_schema.sql` file from the FastAPI project is no longer needed.

- The arXiv "Add from arXiv" feature downloads PDFs and stores them in a
  hash-based directory structure (`pdf_data/papers/{sha256[:2]}/{sha256}.pdf`).
  Papers are deduplicated by SHA-256 hash — if the same file is added by
  multiple users or to multiple profiles, only one copy is stored on disk.
  A 3-second delay is inserted between consecutive downloads to comply with
  arXiv's rate limit guidelines. Per-request downloads are capped at 10 IDs.

- **Paper deduplication:** Paper rows are linked to corpora via a many-to-many
  relationship (`Paper.corpora`). Removing a paper from a profile only unlinks
  it — the file and database row are preserved as long as other corpora
  reference them. To clean up orphaned papers (no corpus links), run:

  ```bash
  python manage.py cleanup_orphan_papers          # dry run
  python manage.py cleanup_orphan_papers --apply   # actually delete
  ```

- The legacy `Paper.corpus` ForeignKey is kept as a nullable column for
  backward compatibility but is no longer queried. Both Django and the
  pipeline use the `Paper.corpora` ManyToManyField exclusively. The FK
  can be dropped in a future migration once the pipeline is fully verified.

- The arXiv search API endpoint enforces a per-session cooldown (3 seconds
  between searches) to prevent excessive requests to arXiv.

- Profile category validation only accepts leaf arXiv categories (e.g.
  `cs.AI`, `hep-th`), not parent group codes like `cs` or `physics`.

- Email verification is available but off by default. Set
  `REQUIRE_EMAIL_VERIFICATION=True` to require new users to confirm their
  email before signing in. In development, verification links are printed
  to the console (Django's default `console.EmailBackend`). For production,
  set `EMAIL_HOST` in `.env` to enable SMTP — the same env vars
  (`EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`,
  `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`) work for both Django and
  the FastAPI `email_service`, so one `.env` file covers both services.

- **ORCID sign-in** is available as an optional OAuth2 login method.
  To enable it, register an app at https://orcid.org/developer-tools,
  set `ORCID_CLIENT_ID` and `ORCID_CLIENT_SECRET` in `.env`, and add
  `https://your-domain/auth/orcid/callback/` as the redirect URI.
  Set `ORCID_SANDBOX=True` for development against sandbox.orcid.org.
  On first sign-in, the app attempts to read the user's email from their
  ORCID record via the public API — this only works if the user has set
  their email to "public" on orcid.org. If an email is found, the account is created automatically.
  If not, the user is prompted to provide one. ORCID users are
  automatically marked as email-verified. The ORCID button appears on
  the login and register pages only when credentials are configured.
