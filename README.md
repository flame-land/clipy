# Clipy

Clipy is a Discord clip-finder bot that searches YouTube for clips up to 60 seconds, shows thumbnail previews, and can send the first 60 seconds of supported public video links as attachments.

## Commands

Slash commands:
- /clip search — search for a scene or video.
- /clip random — search a random anime-scene query.
- /clip sources — show supported sources.
- /clip help — command guide.
- /download link:<URL> — choose download type, quality, and format.
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

After running `/download` or `!download`, use the interactive menus to choose the type, quality, and format.

- Only the first 60 seconds are downloaded, even when the source video is longer.
- Video quality: best available, 1080p, 720p, 480p, or 360p.
- Video format: MP4 or WebM.
- Audio format: MP3 or M4A.
- Audio quality: 128, 192, or 320 kbps.

Clipy allows larger downloads than the previous 25 MB fallback and gives the download more time to finish. The actual file still has to fit Discord's upload limit; the bot uses the server's reported limit when available and a 100 MB fallback in DMs. If a file won't fit, choose a lower quality or shorter clip. Large files can take longer, and audio conversion requires FFmpeg installed on the machine running Clipy.

Supported public clip links include YouTube, Instagram, Facebook/fb.watch, TikTok, Vimeo, Reddit, X/Twitter, Dailymotion, Streamable, Twitch clips, Pinterest, and Tumblr. This is not every website on the internet; availability depends on yt-dlp extractor support and each site's current behavior. Search currently searches YouTube only. Search results show thumbnails and are filtered to clips with known durations of 60 seconds or less. Downloads are trimmed to the first 60 seconds and require FFmpeg. Private, restricted, unavailable, or unsupported content may fail. Files are temporary and are deleted after sending. Use this only for content you have permission to download; Clipy does not bypass access controls or DRM.

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

- `BOT_PREFIX`: prefix for text commands; default `!`.
- `DEV_GUILD_ID`: optional test server ID for faster slash-command syncing.
- `BOT_STATUS`: online, idle, dnd, or invisible.
- `BOT_ACTIVITY_TYPE`: playing, listening, watching, competing, or streaming.
- `BOT_ACTIVITY_MESSAGES`: activity texts rotated in order, separated by `|` (for example `/clip search|anime clips|!help`).
- `BOT_ACTIVITY_INTERVAL`: seconds between activity messages; minimum 15, default 30.
- `BOT_ACTIVITY_NAME`: fallback activity text if `BOT_ACTIVITY_MESSAGES` is empty.
- `BOT_STREAM_URL`: Twitch or YouTube URL, required for streaming activity.

Example local `.env` configuration:

    BOT_STATUS=online
    BOT_ACTIVITY_TYPE=listening
    BOT_ACTIVITY_MESSAGES=/clip search|anime clips|!help
    BOT_ACTIVITY_INTERVAL=30

Discord bots cannot set a mobile client status. This rotates the bot's standard Discord activity; it does not create Discord Rich Presence buttons or custom assets. Change the bot's global username, avatar, and About Me/profile details in the Discord Developer Portal; these are not changed by this configuration file.
