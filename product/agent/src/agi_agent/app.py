"""HTTP API for the chat panel, served under /agent on the catalog's own origin (Caddy routes it here)."""

import asyncio
import hashlib
import json
import os
import re
import time
from contextlib import asynccontextmanager
from urllib.parse import unquote

import anthropic
import httpx
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import journal
from .loop import MODEL, run_turn
from .om_mcp import OM_URL, OmMcp, Unauthorized
from .proposals import Proposals
from .tools import model_tools

state: dict = {}


@asynccontextmanager
async def lifespan(_: FastAPI):
    state["http"] = httpx.AsyncClient()
    state["claude"] = anthropic.AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    state["tools"] = None  # OM's tool list is the same for every user: fetched once, on the first chat
    state["conversations"] = {}  # (user, conversation_id) -> {"history": [...], "lock": Lock, "notes": [...]}
    state["proposals"] = Proposals()
    state["users"] = {}  # sha256(token) -> (user name, valid until)
    yield
    await state["http"].aclose()


app = FastAPI(title="AGI catalog agent", lifespan=lifespan)


class ChatIn(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=100)
    message: str = Field(min_length=1, max_length=8000)
    page: str | None = Field(default=None, max_length=2000)


class DecisionIn(BaseModel):
    proposal_id: str
    action: str = Field(pattern="^(apply|discard)$")


def bearer(authorization: str | None) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Sign in to the catalog first.")
    return authorization.removeprefix("Bearer ").strip()


async def user_of(token: str) -> str:
    """Who is asking, as OM says after checking the token's signature; keys conversations, proposals and the journal."""
    key = hashlib.sha256(token.encode()).hexdigest()
    cached = state["users"].get(key)
    if cached and cached[1] > time.monotonic():
        return cached[0]
    r = await state["http"].get(f"{OM_URL}/api/v1/users/loggedInUser", headers={"Authorization": f"Bearer {token}"},
                                timeout=15)
    if r.status_code in (401, 403):
        raise HTTPException(401, "Your catalog session has expired. Reload the page and ask again.")
    r.raise_for_status()
    name = r.json()["name"]
    state["users"][key] = (name, time.monotonic() + 300)
    return name


# OM pages the user may be looking at: /table/<fqn>, /glossary/<fqn>, /metric/<fqn>, ... (tabs follow after a slash)
PAGE_TYPES = {"table": "table", "glossary": "glossaryTerm", "metric": "metric", "pipeline": "pipeline",
              "database": "database", "databaseSchema": "databaseSchema", "dashboard": "dashboard",
              "topic": "topic", "storedProcedure": "storedProcedure"}


def page_hint(page: str | None) -> str:
    if not page:
        return ""
    m = re.match(r"^/(\w+)/([^/?#]+)", page)
    if not m or m.group(1) not in PAGE_TYPES:
        return ""
    fqn = unquote(m.group(2)).replace('"', "")
    return f"[The user is viewing the {PAGE_TYPES[m.group(1)]} `{fqn}` in the catalog.]\n\n"


def sse(event: dict) -> bytes:
    return f"event: {event['type']}\ndata: {json.dumps(event, ensure_ascii=False, default=str)}\n\n".encode()


@app.get("/agent/health")
async def health():
    return {"ok": True, "model": MODEL}


@app.get("/agent/demo-login")
async def demo_login():
    """The shared demo login behind the sign-in page's "Sign in as jury" button; 404 unless the server sets both."""
    email, password = os.environ.get("DEMO_LOGIN_EMAIL"), os.environ.get("DEMO_LOGIN_PASSWORD")
    if not (email and password):
        raise HTTPException(status_code=404)
    return {"email": email, "password": password}


@app.post("/agent/chat")
async def chat(body: ChatIn, authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    user = await user_of(token)
    owner = (user, body.conversation_id)
    conv = state["conversations"].setdefault(owner, {"history": [], "lock": asyncio.Lock(), "notes": []})

    async def events():
        async with conv["lock"]:
            history = conv["history"]
            mark = len(history)
            notes = "".join(f"[{n}]\n" for n in conv["notes"])
            conv["notes"].clear()
            history.append({"role": "user", "content": notes + page_hint(body.page) + body.message})
            mcp = OmMcp(token, state["http"])
            record = {"user": user, "conversation": body.conversation_id, "page": body.page,
                      "question": body.message}
            completed = False
            try:
                await mcp.initialize()
                if state["tools"] is None:
                    state["tools"] = model_tools(await mcp.list_tools())
                answer = []
                async for ev in run_turn(state["claude"], mcp, state["tools"], history, state["proposals"], owner):
                    if ev["type"] == "text":
                        answer.append(ev["text"])
                    if ev["type"] == "done":
                        completed = True
                        record.update({k: v for k, v in ev.items() if k != "type"}, answer="".join(answer))
                    yield sse(ev)
            except Unauthorized:
                record["error"] = "unauthorized"
                yield sse({"type": "error", "code": "unauthorized",
                           "message": "Your catalog session has expired. Reload the page and ask again."})
            except (anthropic.APIError, httpx.HTTPError) as e:
                record["error"] = repr(e)
                yield sse({"type": "error", "code": "upstream", "message": "The assistant is unavailable right now. "
                           "Please try again in a moment."})
            finally:
                if not completed:  # error or client gone: never keep a half turn (a tool call without its result)
                    del history[mark:]
                journal.write(record)

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/agent/proposals")
async def decide(body: DecisionIn, authorization: str | None = Header(default=None)):
    token = bearer(authorization)
    user = await user_of(token)
    p = state["proposals"].get(user, body.proposal_id)
    if p is None:
        raise HTTPException(404, "No such proposal.")
    if p["status"] != "proposed":
        raise HTTPException(409, f"Proposal {p['id']} is already {p['status']}.")
    if body.action == "discard":
        p["status"] = "discarded"
        ok, message = True, "Discarded; nothing was changed."
    else:
        mcp = OmMcp(token, state["http"])
        try:
            await mcp.initialize()
            ok, message = await state["proposals"].apply(p, mcp, state["http"], token)
        except Unauthorized:
            raise HTTPException(401, "Your catalog session has expired. Reload the page and try again.")
    conv = state["conversations"].get(p["owner"])
    if conv is not None:
        conv["notes"].append(f"Proposal {p['id']} ({p['summary']}) was {p['status']} by the user. {message}")
    journal.write({"user": user, "proposal": p["id"], "fqn": p["fqn"], "action": body.action,
                   "status": p["status"], "message": message})
    return {"ok": ok, "status": p["status"], "message": message}
