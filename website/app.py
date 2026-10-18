"""Clipy web dashboard. Run as a separate web service from the Discord bot."""
from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
from pathlib import Path
from urllib.parse import urlencode, urlparse

import requests
import yt_dlp
from flask import Flask, abort, g, redirect, request, send_file, session, url_for
from werkzeug.middleware.proxy_fix import ProxyFix
import imageio_ffmpeg

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = Path(os.getenv("CLIPY_WEB_DATA", str(BASE_DIR / "data"))).resolve()
FILES_DIR = DATA_DIR / "files"
DB_PATH = DATA_DIR / "clipy_web.sqlite3"
DATA_DIR.mkdir(parents=True, exist_ok=True)
FILES_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.secret_key = os.getenv("WEB_SESSION_SECRET", "")
if not app.secret_key:
    raise RuntimeError("Set WEB_SESSION_SECRET to a long random secret before starting the website.")
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.getenv("COOKIE_SECURE", "1") == "1",
    MAX_CONTENT_LENGTH=16 * 1024,
)
if os.getenv("TRUST_PROXY", "0") == "1":
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

DISCORD_API = "https://discord.com/api/v10"
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID", "").strip()
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET", "").strip()
BOT_TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
LINK_TTL = int(os.getenv("DOWNLOAD_LINK_TTL_SECONDS", "86400"))
MAX_FILE_BYTES = int(os.getenv("MAX_DOWNLOAD_BYTES", str(2 * 1024 * 1024 * 1024)))
MAX_DURATION = int(os.getenv("MAX_DOWNLOAD_SECONDS", "3600"))
ALLOWED_HOSTS = {
    "youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be",
    "instagram.com", "www.instagram.com", "facebook.com", "www.facebook.com",
    "m.facebook.com", "fb.watch", "tiktok.com", "www.tiktok.com",
    "m.tiktok.com", "vm.tiktok.com", "vt.tiktok.com", "vimeo.com",
    "www.vimeo.com", "player.vimeo.com", "reddit.com", "www.reddit.com",
    "old.reddit.com", "v.redd.it", "x.com", "www.x.com", "twitter.com",
    "www.twitter.com", "t.co", "dailymotion.com", "www.dailymotion.com",
    "dai.ly", "streamable.com", "www.streamable.com", "twitch.tv",
    "www.twitch.tv", "clips.twitch.tv", "pinterest.com", "www.pinterest.com",
    "pin.it", "tumblr.com", "www.tumblr.com",
}
DB_LOCK = threading.Lock()


def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=20)
        g.db.row_factory = sqlite3.Row
    return g.db


@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS web_sessions (
            sid TEXT PRIMARY KEY, user_id TEXT NOT NULL, username TEXT NOT NULL,
            avatar TEXT, access_token TEXT NOT NULL, expires_at INTEGER NOT NULL
        )""")
        conn.execute("""CREATE TABLE IF NOT EXISTS downloads (
            token TEXT PRIMARY KEY, owner_id TEXT NOT NULL, file_path TEXT NOT NULL,
            filename TEXT NOT NULL, created_at INTEGER NOT NULL, expires_at INTEGER NOT NULL
        )""")
        conn.commit()


init_db()


def require_config():
    if not (CLIENT_ID and CLIENT_SECRET and BOT_TOKEN and BASE_URL):
        abort(503, "Website setup incomplete. Configure Discord OAuth and PUBLIC_BASE_URL environment variables.")


def current_user():
    sid = session.get("sid")
    if not sid:
        return None
    row = db().execute("SELECT * FROM web_sessions WHERE sid=?", (sid,)).fetchone()
    if not row or row["expires_at"] <= int(time.time()):
        if row:
            db().execute("DELETE FROM web_sessions WHERE sid=?", (sid,))
            db().commit()
        session.clear()
        return None
    return row


def login_required():
    user = current_user()
    if not user:
        return None
    return user


def validate_video_url(raw):
    try:
        parsed = urlparse((raw or "").strip())
        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != "https" or host not in ALLOWED_HOSTS:
            return None
        if parsed.username or parsed.password or parsed.port not in (None, 443):
            return None
        return parsed.geturl()
    except ValueError:
        return None


def discord_get(path, token, *, bot=False):
    auth = f"Bot {token}" if bot else f"Bearer {token}"
    response = requests.get(
        f"{DISCORD_API}{path}",
        headers={"Authorization": auth, "User-Agent": "Clipy-Web/1.0"},
        timeout=12,
    )
    response.raise_for_status()
    return response.json()


def can_manage_guild(guild):
    try:
        permissions = int(guild.get("permissions", "0"))
    except (TypeError, ValueError):
        permissions = 0
    return bool(permissions & 0x8 or permissions & 0x20)


def bot_is_in_guild(guild_id):
    try:
        discord_get(f"/guilds/{guild_id}", BOT_TOKEN, bot=True)
        return True
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code in (403, 404):
            return False
        raise


def page(title, body, *, script=""):
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#080b14"><title>{title} · Clipy</title>
<style>
:root{{--bg:#080b14;--panel:#101727;--line:#24324b;--muted:#9baac4;--text:#f3f6ff;--blue:#65a9ff;--cyan:#66ead9}}
*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(ellipse at 70% -20%,#17365a 0,transparent 46%),var(--bg);color:var(--text);font:16px/1.55 Inter,ui-sans-serif,system-ui,-apple-system,sans-serif}}
a{{color:var(--blue);text-decoration:none}}a:hover{{text-decoration:underline}}.wrap{{width:min(1080px,92vw);margin:auto}}header{{display:flex;align-items:center;justify-content:space-between;padding:22px 0;border-bottom:1px solid #ffffff12}}.brand{{font-size:22px;font-weight:850;letter-spacing:-.7px;color:white}}.brand b{{color:var(--cyan)}}.nav{{display:flex;gap:16px;align-items:center;color:var(--muted)}}main{{padding:56px 0 80px}}.eyebrow{{color:var(--cyan);font-size:12px;font-weight:800;letter-spacing:2px;text-transform:uppercase}}h1{{font-size:clamp(36px,7vw,68px);line-height:1.02;letter-spacing:-2.7px;margin:12px 0 20px}}h2{{font-size:25px;letter-spacing:-.6px}}p{{color:var(--muted)}}.hero{{max-width:780px;margin-bottom:34px}}.hero p{{font-size:18px;max-width:660px}}.btn{{display:inline-flex;align-items:center;justify-content:center;border:0;border-radius:12px;padding:12px 18px;background:linear-gradient(120deg,#69aaff,#66ead9);color:#06101b;font-weight:800;cursor:pointer;font-size:15px}}.btn.secondary{{background:#182238;color:var(--text);border:1px solid var(--line)}}.btn:disabled{{opacity:.5;cursor:wait}}.grid{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}}.panel,.guild,.result{{background:linear-gradient(145deg,#121c2e,#0d1320);border:1px solid var(--line);border-radius:18px;padding:22px;box-shadow:0 20px 60px #0002}}.step{{font-size:12px;color:var(--cyan);font-weight:800;letter-spacing:1px}}.panel h3{{margin:8px 0}}.guilds{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px;margin:24px 0}}.guild{{display:flex;align-items:center;gap:14px;padding:16px}}.guild img,.avatar{{width:46px;height:46px;border-radius:14px;object-fit:cover;background:#24324b}}.guild .name{{font-weight:750;overflow-wrap:anywhere}}.guild .sub{{font-size:13px;color:var(--muted)}}.guild .btn{{margin-left:auto;white-space:nowrap}}input{{width:100%;background:#080e19;color:var(--text);border:1px solid #34435e;border-radius:12px;padding:14px;font:inherit;margin:8px 0 12px}}label{{font-weight:700}}.formrow{{display:flex;gap:10px;align-items:center}}.formrow input{{flex:1;min-width:0}}.note{{font-size:13px;color:var(--muted)}}.error{{color:#ffb7b7;background:#401e2a;border:1px solid #7d394b;padding:12px;border-radius:10px}}.success{{color:#b5ffea;background:#12352f;border:1px solid #23695e;padding:14px;border-radius:12px;overflow-wrap:anywhere}}.result{{margin-top:18px}}.empty{{padding:32px;text-align:center;border:1px dashed #34435e;border-radius:16px;color:var(--muted)}}footer{{border-top:1px solid #ffffff12;padding:22px 0 34px;color:var(--muted);font-size:13px}}@media(max-width:720px){{.grid{{grid-template-columns:1fr}}.guilds{{grid-template-columns:1fr}}main{{padding-top:36px}}h1{{letter-spacing:-1.5px}}.formrow{{display:block}}.formrow .btn{{width:100%}}.nav{{gap:10px;font-size:13px}}}}
</style></head><body><div class="wrap"><header><a class="brand" href="/">clipy<b>.</b></a><nav class="nav"><a href="/">Home</a><a href="/dashboard">Dashboard</a></nav></header><main>{body}</main><footer>Clipy · Use only content you have permission to download. Generated links expire automatically.</footer></div><script>{script}</script></body></html>"""


@app.get("/")
def home():
    user = current_user()
    button = '<a class="btn" href="/dashboard">Open dashboard →</a>' if user else '<a class="btn" href="/login">Get started with Discord →</a>'
    body = f"""
<section class="hero"><div class="eyebrow">Find it. Process it. Get a link.</div>
<h1>Your videos.<br><span style="color:#78b9ff">One simple dashboard.</span></h1>
<p>Clipy helps you turn a supported public video URL into a temporary download link. Sign in with Discord, choose a server you manage, then create and copy your link from the dashboard.</p>{button}</section>
<section class="grid"><article class="panel"><div class="step">01 / CONNECT</div><h3>Sign in securely</h3><p>Use Discord OAuth to see servers where you have permission to manage them.</p></article>
<article class="panel"><div class="step">02 / SET UP</div><h3>Choose your server</h3><p>If Clipy is missing, add it through Discord's official invite flow. Otherwise, open the dashboard.</p></article>
<article class="panel"><div class="step">03 / DOWNLOAD</div><h3>Generate a link</h3><p>Paste a supported public video URL. When processing finishes, copy a private, expiring download link.</p></article></section>
<p class="note" style="margin-top:22px">Limits depend on the hosting plan and source platform. Private/restricted videos may not work; generated links are temporary.</p>"""
    return page("Video dashboard", body)


@app.get("/login")
def login():
    require_config()
    state = secrets.token_urlsafe(32)
    session["oauth_state"] = state
    params = urlencode({
        "client_id": CLIENT_ID,
        "redirect_uri": f"{BASE_URL}/callback",
        "response_type": "code",
        "scope": "identify guilds",
        "state": state,
        "prompt": "none",
    })
    return redirect(f"https://discord.com/oauth2/authorize?{params}")


@app.get("/callback")
def callback():
    require_config()
    state = request.args.get("state", "")
    expected = session.pop("oauth_state", "")
    if not state or not expected or not secrets.compare_digest(state, expected):
        abort(400, "Invalid OAuth state. Please sign in again.")
    code = request.args.get("code")
    if not code:
        return redirect("/login")
    response = requests.post(
        f"{DISCORD_API}/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": f"{BASE_URL}/callback",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=12,
    )
    response.raise_for_status()
    token_data = response.json()
    access_token = token_data["access_token"]
    user = discord_get("/users/@me", access_token)
    sid = secrets.token_urlsafe(32)
    expires = int(time.time()) + min(int(token_data.get("expires_in", 604800)), 604800)
    db().execute(
        "INSERT INTO web_sessions(sid,user_id,username,avatar,access_token,expires_at) VALUES(?,?,?,?,?,?)",
        (sid, str(user["id"]), user.get("global_name") or user["username"], user.get("avatar"), access_token, expires),
    )
    db().commit()
    session.clear()
    session["sid"] = sid
    return redirect("/dashboard")


@app.get("/dashboard")
def dashboard():
    user = login_required()
    if not user:
        return redirect("/login")
    try:
        guilds = [
            guild for guild in discord_get("/users/@me/guilds", user["access_token"])
            if can_manage_guild(guild)
        ]
    except requests.RequestException:
        abort(502, "Discord could not be reached. Please reload the dashboard.")
    avatar = ""
    if user["avatar"]:
        avatar = f'<img class="avatar" src="https://cdn.discordapp.com/avatars/{user["user_id"]}/{user["avatar"]}.png?size=96" alt="">'
    cards = []
    for guild in guilds:
        try:
            installed = bot_is_in_guild(guild["id"])
        except requests.RequestException:
            installed = False
        icon = (
            f'<img src="https://cdn.discordapp.com/icons/{guild["id"]}/{guild["icon"]}.png?size=96" alt="">'
            if guild.get("icon") else '<div class="avatar" style="display:grid;place-items:center">✦</div>'
        )
        if installed:
            action = f'<a class="btn" href="/server/{guild["id"]}">Manage →</a>'
            state_text = "Clipy is in this server"
        else:
            invite = "https://discord.com/oauth2/authorize?" + urlencode({
                "client_id": CLIENT_ID,
                "scope": "bot applications.commands",
                "permissions": "2147568640",
                "guild_id": guild["id"],
                "disable_guild_select": "true",
            })
            action = f'<a class="btn secondary" href="{invite}" rel="noopener">Add bot ↗</a>'
            state_text = "Invite Clipy to continue"
        cards.append(f'<article class="guild">{icon}<div><div class="name">{guild["name"]}</div><div class="sub">{state_text}</div></div>{action}</article>')
    content = "".join(cards) or '<div class="empty">No servers with Manage Server permission were found on this Discord account.</div>'
    body = f"""
<section class="hero"><div class="eyebrow">Your workspace</div><h1>Welcome, {user["username"]}.</h1><p>Choose a server you manage. Add Clipy if it isn't there yet, then open its dashboard to generate download links.</p><p><a class="btn secondary" href="/logout">Log out</a></p></section>
<div class="panel"><h2>Your servers</h2><p>Only servers where your Discord account has Manage Server or Administrator permission are shown.</p><div class="guilds">{content}</div></div>
"""
    return page("Dashboard", body)


@app.get("/server/<guild_id>")
def server_dashboard(guild_id):
    user = login_required()
    if not user:
        return redirect("/login")
    if not guild_id.isdigit():
        abort(404)
    try:
        guilds = discord_get("/users/@me/guilds", user["access_token"])
    except requests.RequestException:
        abort(502, "Discord could not be reached.")
    guild = next((g for g in guilds if g["id"] == guild_id and can_manage_guild(g)), None)
    if not guild:
        abort(403, "You do not have permission to manage this server.")
    try:
        if not bot_is_in_guild(guild_id):
            return redirect("/dashboard")
    except requests.RequestException:
        abort(502, "Could not verify Clipy's membership in this server.")
    body = f"""
<section class="hero"><div class="eyebrow">Server dashboard</div><h1>{guild["name"]}</h1><p>Paste a public video link to process it on the website. Large files aren't sent through Discord attachments; your generated link will be hosted temporarily by this web service.</p><a href="/dashboard">← All servers</a></section>
<section class="panel"><h2>Generate a download link</h2><form id="download-form"><label for="video-url">Video URL</label><input id="video-url" name="url" type="url" placeholder="https://www.youtube.com/watch?v=…" required autocomplete="url"><button class="btn" id="submit-btn" type="submit">Process video →</button><p class="note">Supported public sites only. Current defaults: up to 1 hour and 2 GB, subject to hosting storage, bandwidth, and platform restrictions. Generated links expire after 24 hours.</p></form><div id="message" aria-live="polite"></div></section>
<section class="result"><h2>How it works</h2><p>1. Paste the original video URL. 2. Clipy processes it on the website server. 3. Copy the generated URL and open it to download the file.</p></section>
"""
    script = r"""
const form=document.getElementById('download-form'),btn=document.getElementById('submit-btn'),msg=document.getElementById('message');
form.addEventListener('submit',async e=>{e.preventDefault();btn.disabled=true;btn.textContent='Processing…';msg.innerHTML='<p>Processing may take a while for long or high-quality videos. Keep this tab open.</p>';try{const r=await fetch('/api/download',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({url:document.getElementById('video-url').value})});const data=await r.json();if(!r.ok)throw new Error(data.error||'Could not process this video.');msg.innerHTML='<div class="success"><strong>Ready to download</strong><p><a href="'+data.url+'">'+data.url+'</a></p><button class="btn" id="copy-link" type="button">Copy download link</button><p class="note">File: '+data.filename+' · Expires '+data.expires+' · Keep this link private.</p></div>';document.getElementById('copy-link').onclick=async()=>{await navigator.clipboard.writeText(data.url);document.getElementById('copy-link').textContent='Copied ✓'};}catch(err){msg.innerHTML='<p class="error">'+err.message+'</p>'}finally{btn.disabled=false;btn.textContent='Process video →'}});
"""
    return page("Server dashboard", body, script=script)


@app.post("/api/download")
def create_download():
    user = login_required()
    if not user:
        return {"error": "Please sign in again."}, 401
    payload = request.get_json(silent=True) or {}
    url = validate_video_url(payload.get("url", ""))
    if not url:
        return {"error": "Use an HTTPS video URL from one of Clipy's supported public sites."}, 400

    # Keep work and output on the server; never trust a remote filename or a client path.
    job_dir = FILES_DIR / secrets.token_hex(16)
    job_dir.mkdir(mode=0o700)
    opts = {
        "outtmpl": str(job_dir / "video.%(ext)s"),
        "noplaylist": True,
        "max_filesize": MAX_FILE_BYTES,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 25,
        "retries": 2,
        "cachedir": False,
        "ffmpeg_location": imageio_ffmpeg.get_ffmpeg_exe(),
        "match_filter": yt_dlp.utils.match_filter_func(
            f"duration > {MAX_DURATION}"
        ),
    }
    try:
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=True)
        candidates = [p for p in job_dir.iterdir() if p.is_file() and not p.name.endswith((".part", ".ytdl"))]
        if not candidates:
            raise RuntimeError("No output file was created.")
        path = max(candidates, key=lambda p: p.stat().st_size)
        if path.stat().st_size > MAX_FILE_BYTES:
            raise RuntimeError("The file exceeds the configured hosting limit.")
        token = secrets.token_urlsafe(32)
        expires = int(time.time()) + LINK_TTL
        filename = f"{(info or {}).get('title') or 'clip'}{path.suffix}"
        # Strip control characters and keep a sensible filename length.
        filename = "".join(ch for ch in filename if ch.isprintable() and ch not in '\\\\/:*?"<>|')[:160] or f"clip{path.suffix}"
        db().execute(
            "INSERT INTO downloads(token,owner_id,file_path,filename,created_at,expires_at) VALUES(?,?,?,?,?,?)",
            (token, user["user_id"], str(path.resolve()), filename, int(time.time()), expires),
        )
        db().commit()
        download_url = f"{BASE_URL}/file/{token}"
        return {"url": download_url, "filename": filename, "expires": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(expires))}
    except Exception as exc:
        for item in job_dir.glob("*"):
            item.unlink(missing_ok=True)
        job_dir.rmdir()
        # Avoid returning raw extractor messages, which can expose implementation details.
        app.logger.info("Video processing failed (%s)", type(exc).__name__)
        return {"error": "Processing failed. The link may be private, unsupported, too long, or over the configured size limit."}, 400


@app.get("/file/<token>")
def get_file(token):
    if len(token) < 30 or not token.replace("-", "").replace("_", "").isalnum():
        abort(404)
    row = db().execute("SELECT * FROM downloads WHERE token=?", (token,)).fetchone()
    if not row:
        abort(404)
    if row["expires_at"] <= int(time.time()):
        abort(410, "This download link has expired.")
    path = Path(row["file_path"]).resolve()
    if not path.is_relative_to(FILES_DIR.resolve()) or not path.is_file():
        abort(404)
    return send_file(path, as_attachment=True, download_name=row["filename"], conditional=True)


@app.get("/logout")
def logout():
    sid = session.get("sid")
    if sid:
        db().execute("DELETE FROM web_sessions WHERE sid=?", (sid,))
        db().commit()
    session.clear()
    return redirect("/")


@app.get("/health")
def health():
    return {"ok": True}


@app.errorhandler(400)
@app.errorhandler(403)
@app.errorhandler(404)
@app.errorhandler(410)
@app.errorhandler(502)
@app.errorhandler(503)
def handle_error(error):
    code = getattr(error, "code", 500)
    message = getattr(error, "description", "Something went wrong.")
    return page("Notice", f'<section class="panel"><h1>Something went wrong</h1><p>{message}</p><a class="btn" href="/dashboard">Back to dashboard</a></section>'), code


if __name__ == "__main__":
    require_config()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")), debug=False)
