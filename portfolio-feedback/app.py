"""Comments, likes and dislikes for the articles on the portfolio (lucas.<root domain>/articles/<slug>/).

No accounts: a comment needs a name and a text; a vote needs a random voter id the browser keeps in localStorage.
Abuse controls: articles must exist in the published site, length limits, a honeypot field, a per-IP rate limit on
writes (IPs are only kept as salted hashes, in memory), one vote per voter per article, and an admin token to delete.

Routes (served under /api/feedback on the portfolio host, same origin as the site):
  GET    /api/feedback/{slug}                 counts and comments, newest first
  POST   /api/feedback/{slug}/vote            {"voter": "<uuid>", "value": 1 | -1 | 0}
  POST   /api/feedback/{slug}/comments        {"name": "...", "body": "...", "website": ""}
  DELETE /api/feedback/comments/{id}          header X-Admin-Token
  GET    /api/feedback/health
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
import sqlite3
import time
from collections import defaultdict, deque
from contextlib import closing

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

DB = os.environ.get("FEEDBACK_DB", "/data/feedback.db")
SITE = os.environ.get("FEEDBACK_SITE_ROOT", "/site")
ADMIN_TOKEN = os.environ.get("FEEDBACK_ADMIN_TOKEN", "")
SALT = secrets.token_hex(16)  # rotates on restart; hashes are only used for rate limiting
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{2,90}$")
VOTER = re.compile(r"^[a-f0-9-]{16,64}$")
LIMITS = {"comment": (6, 600), "vote": (40, 600)}  # writes per IP per window (seconds)

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
_writes: dict[str, deque] = defaultdict(deque)


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB, timeout=5)
    con.row_factory = sqlite3.Row
    return con


with closing(db()) as con:
    con.executescript("""
        pragma journal_mode = wal;
        create table if not exists comments (
            id integer primary key autoincrement, slug text not null, name text not null, body text not null,
            created_at integer not null);
        create index if not exists comments_slug on comments (slug, created_at);
        create table if not exists votes (
            slug text not null, voter text not null, value integer not null, updated_at integer not null,
            primary key (slug, voter));
    """)


def require_article(slug: str) -> None:
    if not SLUG.match(slug) or not os.path.isfile(os.path.join(SITE, "articles", slug, "index.html")):
        raise HTTPException(404, "unknown article")


def rate_limit(request: Request, kind: str) -> None:
    ip = (request.headers.get("x-forwarded-for") or (request.client.host if request.client else "")).split(",")[0].strip()
    key = kind + hashlib.sha256((SALT + ip).encode()).hexdigest()
    now, (limit, window) = time.time(), LIMITS[kind]
    q = _writes[key]
    while q and q[0] < now - window:
        q.popleft()
    if len(q) >= limit:
        raise HTTPException(429, "too many requests, try again in a few minutes")
    q.append(now)


def summary(con: sqlite3.Connection, slug: str, voter: str | None = None) -> dict:
    likes, dislikes = con.execute(
        "select coalesce(sum(value = 1), 0), coalesce(sum(value = -1), 0) from votes where slug = ?", (slug,)).fetchone()
    comments = [dict(r) for r in con.execute(
        "select id, name, body, created_at from comments where slug = ? order by created_at desc limit 200", (slug,))]
    mine = 0
    if voter and VOTER.match(voter):
        row = con.execute("select value from votes where slug = ? and voter = ?", (slug, voter)).fetchone()
        mine = row["value"] if row else 0
    return {"likes": likes, "dislikes": dislikes, "my_vote": mine, "comments": comments}


@app.get("/api/feedback/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/feedback/{slug}")
def read(slug: str, voter: str | None = None) -> dict:
    require_article(slug)
    with closing(db()) as con:
        return summary(con, slug, voter)


class Vote(BaseModel):
    voter: str = Field(min_length=16, max_length=64)
    value: int = Field(ge=-1, le=1)


@app.post("/api/feedback/{slug}/vote")
def vote(slug: str, payload: Vote, request: Request) -> dict:
    require_article(slug)
    if not VOTER.match(payload.voter):
        raise HTTPException(422, "invalid voter id")
    rate_limit(request, "vote")
    with closing(db()) as con, con:
        if payload.value == 0:
            con.execute("delete from votes where slug = ? and voter = ?", (slug, payload.voter))
        else:
            con.execute(
                "insert into votes (slug, voter, value, updated_at) values (?, ?, ?, ?) "
                "on conflict (slug, voter) do update set value = excluded.value, updated_at = excluded.updated_at",
                (slug, payload.voter, payload.value, int(time.time())))
        return summary(con, slug, payload.voter)


class Comment(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    body: str = Field(min_length=2, max_length=2000)
    website: str = ""  # honeypot: hidden in the form, bots fill it


@app.post("/api/feedback/{slug}/comments", status_code=201)
def comment(slug: str, payload: Comment, request: Request) -> dict:
    require_article(slug)
    if payload.website:
        return {"ok": True}  # pretend success to the bot
    name, body = " ".join(payload.name.split()), payload.body.strip()
    if not name or len(body) < 2:
        raise HTTPException(422, "name and comment are required")
    if len(re.findall(r"https?://", body)) > 2:
        raise HTTPException(422, "too many links")
    rate_limit(request, "comment")
    with closing(db()) as con, con:
        con.execute("insert into comments (slug, name, body, created_at) values (?, ?, ?, ?)",
                    (slug, name, body, int(time.time())))
        return summary(con, slug)


@app.delete("/api/feedback/comments/{comment_id}")
def delete(comment_id: int, x_admin_token: str = Header(default="")) -> dict:
    if not ADMIN_TOKEN or not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(403, "forbidden")
    with closing(db()) as con, con:
        n = con.execute("delete from comments where id = ?", (comment_id,)).rowcount
    return {"deleted": n}
