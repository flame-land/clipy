# Clipy Web Dashboard

A separate Flask web service for Discord OAuth login, server selection, bot invitation, and temporary generated download links. It runs separately from the Discord bot process.

## User flow

1. Open the website and choose **Get started with Discord**.
2. Sign in through Discord OAuth (`identify` + `guilds` scopes).
3. Choose a server where the signed-in user has **Manage Server** or **Administrator** permission.
4. If Clipy is not installed there, use **Add bot** to open Discord's official invite screen for that server. Return to the dashboard after inviting it.
5. Open that server's dashboard, paste a supported public video URL, and wait for processing.
6. Copy the generated temporary link and use it to download the file. Website downloads are not constrained by Discord's attachment limit, but the web host's storage, bandwidth, time, and configured size/duration limits still apply.

## Environment variables

Configure these in the **web service**, not only in the Discord bot service:

- `DISCORD_CLIENT_ID`: Discord application's client ID (same application as the bot).
- `DISCORD_CLIENT_SECRET`: Discord OAuth2 client secret. Never commit it.
- `DISCORD_TOKEN`: bot token. Never commit it or expose it in browser code.
- `WEB_SESSION_SECRET`: a long random secret used to sign browser sessions. Example generator: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
- `PUBLIC_BASE_URL`: public HTTPS origin, e.g. `https://clipy.example.com`, without a trailing slash.
- `COOKIE_SECURE=1`: use secure cookies on HTTPS production sites. For local-only HTTP development, set `COOKIE_SECURE=0`.
- Optional: `PORT` (default `8080`), `CLIPY_WEB_DATA` (persistent writable data directory), `DOWNLOAD_LINK_TTL_SECONDS` (default `86400`), `MAX_DOWNLOAD_BYTES` (default 2 GiB), `MAX_DOWNLOAD_SECONDS` (default 3600), `TRUST_PROXY=1` only behind a correctly configured trusted reverse proxy.

## Discord Developer Portal

1. Open the same Discord application that owns Clipy.
2. Under **OAuth2**, add the exact redirect URI `https://YOUR-DOMAIN/callback` (replace with your real HTTPS domain).
3. Copy the OAuth2 client ID and client secret into the web service environment.
4. Ensure the bot is public if you want other server managers to add it.

The web app requests only `identify` and `guilds` for login/server listing. It does not ask for a user's Discord password. The bot invite uses `bot` + `applications.commands` scopes.

## Run locally

From the repository root, install the website dependencies and set the required environment variables, then run:

```bash
pip install -r website/requirements.txt
python website/app.py
```

For a production web service, use a WSGI server, for example:

```bash
gunicorn --chdir website --bind 0.0.0.0:${PORT:-8080} app:app
```

Use a host with persistent writable disk for `CLIPY_WEB_DATA`; otherwise generated files and login sessions can disappear when the service restarts. Do not use Flask's development server for public production traffic.

## Dashboard settings

Each server dashboard has its own saved download settings:

- Output format: best available/original, MP4 video, or MP3 audio only.
- Maximum video duration: 1–60 minutes, bounded by `MAX_DOWNLOAD_SECONDS`.
- Maximum file size: 50–2048 MB, bounded by `MAX_DOWNLOAD_BYTES`.
- Generated link expiry: 1 hour to 7 days.

These settings are stored in the website SQLite database and apply to downloads initiated for that server. Hosting-wide caps always win. MP4/MP3 conversion requires FFmpeg, supplied through `imageio-ffmpeg`; some sources may not offer a compatible format.

## Generated file links

Links use random, unguessable tokens and expire after the configured TTL. Files are stored on the web host, not sent through Discord. The default processing limits are 2 GiB and one hour; adjust only to limits your host can safely support. You are responsible for complying with source-site terms, copyright rules, and having permission to download the content. Private/restricted content may fail. A host's available disk, memory, CPU, bandwidth, and platform restrictions remain real limits.

## Important deployment notes

- Run the website and bot as separate services/processes; do not replace `main.py` with this app.
- Keep the bot token, OAuth secret, and session secret in environment variables or your host's secret manager.
- Use HTTPS. Do not set `COOKIE_SECURE=0` on a public HTTPS deployment.
- Set a disk quota and monitor bandwidth: video processing is resource-intensive.
- Back up or persist the `website/data` directory if you want sessions and generated files to survive deploys.
