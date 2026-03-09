"""
title: LLM Council Tool
author: matheusbuniotto
funding_url: https://github.com/matheusbuniotto/openwebui-tools
version: 0.3.0
license: MIT
"""

import os
import asyncio
import re
from typing import List, Dict, Any, Tuple, Optional
from pydantic import BaseModel, Field
import requests

DEFAULT_COUNCIL_MODELS = "openai/gpt-4.1,openai/gpt-4o-mini,google/gemini-2.5-flash"


class Tools:
    class Valves(BaseModel):
        openwebui_base_url: str = Field(
            default="",
            description="Base URL for OpenWebUI API. Leave empty to auto-detect.",
        )
        openwebui_api_key: str = Field(
            default="",
            description="API Key for OpenWebUI. Leave empty to auto-detect.",
        )
        fallback_api_key: str = Field(
            default="",
            description="Fallback API key for OpenAI/OpenRouter.",
        )
        fallback_base_url: str = Field(
            default="https://api.openai.com/v1",
            description="Fallback API base URL.",
        )
        council_models: str = Field(
            default=DEFAULT_COUNCIL_MODELS,
            description="Comma-separated model IDs or 'all' for all available models.",
        )
        chairperson_model: str = Field(
            default="",
            description="Model ID for the Chairperson.",
        )
        max_models: int = Field(
            default=5,
            description="Maximum models when using 'all'.",
        )
        timeout: int = Field(
            default=60,
            description="Timeout in seconds for requests.",
        )

    def __init__(self):
        self.valves = self.Valves()
        self._resolved_api_key: Optional[str] = None
        self._resolved_base_url: Optional[str] = None
        self._using_fallback: bool = False

    def _resolve_api_key(self, __user__: Optional[dict] = None) -> Optional[str]:
        """Resolves API key with priority ordering."""
        if __user__:
            token = __user__.get("token") or __user__.get("api_key")
            if token:
                return token

        env_key = os.environ.get("OPENWEBUI_API_KEY")
        if env_key:
            return env_key

        if self.valves.openwebui_api_key:
            return self.valves.openwebui_api_key

        return None

    def _resolve_fallback_api_key(self) -> Optional[str]:
        """Resolves fallback API key."""
        if self.valves.fallback_api_key:
            return self.valves.fallback_api_key

        for env_var in ["OPENAI_API_KEY", "OPENROUTER_API_KEY"]:
            key = os.environ.get(env_var)
            if key:
                return key

        return None

    def _resolve_base_url(self) -> str:
        """Resolves base URL with fallback options."""
        if self.valves.openwebui_base_url:
            return self.valves.openwebui_base_url

        env_url = os.environ.get("OPENWEBUI_BASE_URL")
        if env_url:
            return env_url

        localhost_url = "http://localhost:3000/api"
        docker_url = "http://host.docker.internal:3000/api"

        try:
            response = requests.get(f"{localhost_url}/models", timeout=2)
            if response.status_code in [200, 401, 403]:
                return localhost_url
        except Exception:
            pass

        return docker_url

    def _try_fallback(self) -> Tuple[Optional[str], Optional[str]]:
        """Attempts to use fallback API."""
        fallback_key = self._resolve_fallback_api_key()
        if fallback_key:
            return fallback_key, self.valves.fallback_base_url
        return None, None

    async def _emit_status(
        self,
        event_emitter: Any,
        level: str,
        message: str,
        done: bool,
    ):
        """Emits status updates."""
        if event_emitter:
            await event_emitter(
                {
                    "type": "status",
                    "data": {
                        "status": "complete" if done else "in_progress",
                        "level": level,
                        "description": message,
                        "done": done,
                    },
                }
            )

    def _query_model_sync(
        self, model: str, messages: List[Dict[str, Any]], api_key: str, base_url: str
    ) -> Optional[Dict[str, Any]]:
        """Synchronous helper to query a model."""
        url = f"{base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": messages,
        }

        try:
            response = requests.post(
                url, headers=headers, json=payload, timeout=self.valves.timeout
            )
            response.raise_for_status()
            data = response.json()
            return data["choices"][0]["message"]
        except Exception as e:
            print(f"Error querying model {model}: {e}")
            return {"error": str(e)}

    async def _query_model_async(
        self, model: str, messages: List[Dict[str, Any]], api_key: str, base_url: str
    ) -> Tuple[str, Optional[Dict[str, Any]]]:
        """Async wrapper for querying a model."""
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None, self._query_model_sync, model, messages, api_key, base_url
        )
        return model, result

    def _parse_ranking_from_text(self, ranking_text: str) -> List[str]:
        """Extracts ranking list from model text."""
        if "FINAL RANKING:" in ranking_text:
            parts = ranking_text.split("FINAL RANKING:")
            if len(parts) >= 2:
                ranking_section = parts[1]
                numbered_matches = re.findall(
                    r"\d+\.\s*Response [A-Z]", ranking_section
                )
                if numbered_matches:
                    return [
                        re.search(r"Response [A-Z]", m).group()
                        for m in numbered_matches
                    ]

        matches = re.findall(r"Response [A-Z]", ranking_text)
        return matches

    def _get_available_models(self, api_key: str, base_url: str) -> List[str]:
        """Fetches available models from API."""
        url = f"{base_url}/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = requests.get(url, headers=headers, timeout=self.valves.timeout)
            response.raise_for_status()
            data = response.json()
            return [model["id"] for model in data.get("data", [])]
        except Exception as e:
            print(f"Error fetching models: {e}")
            return []

    async def consult_council(
        self,
        topic: str,
        __user__: Optional[dict] = None,
        __event_emitter__: Any = None,
    ) -> str:
        """Orchestrates 3-stage council deliberation."""
        # Resolve credentials
        api_key = self._resolve_api_key(__user__)
        base_url = self._resolve_base_url()
        self._using_fallback = False

        if not api_key:
            fallback_key, fallback_url = self._try_fallback()
            if fallback_key:
                api_key = fallback_key
                base_url = fallback_url
                self._using_fallback = True
            else:
                await self._emit_status(
                    __event_emitter__,
                    "error",
                    "No API Key found.",
                    True,
                )
                return "Error: No API Key configured."

        # Fetch available models
        available_models = await asyncio.get_running_loop().run_in_executor(
            None, self._get_available_models, api_key, base_url
        )

        # Determine target models
        configured_models_raw = self.valves.council_models.lower().strip()
        target_models = []

        if configured_models_raw == "all":
            if available_models:
                target_models = available_models[: self.valves.max_models]
        else:
            requested_models = [
                m.strip() for m in self.valves.council_models.split(",") if m.strip()
            ]
            if available_models:
                target_models = [m for m in requested_models if m in available_models]
            else:
                target_models = requested_models

        council_models_list = target_models
        if not council_models_list:
            return "Error: No council models available."

        chairperson = self.valves.chairperson_model or council_models_list[0]

        # Stage 1: Collect responses
        await self._emit_status(
            __event_emitter__,
            "info",
            f"Stage 1: Consulting {len(council_models_list)} members",
            False,
        )

        stage1_messages = [{"role": "user", "content": topic}]
        tasks = [
            self._query_model_async(model, stage1_messages, api_key, base_url)
            for model in council_models_list
        ]

        stage1_results_raw = await asyncio.gather(*tasks)

        valid_responses = []
        for model, response in stage1_results_raw:
            if response and "error" not in response:
                content = response.get("content", "")
                if content:
                    valid_responses.append({"model": model, "response": content})

        if not valid_responses:
            return "Error: All council models failed."

        # Stage 2: Peer ranking
        await self._emit_status(
            __event_emitter__,
            "info",
            "Stage 2: Council reviewing peer responses",
            False,
        )

        labels = [chr(65 + i) for i in range(len(valid_responses))]
        responses_text = "\n\n".join(
            [
                f"Response {label}:\n{r['response']}"
                for label, r in zip(labels, valid_responses)
            ]
        )

        ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {topic}

Here are the responses (anonymized):

{responses_text}

Provide a final ranking formatted as:
FINAL RANKING:
1. Response [Label]
2. Response [Label]
..."""

        ranking_messages = [{"role": "user", "content": ranking_prompt}]
        ranking_tasks = [
            self._query_model_async(model, ranking_messages, api_key, base_url)
            for model in council_models_list
        ]
        stage2_results_raw = await asyncio.gather(*ranking_tasks)

        rankings = []
        for model, response in stage2_results_raw:
            if response:
                content = response.get("content", "")
                parsed = self._parse_ranking_from_text(content)
                rankings.append(
                    {"model": model, "full_text": content, "parsed": parsed}
                )

        # Stage 3: Synthesis
        await self._emit_status(
            __event_emitter__,
            "info",
            "Stage 3: Chairperson synthesizing result",
            False,
        )

        stage1_summary = "\n\n".join(
            [f"Model: {r['model']}\nResponse: {r['response']}" for r in valid_responses]
        )

        stage2_summary = "\n\n".join(
            [
                f"Model: {r['model']}\nRanking: {r.get('parsed', 'No ranking')}"
                for r in rankings
            ]
        )

        chairman_prompt = f"""You are the Chairperson of an LLM Council.

Original Question: {topic}

STAGE 1 - Individual Responses:
{stage1_summary}

STAGE 2 - Peer Rankings:
{stage2_summary}

Synthesize a comprehensive answer considering all inputs."""

        chairman_messages = [{"role": "user", "content": chairman_prompt}]
        _, final_response = await self._query_model_async(
            chairperson, chairman_messages, api_key, base_url
        )

        await self._emit_status(
            __event_emitter__, "info", "Council meeting adjourned.", True
        )

        # Build report
        report_parts = ["# LLM Council Report\n"]

        report_parts.append("## Stage 1: Individual Perspectives")
        for r in valid_responses:
            report_parts.append(f"### {r['model']}\n{r['response']}\n")

        report_parts.append("\n## Stage 2: Peer Evaluation & Ranking")
        for r in rankings:
            report_parts.append(f"### {r['model']}'s Ranking\n{r['full_text']}\n")

        if final_response:
            final_synthesis = final_response.get("content", "Error: No content.")
            report_parts.append(
                f"\n## Stage 3: Chairperson Synthesis ({chairperson})\n{final_synthesis}"
            )
        else:
            report_parts.append("\n## Stage 3: Chairperson Synthesis\nError synthesizing.")

        full_report = "\n".join(report_parts)

        if __event_emitter__:
            await __event_emitter__(
                {
                    "type": "message",
                    "data": {"content": full_report},
                }
            )

        return full_report
