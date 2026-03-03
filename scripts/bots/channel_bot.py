#!/usr/bin/env python3
"""
OWUI Channel Bot — Minimal framework for v0.8.7
Connects to Open WebUI via Socket.IO, listens for channel messages,
and responds via REST API.

Usage:
    # Set environment variables (or use .env file)
    export WEBUI_URL=https://open-webui.myia.io
    export BOT_EMAIL=bot@myia.org
    export BOT_PASSWORD=...

    python channel_bot.py

Architecture:
    1. Login via REST → get JWT token
    2. Connect Socket.IO at /ws/socket.io with JWT auth
    3. Emit user-join → server joins bot to all channel rooms
    4. Listen events:channel → filter messages → respond via REST

Requires: python-socketio[asyncio] aiohttp python-dotenv
"""

import asyncio
import logging
import os
import re
import sys
from pathlib import Path

import aiohttp
import socketio

# Load .env from repo root if available
try:
    from dotenv import load_dotenv
    env_path = Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
except ImportError:
    pass

# --- Configuration ---

WEBUI_URL = os.environ.get("WEBUI_URL", os.environ.get("MYIA_URL", ""))
BOT_EMAIL = os.environ.get("BOT_EMAIL", os.environ.get("MYIA_EMAIL", ""))
BOT_PASSWORD = os.environ.get("BOT_PASSWORD", os.environ.get("MYIA_PASSWORD", ""))

# Bot behavior
BOT_NAME = os.environ.get("BOT_NAME", "Channel Bot")
BOT_TRIGGER = os.environ.get("BOT_TRIGGER", "")  # Keyword trigger (empty = respond to all)
BOT_CHANNELS = os.environ.get("BOT_CHANNELS", "")  # Comma-separated channel names (empty = all)
IGNORE_OWN_MESSAGES = True
RECONNECT_DELAY = 5  # seconds

# Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
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
        self.session: aiohttp.ClientSession | None = None

    async def login(self, email: str, password: str) -> bool:
        """Authenticate and store JWT token."""
        self.session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(ssl=False)
        )
        async with self.session.post(
            f"{self.base_url}/api/v1/auths/signin",
            json={"email": email, "password": password},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                self.token = data.get("token", "")
                self.user_id = data.get("id", "")
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
        """Post a message to a channel (or reply to a thread)."""
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

    async def chat_completion(
        self, model: str, messages: list[dict], stream: bool = False
    ) -> str:
        """Call OWUI's OpenAI-compatible chat completion API."""
        async with self.session.post(
            f"{self.base_url}/api/chat/completions",
            headers=self.headers,
            json={"model": model, "messages": messages, "stream": stream},
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                choices = data.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "")
            return ""

    async def close(self):
        if self.session:
            await self.session.close()


# --- Bot logic (override this) ---

class ChannelBot:
    """Base channel bot. Subclass and override on_message() for custom logic."""

    def __init__(self, client: OWUIClient):
        self.client = client
        self.sio = socketio.AsyncClient(ssl_verify=False)
        self.allowed_channels: set[str] = set()  # channel IDs to listen on
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
        """Route channel events to appropriate handlers."""
        event_type = data.get("data", {}).get("type", "")
        event_data = data.get("data", {}).get("data", {})
        channel_id = data.get("channel_id", "")
        user = data.get("user", {})

        # Only process message events
        if event_type != "message":
            return

        # Skip if not a dict (malformed event)
        if not isinstance(event_data, dict):
            return

        # Skip own messages to prevent loops
        if IGNORE_OWN_MESSAGES and user.get("id") == self.client.user_id:
            return

        # Skip model responses (meta.model_id present)
        meta = event_data.get("meta") or {}
        if meta.get("model_id"):
            return

        # Filter by allowed channels
        if self.allowed_channels and channel_id not in self.allowed_channels:
            return

        content = event_data.get("content", "")
        message_id = event_data.get("id", "")
        parent_id = event_data.get("parent_id")
        sender_name = user.get("name", "unknown")

        # Filter by trigger keyword (if configured)
        if BOT_TRIGGER and BOT_TRIGGER.lower() not in content.lower():
            return

        log.info(
            "Message from %s in %s: %s",
            sender_name,
            channel_id[:8],
            content[:80],
        )

        try:
            await self.on_message(
                channel_id=channel_id,
                message_id=message_id,
                parent_id=parent_id,
                content=content,
                sender_name=sender_name,
                sender_id=user.get("id", ""),
                mentions=extract_mentions(content),
                raw=event_data,
            )
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
        """
        Override this method to implement custom bot logic.

        Default implementation: echo bot (responds with quoted message).
        """
        clean = strip_mentions(content)
        response = f"> {clean}\n\nMessage received! (echo from {BOT_NAME})"
        # Reply in thread if it's a thread, otherwise reply to the message
        reply_parent = parent_id or message_id
        await self.client.post_message(channel_id, response, parent_id=reply_parent)

    async def start(self):
        """Connect and start listening."""
        # Login
        if not await self.client.login(BOT_EMAIL, BOT_PASSWORD):
            log.error("Cannot start bot: login failed")
            return

        log.info("Logged in as %s (user_id=%s)", BOT_EMAIL, self.client.user_id)

        # Resolve allowed channels
        if BOT_CHANNELS:
            channels = await self.client.get_channels()
            channel_names = [n.strip().lower() for n in BOT_CHANNELS.split(",")]
            for ch in channels:
                if ch.get("name", "").lower() in channel_names:
                    self.allowed_channels.add(ch["id"])
            log.info("Listening on channels: %s", self.allowed_channels)
        else:
            log.info("Listening on ALL channels")

        # Connect Socket.IO
        await self.sio.connect(
            WEBUI_URL,
            socketio_path="/ws/socket.io",
            transports=["websocket"],
            auth={"token": self.client.token},
            wait_timeout=10,
        )

        # Join channels
        response = await self.sio.call(
            "user-join",
            {"auth": {"token": self.client.token}},
            timeout=10,
        )
        log.info("Joined as: %s", response)

        # Keep alive with reconnection
        while True:
            try:
                await self.sio.sleep(1)
            except (socketio.exceptions.ConnectionError, Exception) as e:
                log.warning("Connection lost: %s. Reconnecting in %ds...", e, RECONNECT_DELAY)
                await asyncio.sleep(RECONNECT_DELAY)
                try:
                    await self.sio.connect(
                        WEBUI_URL,
                        socketio_path="/ws/socket.io",
                        transports=["websocket"],
                        auth={"token": self.client.token},
                        wait_timeout=10,
                    )
                    await self.sio.call(
                        "user-join",
                        {"auth": {"token": self.client.token}},
                        timeout=10,
                    )
                    log.info("Reconnected successfully")
                except Exception as re_err:
                    log.error("Reconnection failed: %s", re_err)

    async def stop(self):
        """Disconnect and cleanup."""
        if self.sio.connected:
            await self.sio.disconnect()
        await self.client.close()


# --- Example: FAQ Bot with RAG ---

class FAQBot(ChannelBot):
    """
    FAQ bot that uses OWUI's chat completion API to answer questions.
    Optionally routes through a model that has KBs attached (e.g., expert-analyste).
    """

    MODEL_ID = os.environ.get("BOT_MODEL", "gpt-4.1-mini")

    async def on_message(self, channel_id, message_id, parent_id, content, sender_name, sender_id, mentions, raw):
        clean = strip_mentions(content)

        # Skip very short messages
        if len(clean) < 10:
            return

        # Skip if message ends with ? or contains a question word (basic filter)
        # Remove this filter to respond to all messages
        question_indicators = ["?", "comment", "pourquoi", "quand", "quel", "est-ce", "how", "what", "why"]
        is_question = any(q in clean.lower() for q in question_indicators)
        if not is_question:
            return

        log.info("Answering question from %s: %s", sender_name, clean[:60])

        # Get AI response
        response = await self.client.chat_completion(
            model=self.MODEL_ID,
            messages=[
                {
                    "role": "system",
                    "content": (
                        f"Tu es {BOT_NAME}, un assistant dans un channel de discussion. "
                        "Réponds de manière concise et utile. Si tu ne sais pas, dis-le."
                    ),
                },
                {"role": "user", "content": f"{sender_name}: {clean}"},
            ],
        )

        if response:
            reply_parent = parent_id or message_id
            await self.client.post_message(channel_id, response, parent_id=reply_parent)


# --- Main ---

async def main():
    if not WEBUI_URL or not BOT_EMAIL or not BOT_PASSWORD:
        log.error(
            "Missing configuration. Set WEBUI_URL, BOT_EMAIL, BOT_PASSWORD "
            "(or MYIA_URL, MYIA_EMAIL, MYIA_PASSWORD)"
        )
        sys.exit(1)

    client = OWUIClient(WEBUI_URL)

    # Choose bot type based on env
    bot_type = os.environ.get("BOT_TYPE", "echo").lower()
    if bot_type == "faq":
        bot = FAQBot(client)
    else:
        bot = ChannelBot(client)

    log.info("Starting %s (%s mode) → %s", BOT_NAME, bot_type, WEBUI_URL)

    try:
        await bot.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    finally:
        await bot.stop()


if __name__ == "__main__":
    asyncio.run(main())
