# Clipy

Clipy is a Discord clip-finder bot that searches YouTube and can send supported public videos or audio as attachments.

## Commands

Slash commands:
- /clip search — search for a scene or video.
- /clip random — search a random anime-scene query.
- /clip sources — show supported sources.
- /clip help — command guide.
- /download link:<URL> — choose video quality or audio format.
- /clip ping — check latency.

Prefix commands (default prefix is !):
- !clip search goku black
- !clip random
- !clip sources
- !download https://...
- !help
- !ping

Mention commands also work, for example: @Clipy download https://...

## Downloads

After running `/download` or `!download`, use the buttons to choose:
- Video: best available, 1080p, 720p, 480p, or 360p.
- Audio: MP3 or M4A.

The maximum file size follows the current Discord server's upload limit (with a small safety margin); downloads in DMs use a conservative fallback. A lower quality is more likely to fit. Large downloads can take longer, and audio conversion requires FFmpeg installed on the machine running Clipy.

Supported links: public YouTube, Instagram, Facebook/fb.watch, and TikTok URLs that can be downloaded without logging in. Private, restricted, unavailable, or unsupported content may fail. Files are temporary and are deleted after sending. Use this only for content you have permission to download; Clipy does not bypass access controls or DRM.

## Setup in Termux

    pkg update
    pkg install git python ffmpeg -y
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
