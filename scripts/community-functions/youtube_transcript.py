from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
import re
import asyncio

from pydantic import BaseModel, Field
from youtube_transcript_api import (
    YouTubeTranscriptApi,
    TranscriptsDisabled,
    NoTranscriptFound,
)

YOUTUBE_ID_REGEX = re.compile(
    r"(?:v=|youtu\.be/|youtube\.com/embed/|shorts/)([A-Za-z0-9_-]{11})"
)

class EventEmitter:
    def __init__(self, event_emitter: Callable[[dict], Any] | None = None):
        self.event_emitter = event_emitter

    async def progress_update(self, description: str) -> None:
        await self.emit(description)

    async def error_update(self, description: str) -> None:
        await self.emit(description, "error", True)

    async def success_update(self, description: str) -> None:
        await self.emit(description, "success", True)

    async def emit(
        self,
        description: str = "Unknown State",
        status: str = "in_progress",
        done: bool = False,
    ) -> None:
        if self.event_emitter:
            await self.event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": status,
                        "description": description,
                        "done": done,
                    },
                }
            )

def extract_video_id(url_or_id: str) -> str:
    candidate = url_or_id.strip()
    if len(candidate) == 11 and re.fullmatch(r"[A-Za-z0-9_-]{11}", candidate):
        return candidate

    match = YOUTUBE_ID_REGEX.search(candidate)
    if not match:
        raise ValueError("Unable to extract video ID from provided URL/ID.")
    return match.group(1)

def _fetch_youtube_transcript_structured(
    url_or_id: str,
    language: str = "vi",
    fallback_languages: Optional[List[str]] = None,
) -> Dict[str, object]:
    if fallback_languages is None:
        fallback_languages = [language, "en"]
    else:
        if language not in fallback_languages:
            fallback_languages = [language] + fallback_languages

    video_id = extract_video_id(url_or_id)

    last_error: Optional[Exception] = None
    transcript_data = None
    used_language = None

    ytt_api = YouTubeTranscriptApi()

    for lang in fallback_languages:
        try:
            transcript_data = ytt_api.fetch(video_id, languages=[lang])
            used_language = lang
            break
        except (TranscriptsDisabled, NoTranscriptFound) as e:
            last_error = e
            continue

    if transcript_data is None:
        msg = "No transcript found for this video."
        if last_error is not None:
            msg += f" Reason: {last_error}"
        raise RuntimeError(msg)

    segments = []
    for snippet in transcript_data:
        segments.append(
            {
                "start": getattr(snippet, "start", None),
                "duration": getattr(snippet, "duration", None),
                "text": getattr(snippet, "text", ""),
            }
        )

    full_text = "\n".join(seg["text"] for seg in segments if seg["text"])

    return {
        "video_id": video_id,
        "language": used_language,
        "segments": segments,
        "full_text": full_text,
    }

class Tools:
    class Valves(BaseModel):
        CITATION: bool = Field(
            default=True, description="True or false for citation (not used yet)."
        )

    class UserValves(BaseModel):
        TRANSCRIPT_LANGUAGE: str = Field(
            default="fr,en",
            description="Comma-separated list of languages from highest priority to lowest.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self.citation = self.valves.CITATION

    async def get_youtube_transcript(
        self,
        url: str,
        __event_emitter__: Callable[[dict], Any] | None = None,
        __user__: dict = {},
    ) -> str:
        emitter = EventEmitter(__event_emitter__)

        if "valves" not in __user__:
            __user__["valves"] = self.UserValves()

        try:
            await emitter.progress_update(f"Validating URL/ID: {url}")

            if not url:
                raise ValueError("Invalid YouTube URL/ID (empty).")
            elif "dQw4w9WgXcQ" in url:
                raise ValueError("Rick Roll URL provided... is that what you want?")

            languages = [
                item.strip()
                for item in __user__["valves"].TRANSCRIPT_LANGUAGE.split(",")
                if item.strip()
            ]
            if not languages:
                languages = ["fr", "en"]

            await emitter.progress_update(
                f"Fetching transcript (preferred languages: {', '.join(languages)})"
            )

            data = await asyncio.to_thread(
                _fetch_youtube_transcript_structured,
                url,
                languages[0],
                languages,
            )

            transcript_text = data.get("full_text", "")
            if not transcript_text:
                raise RuntimeError("Transcript is empty.")

            await emitter.success_update("Transcript retrieved successfully!")
            return transcript_text

        except Exception as e:
            error_message = f"Error: {str(e)}"
            await emitter.error_update(error_message)
            return error_message
