# ◈ Clipy

Clipy is a Discord clip-finder bot built with Python, discord.py, and Discord Components V2. It searches YouTube for scenes and videos and displays interactive, paginated results.

## Current features

- /clip search clip:<keywords> — search YouTube for a scene or video.
- /clip random — search a random anime-scene query.
- /clip sources — show supported search sources.
- /clip help — command guide.
- /ping — check bot latency.
- Components V2 interface; no embeds.
- Query validation, timeout handling, and useful error messages.

Important: this version returns source/watch links, not guaranteed direct download links. It searches metadata only and does not download or rehost videos. YouTube is currently the only integrated search source.

## Requirements

- Python 3.10 or newer (Python 3.11+ recommended).
- A Discord application and bot token.

## Setup

1. Clone this repository: https://github.com/flame-land/clipy
2. Install dependencies with: python -m pip install -r requirements.txt
3. Copy .env.example to .env.
4. Put your Discord bot token in .env as DISCORD_TOKEN=your_token_here.
5. Optional: set DEV_GUILD_ID to your test server ID for faster command sync during development.
6. Start the bot with: python main.py

Never commit your real .env file or share your bot token. If a token is exposed, reset it in the Discord Developer Portal immediately.

## Invite the bot

In the Discord Developer Portal, open OAuth2 → URL Generator and select the bot and applications.commands scopes. Invite it to your server. Administrator permission is not required.

## Project structure

- main.py — bot startup and slash-command sync
- cogs/clip.py — slash commands
- services/search.py — YouTube search adapter
- utils/components.py — Components V2 layouts
- requirements.txt — Python dependencies
- .env.example — safe configuration template

## Roadmap

- Add more supported search providers.
- Deduplicate and rank results across providers.
- Add provider-approved direct-download support where available.
- Add tests and CI checks.
- Add opt-in saved clips and search history.

## Responsible use

Respect each platform's terms, copyright rules, and content-owner permissions. Clipy currently links to source pages and does not download or rehost media.

## License

No license has been selected. Standard copyright applies until a license is added; do not assume the code is licensed for reuse.
