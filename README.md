# Clipy

Clipy is a Discord clip-finder bot. It searches YouTube for short clips, shows thumbnail previews, and can send the first 60 seconds of supported public video links as attachments.

## Commands

Slash commands:
- `/clip search` — search YouTube for a scene or clip.
- `/clip random` — search a random anime-scene query.
- `/clip sources` — show search and download sources.
- `/clip help` — command guide.
- `/clip ping` — check gateway latency.
- `/download link:<URL>` — choose download type, quality, and format.

Prefix commands (default prefix is `!`):
- `!clip search goku black`
- `!clip random`
- `!clip sources`
- `!download https://...`
- `!help`
- `!ping`

Mention commands also work, for example: `@Clipy clip search goku black`. Enable Message Content Intent in the Discord Developer Portal for prefix and mention commands.

## Downloads

After running `/download` or `!download`, use the interactive menus to choose the type, quality, and format.

- Only the first 60 seconds are processed, even when the source video is longer.
- Video quality: best available, 1080p, 720p, 480p, or 360p.
- Video format: MP4 or WebM.
- Audio format: MP3 or M4A.
- Audio quality: 128, 192, or 320 kbps.

The final file must fit Discord's upload limit. Clipy uses the server's reported attachment limit when available and a 100 MB fallback in DMs. If a file is too large, select a lower quality. Large files can take longer to process.

Clipy installs `imageio-ffmpeg`, which provides a bundled FFmpeg executable on supported platforms. On Termux, install the native FFmpeg package too:

    pkg install ffmpeg -y

Some hosts or media operations may still require a compatible system FFmpeg/ffprobe installation. FFmpeg availability depends on the host platform and package wheel.

Supported public-link download sources include YouTube, Instagram, Facebook/fb.watch, TikTok, Vimeo, Reddit, X/Twitter, Dailymotion, Streamable, Twitch clips, Pinterest, and Tumblr. This is not every website on the internet: support depends on yt-dlp's extractors and each site's current behavior. Search currently searches YouTube only. Search results include thumbnails and are filtered to clips with known durations of 60 seconds or less.

Private, restricted, unavailable, or unsupported content may fail. Files are temporary and are deleted after sending. Only download content you have permission to use; Clipy does not bypass access controls or DRM.

## Setup in Termux

    pkg update
    pkg install git python ffmpeg -y
    git clone https://github.com/flame-land/clipy.git
    cd clipy
    python -m pip install -r requirements.txt
    cp .env.example .env
    nano .env
    python main.py

Set `DISCORD_TOKEN` in your local `.env`. Never commit or share your real token.

## Configuration

- `BOT_PREFIX`: prefix for text commands; default `!`.
- `DEV_GUILD_ID`: optional test server ID for faster slash-command syncing.
- `BOT_STATUS`: `online`, `idle`, `dnd`, or `invisible`.
- `BOT_ACTIVITY_TYPE`: `playing`, `listening`, `watching`, `competing`, or `streaming`.
- `BOT_ACTIVITY_MESSAGES`: activity texts rotated in order, separated by `|` (example: `/clip search|anime clips|!help`).
- `BOT_ACTIVITY_INTERVAL`: seconds between activity messages; minimum 15, default 30.
- `BOT_ACTIVITY_NAME`: fallback activity text if `BOT_ACTIVITY_MESSAGES` is empty.
- `BOT_STREAM_URL`: Twitch or YouTube URL, required for streaming activity.

Example local `.env` configuration:

    BOT_STATUS=online
    BOT_ACTIVITY_TYPE=listening
    BOT_ACTIVITY_MESSAGES=/clip search|anime clips|!help
    BOT_ACTIVITY_INTERVAL=30

Discord bots cannot set a mobile client status. This rotates the bot's standard Discord activity; it does not create Rich Presence buttons or custom assets. Change the bot's username, avatar, and About Me/profile details in the Discord Developer Portal.
