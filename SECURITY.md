# Security

## Protect the bot token

- Keep `DISCORD_TOKEN` only in your local `.env` file. Never paste it into issues, screenshots, chat, or commits.
- If the token is exposed, reset it immediately in the Discord Developer Portal and update the local `.env`.
- Do not run Clipy from an untrusted fork or install unreviewed code while the token is present.

## Run with limited access

- Give the bot only the Discord permissions it actually needs; avoid Administrator.
- Enable Message Content Intent only if you use prefix and mention commands.
- Keep Python, `discord.py`, `yt-dlp`, and FFmpeg updated.
- Run the bot as a normal user, not root, and keep the host OS and Termux packages updated.
- Do not expose a remote shell, file browser, or token-containing `.env` through a public web server.

## Reporting a vulnerability

Do not publish working exploit details or secrets in a public issue. Contact the repository maintainer privately first.

## Current safeguards

- Commands accept only explicitly supported HTTPS download hosts.
- Download links with credentials, non-standard ports, or unapproved hosts are rejected.
- Download options are restricted to the person who invoked the command.
- Search and download commands have cooldowns; temporary download files are removed after sending.
- These checks reduce risk but do not guarantee that the bot cannot be compromised. Review dependency alerts and logs regularly.