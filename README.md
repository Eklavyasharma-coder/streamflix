# StreamFlix Plus — Flask full-stack demo

This is an upgraded local-first Flask project with advanced catalogue filters, optional TMDB metadata import, YouTube trailers, accounts, watch history/progress, watchlist, ratings/reviews, a protected admin dashboard, genre-based recommendations, and responsive CSS.

## Requirements
- Python 3.10+
- Internet connection for optional TMDB and poster images
- A TMDB API key is optional. TMDB metadata does **not** grant rights to stream films.

## Windows / VS Code setup
1. Extract the ZIP.
2. Open the `streamflix_plus` folder in VS Code.
3. Open Terminal → New Terminal.
4. Create a virtual environment:
   ```powershell
   py -m venv .venv
   ```
5. Activate it:
   ```powershell
   .\\.venv\\Scripts\\Activate.ps1
   ```
   If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, then activate again.
6. Install packages:
   ```powershell
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   ```
7. Optional: copy `.env.example` to `.env` and set values. Flask does not automatically load `.env` in this version; either set environment variables in the terminal or install `python-dotenv` and add `from dotenv import load_dotenv; load_dotenv()` near the top of `app.py`.
   For a quick local TMDB key in PowerShell:
   ```powershell
   $env:TMDB_API_KEY="your_tmdb_v3_api_key"
   ```
8. Run:
   ```powershell
   python app.py
   ```
9. Open http://127.0.0.1:5000

## Local admin
Default local admin:
- Email: `admin@streamflix.local`
- Password: `ChangeMe123!`

Change these before sharing the app. The admin account is created on first database initialization. If you change the environment variables later, the existing account password is not automatically reset.

## Main routes
- `/` home and personalized genre recommendations
- `/movies` search and filters
- `/movie/<id>` detail, trailer, reviews
- `/register`, `/login`, `/profile`
- `/watch/<id>` demo player and progress tracking
- `/my-list` watchlist
- `/admin` admin dashboard
- `/admin/tmdb?q=...` search/import TMDB metadata

## Database
SQLite is created automatically at first run (`instance/streamflix.db`). Tables: `user`, `movie`, `watch_history`, `review`. This project uses `db.create_all()` for a fresh local setup. For an existing database with an older schema, back it up first; `create_all()` does not alter existing tables. This starter does not include migration tooling.

## Video notes
The sample Big Buck Bunny clip is a public sample video, not a movie catalogue. Add only video URLs you own or are licensed to distribute. For production, store media in object storage/CDN and consider HLS/DASH; do not store video files in the relational database.

## Important production work still needed
- Replace the development secret and default admin password.
- Add CSRF protection, rate limiting, email verification/password reset, moderation/reporting, and tests.
- Use migrations (Flask-Migrate/Alembic) for schema changes.
- Use PostgreSQL in production and persistent storage for uploads; configure HTTPS, secure cookies, backups, and CORS if building a separate Flutter client.
- Watchlist is a simple local cookie-backed starter feature; migrate it to a database table before multi-device syncing.
- For Flutter, build a separate mobile client that consumes authenticated JSON APIs. This package is the web app, not a finished Android APK.
