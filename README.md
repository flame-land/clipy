# Clipy

Clipy is a Discord clip-finder bot that searches YouTube and can send supported public videos as attachments.

## Commands

Slash commands:
- /clip search — search for a scene or video.
- /clip random — search a random anime-scene query.
- /clip sources — show supported sources.
- /clip help — command guide.
- /download link:<URL> — download a public video.
- /ping — check latency.

Prefix commands (default prefix is !):
- !clip search goku black
- !clip random
- !clip sources
- !download https://...
- !help
- !ping

Mention commands also work, for example: @Clipy download https://...

## Download support

Allowed hosts: YouTube, Instagram, Facebook/fb.watch, and TikTok. The link must be public and downloadable without login. Each download is limited to 8 MB to fit typical Discord upload limits. Private, restricted, unsupported, or larger videos may fail. Downloads are temporary and are deleted after being sent. Use this only for content you have permission to download; Clipy does not bypass access controls or DRM.

## Setup in Termux

    pkg update
    pkg install git python -y
    git clone https://github.com/flame-land/clipy.git
    cd clipy
    python -m pip install -r requirements.txt
    cp .env.example .env
    nano .env
    python main.py

Set DISCORD_TOKEN in your local .env. Enable Message Content Intent in the Discord Developer Portal for prefix and mention commands. Never commit or share your real token.

## Configuration

- BOT_PREFIX: prefix for text commands; default !.
- DEV_GUILD_ID: optional test server ID for faster slash-command syncing.
- BOT_STATUS: online, idle, dnd, or invisible.
- BOT_ACTIVITY_TYPE: playing, listening, watching, competing, or streaming.
- BOT_ACTIVITY_NAME: text shown in the activity.
- BOT_STREAM_URL: Twitch or YouTube URL, required for streaming activity.

Discord bots cannot set a mobile client status. Change the bot's global username, avatar, and About Me/profile details in the Discord Developer Portal; these are not changed by this configuration file.
