"""
title: Markdown Normalizer
author: Fu-Jie
author_url: https://github.com/Fu-Jie/openwebui-extensions
funding_url: https://github.com/open-webui
version: 1.2.4
openwebui_id: baaa8732-9348-40b7-8359-7e009660e23c
description: A content normalizer filter that fixes common Markdown formatting issues in LLM outputs, such as broken code blocks, LaTeX formulas, and list formatting.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Callable, Dict
import re
import logging
import asyncio
import json
from dataclasses import dataclass, field

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class NormalizerConfig:
    """Configuration class for enabling/disabling specific normalization rules"""

    enable_escape_fix: bool = True  # Fix excessive escape characters
    enable_escape_fix_in_code_blocks: bool = (
        False  # Apply escape fix inside code blocks (default: False for safety)
    )
    enable_thought_tag_fix: bool = True  # Normalize thought tags
    enable_details_tag_fix: bool = True  # Normalize <details> tags (like thought tags)
    enable_code_block_fix: bool = True  # Fix code block formatting
    enable_latex_fix: bool = True  # Fix LaTeX formula formatting
    enable_list_fix: bool = (
        False  # Fix list item newlines (default off as it can be aggressive)
    )
    enable_unclosed_block_fix: bool = True  # Auto-close unclosed code blocks
    enable_fullwidth_symbol_fix: bool = False  # Fix full-width symbols in code blocks
    enable_mermaid_fix: bool = True  # Fix common Mermaid syntax errors
    enable_heading_fix: bool = (
        True  # Fix missing space in headings (#Header -> # Header)
    )
    enable_table_fix: bool = True  # Fix missing closing pipe in tables
    enable_xml_tag_cleanup: bool = True  # Cleanup leftover XML tags
    enable_emphasis_spacing_fix: bool = False  # Fix spaces inside **emphasis**

    # Custom cleaner functions (for advanced extension)
    custom_cleaners: List[Callable[[str], str]] = field(default_factory=list)


class ContentNormalizer:
    """LLM Output Content Normalizer - Production Grade Implementation"""

    # --- 1. Pre-compiled Regex Patterns (Performance Optimization) ---
    _PATTERNS = {
        # Code block prefix: if ``` is not at start of line (ignoring whitespace)
        "code_block_prefix": re.compile(r"(\S[ \t]*)(```)"),
        # Code block suffix: ```lang followed by non-whitespace (no newline)
        "code_block_suffix": re.compile(r"(```[\w\+\-\.]*)[ \t]+([^\n\r])"),
        # Code block indent: whitespace at start of line + ```
        "code_block_indent": re.compile(r"^[ \t]+(```)", re.MULTILINE),
        # Thought tag: </thought> followed by optional whitespace/newlines
        "thought_end": re.compile(
            r"</(thought|think|thinking)>[ \t]*\n*", re.IGNORECASE
        ),
        "thought_start": re.compile(r"<(thought|think|thinking)>", re.IGNORECASE),
        # Details tag: </details> followed by optional whitespace/newlines
        "details_end": re.compile(r"</details>[ \t]*\n*", re.IGNORECASE),
        # Self-closing details tag: <details ... /> followed by optional whitespace (but NOT already having newline)
        "details_self_closing": re.compile(
            r"(<details[^>]*/\s*>)(?!\n)", re.IGNORECASE
        ),
        # LaTeX block: \[ ... \]
        "latex_bracket_block": re.compile(r"\\\[(.+?)\\\]", re.DOTALL),
        # LaTeX inline: \( ... \)
        "latex_paren_inline": re.compile(r"\\\((.+?)\\\)"),
        # List item: non-newline + digit + dot + space
        "list_item": re.compile(r"([^\n])(\d+\. )"),
        # XML artifacts (e.g. Claude's)
        "xml_artifacts": re.compile(
            r"</?(?:antArtifact|antThinking|artifact)[^>]*>", re.IGNORECASE
        ),
        # Mermaid: Match various node shapes and quote unquoted labels
        "mermaid_node": re.compile(
            r'("[^"\\]*(?:\\.[^"\\]*)*")|'  # Match quoted strings first (Group 1)
            r"(\w+)(?:"
            r"(\(\(\()(?![\"])(.*?)(?<![\"])(\)\)\))|"  # (((...))) Double Circle
            r"(\(\()(?![\"])(.*?)(?<![\"])(\)\))|"  # ((...)) Circle
            r"(\(\[)(?![\"])(.*?)(?<![\"])(\]\))|"  # ([...]) Stadium
            r"(\[\()(?![\"])(.*?)(?<![\"])(\)\])|"  # [(...)] Cylinder
            r"(\[\[)(?![\"])(.*?)(?<![\"])(\]\])|"  # [[...]] Subroutine
            r"(\{\{)(?![\"])(.*?)(?<![\"])(\}\})|"  # {{...}} Hexagon
            r"(\[/)(?![\"])(.*?)(?<![\"])(/\])|"  # [/.../] Parallelogram
            r"(\[\\)(?![\"])(.*?)(?<![\"])(\\\])|"  # [\...\] Parallelogram Alt
            r"(\[/)(?![\"])(.*?)(?<![\"])(\\\])|"  # [/...\] Trapezoid
            r"(\[\\)(?![\"])(.*?)(?<![\"])(/\])|"  # [\.../] Trapezoid Alt
            r"(\()(?![\"])([^)]*?)(?<![\"])(\))|"  # (...) Round - Modified to be safer
            r"(\[)(?![\"])(.*?)(?<![\"])(\])|"  # [...] Square
            r"(\{)(?![\"])(.*?)(?<![\"])(\})|"  # {...} Rhombus
            r"(>)(?![\"])(.*?)(?<![\"])(\])"  # >...] Asymmetric
            r")"
            r"(\s*\[\d+\])?",  # Capture optional citation [1]
            re.DOTALL,
        ),
        # Heading: #Heading -> # Heading
        "heading_space": re.compile(r"^(#+)([^ \n#])", re.MULTILINE),
        # Table: | col1 | col2 -> | col1 | col2 |
        "table_pipe": re.compile(r"^(\|.*[^|\n])$", re.MULTILINE),
        # Emphasis spacing
        "emphasis_spacing": re.compile(
            r"(?<!\*|_)(\*{1,3}|_{1,3})(?P<inner>[^\n]*?)(\1)(?!\*|_)"
        ),
    }

    def __init__(self, config: Optional[NormalizerConfig] = None):
        self.config = config or NormalizerConfig()
        self.applied_fixes = []

    def normalize(self, content: str) -> str:
        """Main entry point: apply all normalization rules in order"""
        self.applied_fixes = []
        if not content:
            return content

        original_content = content

        try:
            if self.config.enable_escape_fix:
                original = content
                content = self._fix_escape_characters(content)
                if content != original:
                    self.applied_fixes.append("Fix Escape Chars")

            if self.config.enable_thought_tag_fix:
                original = content
                content = self._fix_thought_tags(content)
                if content != original:
                    self.applied_fixes.append("Normalize Thought Tags")

            if self.config.enable_details_tag_fix:
                original = content
                content = self._fix_details_tags(content)
                if content != original:
                    self.applied_fixes.append("Normalize Details Tags")

            if self.config.enable_code_block_fix:
                original = content
                content = self._fix_code_blocks(content)
                if content != original:
                    self.applied_fixes.append("Fix Code Blocks")

            if self.config.enable_latex_fix:
                original = content
                content = self._fix_latex_formulas(content)
                if content != original:
                    self.applied_fixes.append("Normalize LaTeX")

            if self.config.enable_list_fix:
                original = content
                content = self._fix_list_formatting(content)
                if content != original:
                    self.applied_fixes.append("Fix List Format")

            if self.config.enable_unclosed_block_fix:
                original = content
                content = self._fix_unclosed_code_blocks(content)
                if content != original:
                    self.applied_fixes.append("Close Code Blocks")

            if self.config.enable_fullwidth_symbol_fix:
                original = content
                content = self._fix_fullwidth_symbols_in_code(content)
                if content != original:
                    self.applied_fixes.append("Fix Full-width Symbols")

            if self.config.enable_mermaid_fix:
                original = content
                content = self._fix_mermaid_syntax(content)
                if content != original:
                    self.applied_fixes.append("Fix Mermaid Syntax")

            if self.config.enable_heading_fix:
                original = content
                content = self._fix_headings(content)
                if content != original:
                    self.applied_fixes.append("Fix Headings")

            if self.config.enable_table_fix:
                original = content
                content = self._fix_tables(content)
                if content != original:
                    self.applied_fixes.append("Fix Tables")

            if self.config.enable_xml_tag_cleanup:
                original = content
                content = self._cleanup_xml_tags(content)
                if content != original:
                    self.applied_fixes.append("Cleanup XML Tags")

            if self.config.enable_emphasis_spacing_fix:
                original = content
                content = self._fix_emphasis_spacing(content)
                if content != original:
                    self.applied_fixes.append("Fix Emphasis Spacing")

            for cleaner in self.config.custom_cleaners:
                original = content
                content = cleaner(content)
                if content != original:
                    self.applied_fixes.append("Custom Cleaner")

            if self.applied_fixes:
                logger.info(f"Markdown Normalizer Applied Fixes: {self.applied_fixes}")

            return content

        except Exception as e:
            logger.error(f"Content normalization failed: {e}", exc_info=True)
            return content

    def _fix_escape_characters(self, content: str) -> str:
        if self.config.enable_escape_fix_in_code_blocks:
            content = content.replace("\\r\\n", "\n")
            content = content.replace("\\n", "\n")
            content = content.replace("\\t", "\t")
            content = content.replace("\\\\", "\\")
            return content
        else:
            parts = content.split("```")
            for i in range(0, len(parts), 2):
                parts[i] = parts[i].replace("\\r\\n", "\n")
                parts[i] = parts[i].replace("\\n", "\n")
                parts[i] = parts[i].replace("\\t", "\t")
                parts[i] = parts[i].replace("\\\\", "\\")
            return "```".join(parts)

    def _fix_thought_tags(self, content: str) -> str:
        content = self._PATTERNS["thought_start"].sub("<thought>", content)
        return self._PATTERNS["thought_end"].sub("</thought>\n\n", content)

    def _fix_details_tags(self, content: str) -> str:
        parts = content.split("```")
        for i in range(0, len(parts), 2):
            parts[i] = self._PATTERNS["details_end"].sub("</details>\n\n", parts[i])
            parts[i] = self._PATTERNS["details_self_closing"].sub(r"\1\n", parts[i])
        return "```".join(parts)

    def _fix_code_blocks(self, content: str) -> str:
        content = self._PATTERNS["code_block_prefix"].sub(r"\n\1", content)
        content = self._PATTERNS["code_block_suffix"].sub(r"\1\n\2", content)
        return content

    def _fix_latex_formulas(self, content: str) -> str:
        content = self._PATTERNS["latex_bracket_block"].sub(r"$$\1$$", content)
        content = self._PATTERNS["latex_paren_inline"].sub(r"$\1$", content)
        return content

    def _fix_list_formatting(self, content: str) -> str:
        return self._PATTERNS["list_item"].sub(r"\1\n\2", content)

    def _fix_unclosed_code_blocks(self, content: str) -> str:
        if content.count("```") % 2 != 0:
            content += "\n```"
        return content

    def _fix_fullwidth_symbols_in_code(self, content: str) -> str:
        FULLWIDTH_MAP = {
            "\uff0c": ",", "\u3002": ".", "\uff08": "(", "\uff09": ")",
            "\u3010": "[", "\u3011": "]", "\uff1b": ";", "\uff1a": ":",
            "\uff1f": "?", "\uff01": "!", "\uff02": '"', "\uff07": "'",
            "\u201c": '"', "\u201d": '"', "\u2018": "'", "\u2019": "'",
        }
        parts = content.split("```")
        for i in range(1, len(parts), 2):
            for full, half in FULLWIDTH_MAP.items():
                parts[i] = parts[i].replace(full, half)
        return "```".join(parts)

    def _fix_mermaid_syntax(self, content: str) -> str:
        def replacer(match):
            if match.group(1):
                return match.group(1)
            id_str = match.group(2)
            groups = match.groups()
            citation = groups[-1] or ""
            for i in range(2, len(groups) - 1, 3):
                if groups[i] is not None:
                    open_char = groups[i]
                    content = groups[i + 1]
                    close_char = groups[i + 2]
                    if citation:
                        content += citation
                    content = content.replace('"', '\\"')
                    return f'{id_str}{open_char}"{content}"{close_char}'
            return match.group(0)

        parts = content.split("```")
        for i in range(1, len(parts), 2):
            lang_line = parts[i].split("\n", 1)[0].strip().lower()
            if "mermaid" in lang_line:
                edge_labels = []

                def protect_edge_label(m):
                    start = m.group(1)
                    label = m.group(2)
                    arrow = m.group(3)
                    edge_labels.append((start, label, arrow))
                    return f"___EDGE_LABEL_{len(edge_labels)-1}___"

                edge_label_pattern = (
                    r"(--|-\.|\=\=)\s+(.+?)\s+(--+[>ox]?|--+\|>|\.-[>ox]?|=+[>ox]?)"
                )
                protected = re.sub(edge_label_pattern, protect_edge_label, parts[i])
                fixed = self._PATTERNS["mermaid_node"].sub(replacer, protected)
                for idx, (start, label, arrow) in enumerate(edge_labels):
                    fixed = fixed.replace(
                        f"___EDGE_LABEL_{idx}___", f"{start} {label} {arrow}"
                    )
                parts[i] = fixed

                subgraph_count = len(re.findall(r"\bsubgraph\b", parts[i], re.IGNORECASE))
                end_count = len(re.findall(r"\bend\b", parts[i], re.IGNORECASE))
                if subgraph_count > end_count:
                    missing_ends = subgraph_count - end_count
                    parts[i] = parts[i].rstrip() + ("\n    end" * missing_ends) + "\n"

        return "```".join(parts)

    def _fix_headings(self, content: str) -> str:
        parts = content.split("```")
        for i in range(0, len(parts), 2):
            parts[i] = self._PATTERNS["heading_space"].sub(r"\1 \2", parts[i])
        return "```".join(parts)

    def _fix_tables(self, content: str) -> str:
        parts = content.split("```")
        for i in range(0, len(parts), 2):
            parts[i] = self._PATTERNS["table_pipe"].sub(r"\1|", parts[i])
        return "```".join(parts)

    def _cleanup_xml_tags(self, content: str) -> str:
        return self._PATTERNS["xml_artifacts"].sub("", content)

    def _fix_emphasis_spacing(self, content: str) -> str:
        def replacer(match):
            symbol = match.group(1)
            inner = match.group("inner")
            inner = self._PATTERNS["emphasis_spacing"].sub(replacer, inner)
            stripped_inner = inner.strip()
            if stripped_inner == inner:
                return f"{symbol}{inner}{symbol}"
            if not stripped_inner:
                return match.group(0)
            if inner.startswith(" ") and inner.endswith(" "):
                if symbol in ["*", "_"]:
                    return match.group(0)
            if symbol == "*" and inner.lstrip().startswith(("*", "_")):
                return match.group(0)
            if symbol == "*" and inner.startswith("   "):
                return match.group(0)
            return f"{symbol}{stripped_inner}{symbol}"

        parts = content.split("```")
        for i in range(0, len(parts), 2):
            while True:
                new_part = self._PATTERNS["emphasis_spacing"].sub(replacer, parts[i])
                if new_part == parts[i]:
                    break
                parts[i] = new_part
        return "```".join(parts)


class Filter:
    class Valves(BaseModel):
        priority: int = Field(
            default=50,
            description="Priority level. Higher runs later (recommended to run after other filters).",
        )
        enable_escape_fix: bool = Field(
            default=True, description="Fix excessive escape characters (\\n, \\t, etc.)"
        )
        enable_escape_fix_in_code_blocks: bool = Field(
            default=False,
            description="Apply escape fix inside code blocks (Warning: May break valid code. Default: False)",
        )
        enable_thought_tag_fix: bool = Field(
            default=True, description="Normalize </thought> tags"
        )
        enable_details_tag_fix: bool = Field(
            default=True, description="Normalize <details> tags"
        )
        enable_code_block_fix: bool = Field(
            default=True, description="Fix code block formatting"
        )
        enable_latex_fix: bool = Field(
            default=True, description="Normalize LaTeX formulas"
        )
        enable_list_fix: bool = Field(
            default=False, description="Fix list item newlines (Experimental)"
        )
        enable_unclosed_block_fix: bool = Field(
            default=True, description="Auto-close unclosed code blocks"
        )
        enable_fullwidth_symbol_fix: bool = Field(
            default=False, description="Fix full-width symbols in code blocks"
        )
        enable_mermaid_fix: bool = Field(
            default=True, description="Fix common Mermaid syntax errors"
        )
        enable_heading_fix: bool = Field(
            default=True, description="Fix missing space in headings"
        )
        enable_table_fix: bool = Field(
            default=True, description="Fix missing closing pipe in tables"
        )
        enable_xml_tag_cleanup: bool = Field(
            default=True, description="Cleanup leftover XML tags"
        )
        enable_emphasis_spacing_fix: bool = Field(
            default=False, description="Fix spaces inside **emphasis**"
        )
        show_status: bool = Field(
            default=True, description="Show status notification when fixes are applied"
        )
        show_debug_log: bool = Field(
            default=True, description="Print debug logs to browser console (F12)"
        )

    def __init__(self):
        self.valves = self.Valves()

    def _get_chat_context(
        self, body: dict, __metadata__: Optional[dict] = None
    ) -> Dict[str, str]:
        chat_id = ""
        message_id = ""
        if isinstance(body, dict):
            chat_id = body.get("chat_id", "")
            message_id = body.get("id", "")
            if not chat_id or not message_id:
                body_metadata = body.get("metadata", {})
                if isinstance(body_metadata, dict):
                    if not chat_id:
                        chat_id = body_metadata.get("chat_id", "")
                    if not message_id:
                        message_id = body_metadata.get("message_id", "")
        if __metadata__ and isinstance(__metadata__, dict):
            if not chat_id:
                chat_id = __metadata__.get("chat_id", "")
            if not message_id:
                message_id = __metadata__.get("message_id", "")
        return {"chat_id": str(chat_id).strip(), "message_id": str(message_id).strip()}

    def _contains_html(self, content: str) -> bool:
        pattern = r"<\s*/?\s*(?:html|head|body|div|p|hr|ul|ol|li|table|thead|tbody|tfoot|tr|td|th|img|a|code|pre|blockquote|h[1-6]|script|style|form|input|button|label|select|option|iframe|link|meta|title)\b"
        return bool(re.search(pattern, content, re.IGNORECASE))

    async def _emit_status(self, __event_emitter__, applied_fixes: List[str]):
        if not self.valves.show_status or not applied_fixes:
            return
        description = "Markdown Normalized"
        if applied_fixes:
            description += f": {', '.join(applied_fixes)}"
        try:
            await __event_emitter__(
                {"type": "status", "data": {"description": description, "done": True}}
            )
        except Exception as e:
            print(f"Error emitting status: {e}")

    async def _emit_debug_log(self, __event_call__, applied_fixes, original, normalized, chat_id=""):
        if not self.valves.show_debug_log or not __event_call__:
            return
        try:
            js_code = f"""
                (async function() {{
                    console.group("Markdown Normalizer Debug");
                    console.log("Chat ID:", {json.dumps(chat_id)});
                    console.log("Applied Fixes:", {json.dumps(applied_fixes, ensure_ascii=False)});
                    console.log("Original Content:", {json.dumps(original, ensure_ascii=False)});
                    console.log("Normalized Content:", {json.dumps(normalized, ensure_ascii=False)});
                    console.groupEnd();
                }})();
            """
            await __event_call__({"type": "execute", "data": {"code": js_code}})
        except Exception as e:
            print(f"Error emitting debug log: {e}")

    async def outlet(
        self,
        body: dict,
        __user__: Optional[dict] = None,
        __event_emitter__=None,
        __event_call__=None,
        __metadata__: Optional[dict] = None,
    ) -> dict:
        if "messages" in body and body["messages"]:
            last = body["messages"][-1]
            content = last.get("content", "") or ""
            if last.get("role") == "assistant" and isinstance(content, str):
                if self._contains_html(content):
                    return body
                if '""&quot;' in content or "tool_call_id" in content or '<details type="tool_calls"' in content:
                    return body
                config = NormalizerConfig(
                    enable_escape_fix=self.valves.enable_escape_fix,
                    enable_escape_fix_in_code_blocks=self.valves.enable_escape_fix_in_code_blocks,
                    enable_thought_tag_fix=self.valves.enable_thought_tag_fix,
                    enable_details_tag_fix=self.valves.enable_details_tag_fix,
                    enable_code_block_fix=self.valves.enable_code_block_fix,
                    enable_latex_fix=self.valves.enable_latex_fix,
                    enable_list_fix=self.valves.enable_list_fix,
                    enable_unclosed_block_fix=self.valves.enable_unclosed_block_fix,
                    enable_fullwidth_symbol_fix=self.valves.enable_fullwidth_symbol_fix,
                    enable_mermaid_fix=self.valves.enable_mermaid_fix,
                    enable_heading_fix=self.valves.enable_heading_fix,
                    enable_table_fix=self.valves.enable_table_fix,
                    enable_xml_tag_cleanup=self.valves.enable_xml_tag_cleanup,
                    enable_emphasis_spacing_fix=self.valves.enable_emphasis_spacing_fix,
                )
                normalizer = ContentNormalizer(config)
                new_content = normalizer.normalize(content)
                if new_content != content:
                    last["content"] = new_content
                    if __event_emitter__:
                        await self._emit_status(__event_emitter__, normalizer.applied_fixes)
                        chat_ctx = self._get_chat_context(body, __metadata__)
                        await self._emit_debug_log(
                            __event_call__, normalizer.applied_fixes,
                            content, new_content, chat_id=chat_ctx["chat_id"],
                        )
        return body
