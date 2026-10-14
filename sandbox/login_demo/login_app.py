"""Mācību demo: reģistrācija, pieteikšanās un lietotāja ierakstu saglabāšana SQLite datubāzē.

Nav saistīts ar `docs/openapi.yaml` līgumu un nav paredzēts produkcijai.
Palaišana: uvicorn login_app:app --reload  (no mapes sandbox/login_demo)
"""

import hashlib
import hmac
import html
import os
import secrets
import sqlite3
from contextlib import asynccontextmanager, closing
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

DB_PATH = os.environ.get("LOGIN_DEMO_DB", os.path.join(os.path.dirname(__file__), "login_demo.db"))
SESSION_COOKIE = "session"
PBKDF2_ITERATIONS = 200_000

# --- Datubāze ---------------------------------------------------------------

def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with closing(connect()) as conn, conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS entries (
                id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                body TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Login demo", lifespan=lifespan)


# --- Paroles un sesijas -----------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, PBKDF2_ITERATIONS)
    return f"{PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    iterations, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
    return hmac.compare_digest(digest.hex(), digest_hex)


def current_user(request: Request) -> sqlite3.Row | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    with closing(connect()) as conn:
        return conn.execute(
            "SELECT users.id, users.username FROM sessions JOIN users ON users.id = sessions.user_id "
            "WHERE sessions.token = ?",
            (token,),
        ).fetchone()


def start_session(user_id: int) -> RedirectResponse:
    token = secrets.token_urlsafe(32)
    with closing(connect()) as conn, conn:
        conn.execute("INSERT INTO sessions (token, user_id) VALUES (?, ?)", (token, user_id))
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax")
    return response


async def read_form(request: Request) -> dict[str, str]:
    parsed = parse_qs((await request.body()).decode(), keep_blank_values=True)
    return {key: values[0] for key, values in parsed.items()}


# --- HTML -------------------------------------------------------------------

STYLES = """
:root {
  --bg: #f4f1ec; --bg-accent: #e6eef0; --card: #ffffff; --text: #1f2a30; --muted: #66737a;
  --border: #dde3e5; --primary: #0f6e6a; --primary-hover: #0b5653; --primary-soft: #e3f1ef;
  --error: #b3261e; --error-soft: #fbeceb; --shadow: 0 10px 30px rgba(20, 40, 45, .08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #12181b; --bg-accent: #16242a; --card: #1b2327; --text: #e7ecee; --muted: #93a1a7;
    --border: #2c383d; --primary: #3fb5a8; --primary-hover: #5cc8bc; --primary-soft: #1d3634;
    --error: #f2938c; --error-soft: #3a2220; --shadow: 0 10px 30px rgba(0, 0, 0, .35);
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; min-height: 100vh; color: var(--text); line-height: 1.5;
  font-family: "Segoe UI", system-ui, -apple-system, Roboto, sans-serif;
  background: radial-gradient(circle at 15% 0%, var(--bg-accent), transparent 55%), var(--bg);
}
a { color: var(--primary); font-weight: 600; text-decoration: none; }
a:hover { text-decoration: underline; }
.auth { min-height: 100vh; display: grid; place-items: center; padding: 1.5rem 1rem; }
.card { background: var(--card); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow); }
.auth .card { width: 100%; max-width: 400px; padding: 2.25rem 2rem; }
.brand { display: flex; align-items: center; gap: .6rem; font-weight: 700; color: var(--primary); }
.logo {
  width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center;
  background: var(--primary); color: #fff; font-size: 1.1rem;
}
h1 { font-size: 1.6rem; margin: 1.5rem 0 .25rem; letter-spacing: -.01em; }
h2 { font-size: 1.1rem; margin: 0 0 1rem; }
.subtitle { color: var(--muted); margin: 0 0 1.5rem; }
form { display: grid; gap: 1rem; }
label { display: grid; gap: .35rem; font-size: .9rem; font-weight: 600; }
input, textarea {
  font: inherit; font-weight: 400; color: var(--text); background: var(--card);
  border: 1px solid var(--border); border-radius: 10px; padding: .7rem .85rem; width: 100%;
  transition: border-color .15s, box-shadow .15s;
}
textarea { resize: vertical; min-height: 7rem; }
input:focus, textarea:focus { outline: none; border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-soft); }
button {
  font: inherit; font-weight: 600; cursor: pointer; border: 0; border-radius: 10px;
  padding: .75rem 1.1rem; background: var(--primary); color: #fff; transition: background .15s;
}
button:hover { background: var(--primary-hover); }
button.ghost { background: transparent; color: var(--muted); border: 1px solid var(--border); padding: .45rem .9rem; }
button.ghost:hover { color: var(--text); background: var(--primary-soft); }
.error {
  background: var(--error-soft); color: var(--error); border-radius: 10px;
  padding: .7rem .9rem; margin: 0 0 1rem; font-size: .92rem;
}
.switch { text-align: center; color: var(--muted); margin: 1.5rem 0 0; font-size: .92rem; }
.topbar {
  position: sticky; top: 0; z-index: 1; background: var(--card); border-bottom: 1px solid var(--border);
}
.topbar-inner { max-width: 720px; margin: 0 auto; padding: .8rem 1rem; display: flex; align-items: center; gap: 1rem; }
.user { margin-left: auto; display: flex; align-items: center; gap: .75rem; color: var(--muted); font-size: .92rem; }
.avatar {
  width: 32px; height: 32px; border-radius: 50%; display: grid; place-items: center;
  background: var(--primary-soft); color: var(--primary); font-weight: 700; text-transform: uppercase;
}
main { max-width: 720px; margin: 0 auto; padding: 1.5rem 1rem 3rem; }
main h1 { margin-top: .5rem; }
.composer { padding: 1.5rem; margin-bottom: 2rem; }
.composer button { justify-self: end; }
.list-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: .75rem; }
.count { color: var(--muted); font-size: .9rem; }
.entry { padding: 1.1rem 1.25rem; margin-bottom: .75rem; }
.entry-head { display: flex; justify-content: space-between; gap: 1rem; align-items: baseline; }
.entry-title { font-weight: 700; font-size: 1.05rem; overflow-wrap: anywhere; }
.entry time { color: var(--muted); font-size: .82rem; white-space: nowrap; }
.entry p { margin: .4rem 0 0; white-space: pre-wrap; overflow-wrap: anywhere; }
.empty { text-align: center; color: var(--muted); padding: 2.5rem 1rem; border: 2px dashed var(--border); border-radius: 16px; }
@media (max-width: 480px) {
  .auth .card { padding: 1.75rem 1.25rem; }
  .user span.name { display: none; }
  .entry-head { flex-direction: column; gap: .1rem; }
}
"""

BRAND = '<div class="brand"><span class="logo">✎</span>Piezīmju grāmata</div>'


def page(title: str, body: str, status_code: int = 200) -> HTMLResponse:
    return HTMLResponse(
        f"""<!doctype html>
<html lang="lv"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} · Piezīmju grāmata</title>
<style>{STYLES}</style></head>
<body>{body}</body></html>""",
        status_code=status_code,
    )


def auth_page(title: str, subtitle: str, content: str, status_code: int) -> HTMLResponse:
    return page(
        title,
        f"""<div class="auth"><div class="card">
{BRAND}
<h1>{html.escape(title)}</h1>
<p class="subtitle">{html.escape(subtitle)}</p>
{content}
</div></div>""",
        status_code,
    )


def error_html(message: str | None) -> str:
    return f'<p class="error" role="alert">{html.escape(message)}</p>' if message else ""


def login_form(error: str | None = None, status_code: int = 200) -> HTMLResponse:
    return auth_page(
        "Pieteikšanās",
        "Laipni lūgti atpakaļ! Piesakies, lai redzētu savus ierakstus.",
        f"""{error_html(error)}
<form method="post" action="/login">
  <label>Lietotājvārds <input name="username" required autocomplete="username" autofocus></label>
  <label>Parole <input name="password" type="password" required autocomplete="current-password"></label>
  <button type="submit">Pieteikties</button>
</form>
<p class="switch">Nav konta? <a href="/register">Reģistrēties</a></p>""",
        status_code,
    )


def register_form(error: str | None = None, status_code: int = 200) -> HTMLResponse:
    return auth_page(
        "Reģistrācija",
        "Izveido kontu – tas aizņems tikai mirkli.",
        f"""{error_html(error)}
<form method="post" action="/register">
  <label>Lietotājvārds <input name="username" required minlength="3" maxlength="50" autocomplete="username" autofocus></label>
  <label>Parole <input name="password" type="password" required minlength="8" autocomplete="new-password" placeholder="Vismaz 8 rakstzīmes"></label>
  <label>Parole atkārtoti <input name="password_confirm" type="password" required minlength="8" autocomplete="new-password"></label>
  <button type="submit">Izveidot kontu</button>
</form>
<p class="switch">Jau ir konts? <a href="/login">Pieteikties</a></p>""",
        status_code,
    )


def format_timestamp(value: str) -> str:
    # SQLite CURRENT_TIMESTAMP: "YYYY-MM-DD HH:MM:SS" (UTC)
    date, _, time = value.partition(" ")
    year, month, day = date.split("-")
    return f"{day}.{month}.{year} {time[:5]}"


# --- Maršruti ---------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    user = current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    with closing(connect()) as conn:
        entries = conn.execute(
            "SELECT title, body, created_at FROM entries WHERE user_id = ? ORDER BY id DESC",
            (user["id"],),
        ).fetchall()
    username = html.escape(user["username"])
    items = "".join(
        f"""<article class="card entry">
  <div class="entry-head"><span class="entry-title">{html.escape(e["title"])}</span>
  <time datetime="{html.escape(e["created_at"])}">{format_timestamp(e["created_at"])}</time></div>
  <p>{html.escape(e["body"])}</p>
</article>"""
        for e in entries
    ) or '<div class="empty">Vēl nav neviena ieraksta. Uzraksti pirmo! ✨</div>'
    return page(
        "Mani ieraksti",
        f"""<header class="topbar"><div class="topbar-inner">
  {BRAND}
  <div class="user"><span class="avatar">{html.escape(user["username"][:1])}</span><span class="name">{username}</span>
    <form method="post" action="/logout"><button type="submit" class="ghost">Iziet</button></form>
  </div>
</div></header>
<main>
  <h1>Mani ieraksti</h1>
  <p class="subtitle">Sveiki, {username}! Pieraksti šeit visu, ko vēlies saglabāt.</p>
  <section class="card composer">
    <h2>Jauns ieraksts</h2>
    <form method="post" action="/entries">
      <label>Virsraksts <input name="title" required maxlength="200" placeholder="Par ko ir šis ieraksts?"></label>
      <label>Teksts <textarea name="body" required maxlength="5000" placeholder="Raksti šeit..."></textarea></label>
      <button type="submit">Saglabāt ierakstu</button>
    </form>
  </section>
  <div class="list-head"><h2>Saglabātie ieraksti</h2><span class="count">{len(entries)}</span></div>
  {items}
</main>""",
    )


@app.get("/register", response_class=HTMLResponse)
def register_page():
    return register_form()


@app.post("/register")
async def register(request: Request):
    form = await read_form(request)
    username = form.get("username", "").strip()
    password = form.get("password", "")
    if not 3 <= len(username) <= 50:
        return register_form("Lietotājvārdam jābūt 3–50 rakstzīmes garam.", 400)
    if len(password) < 8:
        return register_form("Parolei jābūt vismaz 8 rakstzīmes garai.", 400)
    if password != form.get("password_confirm", ""):
        return register_form("Paroles nesakrīt.", 400)
    try:
        with closing(connect()) as conn, conn:
            cursor = conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password)),
            )
    except sqlite3.IntegrityError:
        return register_form("Šāds lietotājvārds jau ir aizņemts.", 409)
    return start_session(cursor.lastrowid)


@app.get("/login", response_class=HTMLResponse)
def login_page():
    return login_form()


@app.post("/login")
async def login(request: Request):
    form = await read_form(request)
    with closing(connect()) as conn:
        user = conn.execute(
            "SELECT id, password_hash FROM users WHERE username = ?",
            (form.get("username", "").strip(),),
        ).fetchone()
    if user is None or not verify_password(form.get("password", ""), user["password_hash"]):
        return login_form("Nepareizs lietotājvārds vai parole.", 401)
    return start_session(user["id"])


@app.post("/logout")
def logout(request: Request):
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        with closing(connect()) as conn, conn:
            conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
    response = RedirectResponse("/login", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.post("/entries")
async def create_entry(request: Request):
    user = current_user(request)
    if user is None:
        return RedirectResponse("/login", status_code=303)
    form = await read_form(request)
    title = form.get("title", "").strip()
    body = form.get("body", "").strip()
    if title and body:
        with closing(connect()) as conn, conn:
            conn.execute(
                "INSERT INTO entries (user_id, title, body) VALUES (?, ?, ?)",
                (user["id"], title[:200], body[:5000]),
            )
    return RedirectResponse("/", status_code=303)
