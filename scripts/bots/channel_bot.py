#!/usr/bin/env python3
"""
OWUI Channel Bot — Multi-mode bot framework for v0.8.7

Modes (set via BOT_TYPE env var):
  echo     — Echo bot (default, for testing)
  faq      — FAQ bot with RAG knowledge base integration
  welcome  — Welcome bot for new channel members

Usage:
    export WEBUI_URL=https://open-webui.myia.io
    export BOT_EMAIL=bot@myia.org
    export BOT_PASSWORD=...
    export BOT_TYPE=faq
    python channel_bot.py

Architecture:
    1. Login via REST → get JWT token
    2. Connect Socket.IO at /ws/socket.io with JWT auth
    3. Emit user-join → server joins bot to all channel rooms
    4. Listen events:channel → filter messages → respond via REST

Requires: python-socketio[asyncio] aiohttp python-dotenv
"""

import asyncio
import json
import logging
import os
import re
import signal
import sys
from pathlib import Path

import aiohttp
import socketio

# Load .env from repo root or from /config/.env (Docker mount)
try:
    from dotenv import load_dotenv

    for env_path in [
        Path("/config/.env"),
        Path(__file__).resolve().parent.parent.parent / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            break
except ImportError:
    pass

# --- Configuration ---

WEBUI_URL = os.environ.get("WEBUI_URL", os.environ.get("MYIA_URL", ""))
BOT_EMAIL = os.environ.get("BOT_EMAIL", os.environ.get("MYIA_EMAIL", ""))
BOT_PASSWORD = os.environ.get("BOT_PASSWORD", os.environ.get("MYIA_PASSWORD", ""))

# Bot behavior
BOT_NAME = os.environ.get("BOT_NAME", "Assistant MyIA")
BOT_TRIGGER = os.environ.get("BOT_TRIGGER", "")  # Keyword trigger (empty = respond to all)
BOT_CHANNELS = os.environ.get("BOT_CHANNELS", "")  # Comma-separated channel names (empty = all)
BOT_MODEL = os.environ.get("BOT_MODEL", "Local.qwen3.6-35b-a3b-fast")
BOT_KB_COLLECTIONS = os.environ.get(
    "BOT_KB_COLLECTIONS", ""
)  # Comma-separated KB collection names for RAG
BOT_RAG_TOP_K = int(os.environ.get("BOT_RAG_TOP_K", "5"))
IGNORE_OWN_MESSAGES = True
RECONNECT_DELAY = int(os.environ.get("RECONNECT_DELAY", "5"))
RECONNECT_MAX_DELAY = int(os.environ.get("RECONNECT_MAX_DELAY", "60"))

# Logging
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("channel-bot")

# --- Mention parsing ---

MENTION_RE = re.compile(r"<@([A-Z]):([^|>]+)(?:\|([^>]+))?>")


def extract_mentions(content: str) -> list[dict]:
    """Extract @mentions from message content."""
    return [
        {"type": m.group(1), "id": m.group(2), "label": m.group(3) or m.group(2)}
        for m in MENTION_RE.finditer(content)
    ]


def strip_mentions(content: str) -> str:
    """Remove @mention tags, leaving just the label text."""
    return MENTION_RE.sub(lambda m: m.group(3) or m.group(2), content).strip()


# --- OWUI API client ---


class OWUIClient:
    """REST API client for Open WebUI."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.token: str = ""
        self.user_id: str = ""
        self.user_name: str = ""
        self.session: aiohttp.ClientSession | None = None

    async def login(self, email: str, password: str) -> bool:
        """Authenticate and store JWT token."""
        timeout = aiohttp.ClientTimeout(total=300, sock_read=180)
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False),
            timeout=timeout,
        )
        async with self.session.post(
            f"{self.base_url}/api/v1/auths/signin",
            json={"email": email, "password": password},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.token = data.get("token", "")
                self.user_id = data.get("id", "")
                self.user_name = data.get("name", "")
                return True
            text = await resp.text()
            log.error("Login failed: %s - %s", resp.status, text[:200])
            return False

    @property
    def headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    async def get_channels(self) -> list[dict]:
        """List all accessible channels."""
        async with self.session.get(
            f"{self.base_url}/api/v1/channels/",
            headers=self.headers,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            return []

    async def post_message(
        self, channel_id: str, content: str, parent_id: str | None = None
    ) -> dict | None:
        """Post a message to a channel (or reply in a thread)."""
        payload = {"content": content}
        if parent_id:
            payload["parent_id"] = parent_id

        async with self.session.post(
            f"{self.base_url}/api/v1/channels/{channel_id}/messages/post",
            headers=self.headers,
            json=payload,
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            log.error("Post message failed: %s - %s", resp.status, text[:200])
            return None

    async def send_typing(self, sio_client, channel_id: str) -> None:
        """Send typing indicator via Socket.IO (fire-and-forget)."""
        try:
            asyncio.create_task(sio_client.emit(
                "events:channel",
                {
                    "channel_id": channel_id,
                    "data": {"type": "typing", "data": {"typing": True}},
                },
            ))
        except Exception:
            pass  # Non-critical

    async def chat_completion(
        self, model: str, messages: list[dict], stream: bool = False
    ) -> str:
        """Call OWUI's OpenAI-compatible chat completion API."""
        try:
            log.debug("Calling chat completion with model %s...", model)
            async with self.session.post(
                f"{self.base_url}/api/chat/completions",
                headers=self.headers,
                json={"model": model, "messages": messages, "stream": stream},
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    choices = data.get("choices", [])
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        log.debug("Chat completion OK: %d chars", len(content))
                        return content
                else:
                    text = await resp.text()
                    log.error("Chat completion failed: %s - %s", resp.status, text[:200])
                return ""
        except asyncio.TimeoutError:
            log.error("Chat completion timed out for model %s", model)
            return ""
        except Exception:
            log.exception("Chat completion error")
            return ""

    async def query_rag(
        self,
        collection_names: list[str],
        query: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Query knowledge bases via OWUI RAG API."""
        async with self.session.post(
            f"{self.base_url}/api/v1/retrieval/query/collection",
            headers=self.headers,
            json={
                "collection_names": collection_names,
                "query": query,
                "k": top_k,
                "hybrid": True,
            },
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                # Response structure: list of {collection_name, documents[{...}]}
                # or flat list of document dicts depending on version
                if isinstance(data, list):
                    return data
                return data.get("documents", data.get("results", []))
            else:
                text = await resp.text()
                log.error("RAG query failed: %s - %s", resp.status, text[:200])
                return []

    async def close(self):
        if self.session:
            await self.session.close()


# --- Bot base class ---


class ChannelBot:
    """Base channel bot. Subclass and override on_message() for custom logic."""

    def __init__(self, client: OWUIClient):
        self.client = client
        self.sio = socketio.AsyncClient(ssl_verify=False, reconnection=False)
        self.allowed_channels: set[str] = set()
        self._running = True
        self._setup_handlers()

    def _setup_handlers(self):
        @self.sio.event
        async def connect():
            log.info("Socket.IO connected")

        @self.sio.event
        async def connect_error(data):
            log.error("Socket.IO connect error: %s", data)

        @self.sio.event
        async def disconnect():
            log.warning("Socket.IO disconnected")

        @self.sio.on("events:channel")
        async def on_channel_event(data):
            await self._handle_event(data)

    async def _handle_event(self, data: dict):
        """Route channel events to appropriate handlers.

        Messages are processed in background tasks to avoid blocking the
        Socket.IO event loop (which would prevent receiving further events
        and could cause heartbeat timeouts).
        """
        event_type = data.get("data", {}).get("type", "")
        event_data = data.get("data", {}).get("data", {})
        channel_id = data.get("channel_id", "")
        user = data.get("user", {})

        if event_type != "message":
            return
        if not isinstance(event_data, dict):
            return
        if IGNORE_OWN_MESSAGES and user.get("id") == self.client.user_id:
            return

        # Skip model auto-responses (from @mention mechanism)
        meta = event_data.get("meta") or {}
        if meta.get("model_id"):
            return

        if self.allowed_channels and channel_id not in self.allowed_channels:
            return

        content = event_data.get("content", "")
        message_id = event_data.get("id", "")
        parent_id = event_data.get("parent_id")
        sender_name = user.get("name", "unknown")

        if BOT_TRIGGER and BOT_TRIGGER.lower() not in content.lower():
            return

        log.info("Message from %s in %s: %s", sender_name, channel_id[:8], content[:80])

        # Process in a background task to not block the Socket.IO event loop
        asyncio.create_task(self._process_message(
            channel_id=channel_id,
            message_id=message_id,
            parent_id=parent_id,
            content=content,
            sender_name=sender_name,
            sender_id=user.get("id", ""),
            mentions=extract_mentions(content),
            raw=event_data,
        ))

    async def _process_message(self, **kwargs):
        """Wrapper for on_message that catches exceptions."""
        try:
            await self.on_message(**kwargs)
        except Exception:
            log.exception("Error in on_message handler")

    async def on_message(
        self,
        channel_id: str,
        message_id: str,
        parent_id: str | None,
        content: str,
        sender_name: str,
        sender_id: str,
        mentions: list[dict],
        raw: dict,
    ):
        """Override this method. Default: echo bot."""
        clean = strip_mentions(content)
        response = f"> {clean}\n\nMessage received! (echo from {BOT_NAME})"
        reply_parent = parent_id or message_id
        await self.client.post_message(channel_id, response, parent_id=reply_parent)

    async def _connect_and_join(self) -> bool:
        """Connect Socket.IO and join channels. Returns True on success."""
        try:
            await self.sio.connect(
                WEBUI_URL,
                socketio_path="/ws/socket.io",
                transports=["websocket"],
                auth={"token": self.client.token},
                wait_timeout=10,
            )
            response = await self.sio.call(
                "user-join",
                {"auth": {"token": self.client.token}},
                timeout=10,
            )
            log.info("Joined as: %s", response)
            return True
        except Exception as e:
            log.error("Connection failed: %s", e)
            return False

    async def start(self):
        """Connect and start listening with automatic reconnection."""
        if not await self.client.login(BOT_EMAIL, BOT_PASSWORD):
            log.error("Cannot start bot: login failed")
            return

        log.info(
            "Logged in as %s (%s)", self.client.user_name, self.client.user_id[:8]
        )

        # Resolve allowed channels
        if BOT_CHANNELS:
            channels = await self.client.get_channels()
            channel_names = [n.strip().lower() for n in BOT_CHANNELS.split(",")]
            for ch in channels:
                if ch.get("name", "").lower() in channel_names:
                    self.allowed_channels.add(ch["id"])
            log.info(
                "Listening on %d channel(s): %s",
                len(self.allowed_channels),
                ", ".join(channel_names),
            )
        else:
            log.info("Listening on ALL channels")

        # Connect with exponential backoff reconnection
        delay = RECONNECT_DELAY
        while self._running:
            if await self._connect_and_join():
                delay = RECONNECT_DELAY  # Reset on success
                # Keep alive loop
                while self._running and self.sio.connected:
                    await asyncio.sleep(1)
                if not self._running:
                    break
                log.warning("Connection lost")
            log.info("Reconnecting in %ds...", delay)
            await asyncio.sleep(delay)
            delay = min(delay * 2, RECONNECT_MAX_DELAY)

    async def stop(self):
        """Disconnect and cleanup."""
        self._running = False
        if self.sio.connected:
            await self.sio.disconnect()
        await self.client.close()


# --- FAQ Bot with RAG ---


class FAQBot(ChannelBot):
    """
    FAQ bot that answers questions using RAG (knowledge base search)
    followed by LLM completion for natural-language responses.
    """

    def __init__(self, client: OWUIClient):
        super().__init__(client)
        self.kb_collections = [
            c.strip()
            for c in BOT_KB_COLLECTIONS.split(",")
            if c.strip()
        ]

    async def on_message(
        self, channel_id, message_id, parent_id, content, sender_name, sender_id, mentions, raw
    ):
        clean = strip_mentions(content)

        # Skip very short messages
        if len(clean) < 10:
            return

        # Only respond to questions (contains ? or question words)
        question_indicators = [
            "?", "comment", "pourquoi", "quand", "quel", "est-ce",
            "how", "what", "why", "when", "where", "which", "aide", "help",
        ]
        if not any(q in clean.lower() for q in question_indicators):
            return

        log.info("Answering question from %s: %s", sender_name, clean[:60])

        # Send typing indicator (fire-and-forget, skip if it fails)
        log.info("Sending typing indicator...")
        await self.client.send_typing(self.sio, channel_id)
        log.info("Typing done")

        # Query RAG if KB collections are configured
        rag_context = ""
        if self.kb_collections:
            try:
                results = await self.client.query_rag(
                    collection_names=self.kb_collections,
                    query=clean,
                    top_k=BOT_RAG_TOP_K,
                )
                if results:
                    chunks = self._extract_chunks(results)
                    if chunks:
                        rag_context = "\n\n---\n\n".join(chunks[:BOT_RAG_TOP_K])
                        log.info("RAG returned %d relevant chunks", len(chunks))
            except Exception:
                log.exception("RAG query failed")

        # Build prompt with RAG context
        system_prompt = (
            f"Tu es {BOT_NAME}, un assistant dans un channel de discussion collaboratif. "
            "Réponds de manière concise et utile en français. "
            "Si tu ne sais pas, dis-le honnêtement."
        )
        if rag_context:
            system_prompt += (
                "\n\nVoici des extraits pertinents de la base de connaissances :\n\n"
                f"{rag_context}\n\n"
                "Utilise ces extraits pour répondre à la question. "
                "Cite les sources si possible."
            )

        log.info("Calling chat completion with model %s...", BOT_MODEL)
        response = await self.client.chat_completion(
            model=BOT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"{sender_name}: {clean}"},
            ],
        )
        log.info("Chat completion returned: %d chars", len(response) if response else 0)

        if response:
            # Strip <think>...</think> tags from thinking models
            response = re.sub(r"<think>.*?</think>", "", response, flags=re.DOTALL).strip()
            reply_parent = parent_id or message_id
            log.info("Posting reply (%d chars) to channel %s, parent=%s",
                     len(response), channel_id[:8], reply_parent[:8] if reply_parent else "None")
            result = await self.client.post_message(channel_id, response, parent_id=reply_parent)
            if result:
                log.info("Reply posted successfully: %s", result.get("id", "?")[:8])
            else:
                log.warning("Reply post returned None")

    @staticmethod
    def _extract_chunks(results) -> list[str]:
        """Extract text chunks from RAG query results."""
        chunks = []
        if isinstance(results, list):
            for item in results:
                if isinstance(item, dict):
                    # Format: {collection_name, documents: [{...}]} or flat {content, ...}
                    if "documents" in item:
                        for doc in item["documents"]:
                            text = doc if isinstance(doc, str) else doc.get("content", doc.get("text", ""))
                            if text:
                                chunks.append(str(text)[:1000])
                    elif "content" in item:
                        chunks.append(str(item["content"])[:1000])
                    elif "text" in item:
                        chunks.append(str(item["text"])[:1000])
                elif isinstance(item, str):
                    chunks.append(item[:1000])
        return chunks


# --- Welcome Bot ---


class WelcomeBot(ChannelBot):
    """
    Welcome bot that greets new users in channels.
    Responds to first-time messages from users it hasn't seen before.
    """

    WELCOME_MESSAGE = os.environ.get(
        "BOT_WELCOME_MESSAGE",
        (
            "Bienvenue sur **{channel}**, {user} ! 👋\n\n"
            "Ce channel est un espace de discussion collaborative. "
            "N'hésitez pas à poser vos questions — vous pouvez aussi mentionner "
            "un modèle IA avec @ pour obtenir de l'aide.\n\n"
            "Bonne discussion !"
        ),
    )

    def __init__(self, client: OWUIClient):
        super().__init__(client)
        self._seen_users: dict[str, set[str]] = {}  # channel_id -> set of user_ids

    async def on_message(
        self, channel_id, message_id, parent_id, content, sender_name, sender_id, mentions, raw
    ):
        # Only greet in top-level messages (not threads)
        if parent_id:
            return

        # Track seen users per channel
        if channel_id not in self._seen_users:
            self._seen_users[channel_id] = set()

        if sender_id in self._seen_users[channel_id]:
            return

        self._seen_users[channel_id].add(sender_id)

        # Get channel name for the welcome message
        channels = await self.client.get_channels()
        channel_name = next(
            (c.get("name", "ce channel") for c in channels if c.get("id") == channel_id),
            "ce channel",
        )

        msg = self.WELCOME_MESSAGE.format(channel=channel_name, user=sender_name)
        await self.client.post_message(channel_id, msg, parent_id=message_id)
        log.info("Welcomed %s in #%s", sender_name, channel_name)


# --- Main ---


async def main():
    if not WEBUI_URL or not BOT_EMAIL or not BOT_PASSWORD:
        log.error(
            "Missing configuration. Set WEBUI_URL, BOT_EMAIL, BOT_PASSWORD "
            "(or MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD)"
        )
        sys.exit(1)

    client = OWUIClient(WEBUI_URL)

    bot_type = os.environ.get("BOT_TYPE", "echo").lower()
    bot_classes = {"echo": ChannelBot, "faq": FAQBot, "welcome": WelcomeBot}
    bot_cls = bot_classes.get(bot_type, ChannelBot)
    bot = bot_cls(client)

    log.info("Starting %s (%s mode) → %s", BOT_NAME, bot_type, WEBUI_URL)
    if bot_type == "faq" and BOT_KB_COLLECTIONS:
        log.info("RAG collections: %s (top_k=%d)", BOT_KB_COLLECTIONS, BOT_RAG_TOP_K)

    # Graceful shutdown
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, lambda: asyncio.create_task(bot.stop()))
        except NotImplementedError:
            pass  # Windows doesn't support add_signal_handler

    try:
        await bot.start()
    except (KeyboardInterrupt, asyncio.CancelledError):
        log.info("Shutting down...")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
