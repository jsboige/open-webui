"""
title: Visuals Core - High Quality
author: Cole
version: 1.0.0
license: MIT
description: High-quality tables, charts, heatmaps, timelines, flowcharts, and trees.
Supports text (Markdown/ASCII) and embed (HTML + optional Plotly CDN).
No dashboards, no knowledge, no time utilities.
required_open_webui_version: 0.4.0

tool_instructions: |
 When calling this tool, arguments MUST be passed as valid JSON objects.

 Rules:
 - Do NOT wrap arguments in XML.
 - Do NOT HTML-escape quotes (no &quot;).
 - Arrays and objects must be native JSON, not strings.
 - rows must be a JSON array of objects.
 - numbers must be numbers, not strings when numeric rules apply.

 Example (chart):
 {
  "x": ["Mon","Tue","Wed"],
  "y": [120, 180, 160],
  "title": "Sessions",
  "chart_type": "line",
  "mode": "auto"
 }
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List, Literal, Set, Tuple, Union

from pydantic import BaseModel, Field

try:
    from fastapi.responses import HTMLResponse
except Exception:
    HTMLResponse = None

ChartType = Literal["bar", "line", "scatter"]
OutputMode = Literal["embed", "text", "auto"]


class Tools:
    """
    Visuals Core - High Quality (OpenWebUI tool)

    Focused features:
    Charts:
    - render_chart
    - render_multi_chart
    - render_bar_chart (ASCII)
    - render_line_chart (ASCII)
    - _ascii_scatter_chart
    - _ascii_chart
    Data Tables:
    - render_table
    - _html_table
    - _html_table_simple
    Comparison & Analysis:
    - render_comparison_table
    - _html_comparison_table
    - _find_best_values
    - _is_best_value
    Heatmaps & Matrices:
    - render_heatmap
    - _ascii_heatmap
    Timelines & Workflows:
    - render_timeline
    - render_flowchart
    - render_tree

    Design goals:
    - Dark-mode-safe HTML output (OpenWebUI friendly)
    - Defensive JSON coercion (stringified / HTML-escaped JSON)
    - Safe limits for huge outputs
    - Plotly via CDN optional; graceful ASCII fallback
    """

    # ---------- Dark-mode-safe palette ----------
    _BG = "#0b0f14"
    _PANEL = "#0b0f14"
    _HEADER = "#111827"
    _TEXT = "#e5e7eb"
    _MUTED = "#94a3b8"
    _BORDER = "#374151"
    _OUTER = "#1f2937"
    _RADIUS = "12px"

    # Metric colors (comparison highlights)
    _POSITIVE = "#16a34a"

    _PLOTLY_CDN_VERSION = "2.27.0"

    def __init__(self) -> None:
        self.valves = self.Valves()

    class Valves(BaseModel):
        allow_external_cdn: bool = Field(
            True,
            description="If true, charts/heatmaps can load Plotly from CDN in embed mode. If false, uses ASCII/text fallbacks.",
        )
        max_rows: int = Field(250, description="Safety cap for table rows.")
        max_cols: int = Field(60, description="Safety cap for table columns.")
        ascii_chart_height: int = Field(12, description="ASCII chart height (lines).")
        ascii_chart_width: int = Field(60, description="ASCII chart width (chars).")
        embed_chart_height: int = Field(420, description="Embedded chart height (px).")
        embed_chart_width: str = Field("100%", description="Embedded chart width (CSS).")

    # =====================================================
    # Defensive JSON coercion
    # =====================================================

    def _coerce_json(self, value: Any, expect: Literal["list", "dict", "any"]) -> Any:
        if value is None:
            return value

        if expect == "list" and isinstance(value, list):
            return value
        if expect == "dict" and isinstance(value, dict):
            return value
        if expect == "any" and isinstance(value, (list, dict)):
            return value

        if isinstance(value, str):
            s = html.unescape(value.strip())

            # strip one layer of wrapping quotes
            if (s.startswith('"') and s.endswith('"')) or (s.startswith("'") and s.endswith("'")):
                s = s[1:-1].strip()

            if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                try:
                    return json.loads(s)
                except Exception:
                    return value
            return value

    def _coerce_str_list(self, value: Any) -> List[str]:
        v = self._coerce_json(value, "list")
        if isinstance(v, list):
            return [str(x) for x in v]
        if isinstance(v, str):
            return [v]
        return []

    def _coerce_float_list(self, value: Any) -> List[float]:
        v = self._coerce_json(value, "list")
        if not isinstance(v, list):
            return []
        out: List[float] = []
        for x in v:
            if isinstance(x, (int, float)) and not isinstance(x, bool):
                out.append(float(x))
            else:
                try:
                    out.append(float(str(x).strip()))
                except Exception:
                    pass
        return out

    def _resolve_mode(self, mode: OutputMode) -> Literal["embed", "text"]:
        if mode == "auto":
            return "embed" if (self.valves.allow_external_cdn and HTMLResponse is not None) else "text"
        return mode

    # =====================================================
    # HTML wrapper + base styles
    # =====================================================

    def _wrap_html(self, title: str, body: str) -> str:
        return f"""<!doctype html>
<html>
<head>
 <meta charset="utf-8" />
 <meta name="viewport" content="width=device-width,initial-scale=1" />
 <title>{html.escape(title)}</title>
 <style>
 :root {{
 --bg: {self._BG};
 --panel: {self._PANEL};
 --header: {self._HEADER};
 --text: {self._TEXT};
 --muted: {self._MUTED};
 --border: {self._BORDER};
 --outer: {self._OUTER};
 --radius: {self._RADIUS};
 }}
 body {{
 margin: 0; padding: 14px;
 background: var(--bg);
 color: var(--text);
 font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif;
 font-size: 14px;
 line-height: 1.35;
 }}
 .card {{
 background: var(--panel);
 border: 1px solid var(--outer);
 border-radius: var(--radius);
 padding: 14px;
 }}
 .title {{
 font-size: 16px;
 font-weight: 900;
 margin: 0 0 10px 0;
 letter-spacing: 0.2px;
 }}
 .muted {{ color: var(--muted); }}
 pre {{
 background: rgba(255,255,255,0.02);
 border: 1px solid var(--outer);
 border-radius: var(--radius);
 padding: 12px;
 overflow: auto;
 white-space: pre-wrap;
 word-break: break-word;
 }}
 table {{
 width: 100%;
 border-collapse: collapse;
 overflow: hidden;
 border-radius: var(--radius);
 }}
 th {{
 text-align: left;
 padding: 8px;
 background: var(--header);
 color: var(--text);
 border-bottom: 1px solid var(--border);
 position: sticky;
 top: 0;
 z-index: 1;
 }}
 td {{
 padding: 8px;
 border-bottom: 1px solid var(--border);
 color: var(--text);
 background: var(--panel);
 vertical-align: top;
 }}
 </style>
</head>
<body>
{body}
</body>
</html>
"""

    # =====================================================
    # Markdown table helper
    # =====================================================

    def _markdown_table(self, title: str, cols: List[str], rows: List[Dict[str, Any]]) -> str:
        def cell(v: Any) -> str:
            s = "" if v is None else str(v)
            return s.replace("\n", " ").strip()

        header = "| " + " | ".join(cols) + " |"
        sep = "| " + " | ".join(["---"] * len(cols)) + " |"
        body_lines = ["| " + " | ".join(cell(r.get(c, "")) for c in cols) + " |" for r in rows]
        out = f"{header}\n{sep}\n" + "\n".join(body_lines)
        return f"### {title}\n\n{out}" if title else out

    # =====================================================
    # HTML tables (dark-mode-safe)
    # =====================================================

    def _html_table(self, title: str, cols: List[str], rows: List[Dict[str, Any]]) -> str:
        def esc(v: Any) -> str:
            s = "" if v is None else str(v)
            return html.escape(s)

        # detect numeric columns for right alignment
        numeric_cols: Set[str] = set()
        for c in cols:
            is_num = True
            for r in rows:
                v = r.get(c)
                if v is None:
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    continue
                is_num = False
                break
            if is_num:
                numeric_cols.add(c)

        ths = "".join(
            f"<th style='text-align:{'right' if c in numeric_cols else 'left'};'>{esc(c)}</th>"
            for c in cols
        )
        trs: List[str] = []
        for r in rows:
            tds = "".join(
                f"<td style='text-align:{'right' if c in numeric_cols else 'left'};'>{esc(r.get(c, ''))}</td>"
                for c in cols
            )
            trs.append(f"<tr>{tds}</tr>")

        return f"""
<div class="card">
 <div class="title">{html.escape(title)}</div>
 <div style="overflow:auto;border:1px solid var(--outer);border-radius:var(--radius);">
 <table>
 <thead><tr>{ths}</tr></thead>
 <tbody>{''.join(trs)}</tbody>
 </table>
 </div>
</div>
"""

    def _html_table_simple(self, cols: List[str], rows: List[Dict[str, Any]]) -> str:
        def esc(v: Any) -> str:
            s = "" if v is None else str(v)
            return html.escape(s)

        ths = "".join(f"<th>{esc(c)}</th>" for c in cols)
        trs: List[str] = []
        for r in rows:
            tds = "".join(f"<td>{esc(r.get(c, ''))}</td>" for c in cols)
            trs.append(f"<tr>{tds}</tr>")

        return f"""
<div style="overflow:auto;border:1px solid var(--outer);border-radius:var(--radius);">
 <table>
 <thead><tr>{ths}</tr></thead>
 <tbody>{''.join(trs)}</tbody>
 </table>
</div>
"""

    # =====================================================
    # Public: Data Tables
    # =====================================================

    async def render_table(
        self,
        rows: Any,
        *,
        title: str = "Table",
        mode: OutputMode = "auto",
    ) -> Union[str, HTMLResponse]:
        rows = self._coerce_json(rows, "list")
        if not isinstance(rows, list):
            return "Invalid 'rows': expected a list of objects."

        fixed_rows: List[Dict[str, Any]] = []
        for i, r in enumerate(rows):
            if isinstance(r, dict):
                fixed_rows.append(r)
            else:
                return f"Invalid row at index {i}: expected dict, got {type(r).__name__}."

        if not fixed_rows:
            return "No valid rows provided."

        rows = fixed_rows[: self.valves.max_rows]

        # union-of-keys in first-seen order
        cols: List[str] = []
        seen: Set[str] = set()
        for r in rows:
            for k in r.keys():
                ks = str(k)
                if ks not in seen:
                    seen.add(ks)
                    cols.append(ks)

        cols = cols[: self.valves.max_cols]
        resolved = self._resolve_mode(mode)

        if resolved == "text" or HTMLResponse is None:
            return self._markdown_table(title, cols, rows)

        page = self._wrap_html(title=title, body=self._html_table(title, cols, rows))
        return HTMLResponse(content=page, headers={"Content-Disposition": "inline"})

    # =====================================================
    # Comparison & Analysis
    # =====================================================

    def _find_best_values(
        self, criteria: List[str], scores: Dict[str, Dict[str, Any]], items: List[str]
    ) -> Dict[str, Set[float]]:
        best_values: Dict[str, Set[float]] = {}
        if not isinstance(scores, dict):
            return best_values

        for criterion in criteria:
            values: List[float] = []
            for item in items:
                item_scores = scores.get(item, {})
                if not isinstance(item_scores, dict):
                    continue
                v = item_scores.get(criterion)
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    values.append(float(v))
                else:
                    try:
                        values.append(float(str(v).strip()))
                    except Exception:
                        pass
            if values:
                best_values[criterion] = {max(values)}
        return best_values

    def _is_best_value(self, criterion: str, val: Any, best_vals: Dict[str, Set[float]]) -> bool:
        if criterion not in best_vals:
            return False
        if isinstance(val, (int, float)) and not isinstance(val, bool):
            return float(val) in best_vals[criterion]
        try:
            s = str(val).replace("\u2605", "").strip()
            return float(s) in best_vals[criterion]
        except Exception:
            return False

    def _html_comparison_table(
        self,
        title: str,
        cols: List[str],
        rows: List[Dict[str, Any]],
        best_values: Dict[str, Set[float]],
    ) -> str:
        def esc(v: Any) -> str:
            s = "" if v is None else str(v)
            return html.escape(s)

        numeric_cols: Set[str] = set()
        for c in cols:
            if c == "Item":
                continue
            is_num = True
            for r in rows:
                v = r.get(c)
                if v is None:
                    continue
                if isinstance(v, (int, float)) and not isinstance(v, bool):
                    continue
                is_num = False
                break
            if is_num:
                numeric_cols.add(c)

        ths = "".join(
            f"<th style='text-align:{'right' if c in numeric_cols else 'left'};'>{esc(c)}</th>"
            for c in cols
        )
        trs: List[str] = []
        for r in rows:
            tds: List[str] = []
            for c in cols:
                raw = r.get(c, "")
                disp = str(raw).replace(" \u2605", "")
                is_best = self._is_best_value(c, raw, best_values)
                bg = "#14532d" if is_best else "var(--panel)"
                fg = "#dcfce7" if is_best else "var(--text)"
                tds.append(
                    f"<td style='text-align:{'right' if c in numeric_cols else 'left'};"
                    f"background:{bg};color:{fg};'>{esc(disp)}</td>"
                )
            trs.append(f"<tr>{''.join(tds)}</tr>")

        return f"""
<div class="card">
 <div class="title">{html.escape(title)}</div>
 <div style="overflow:auto;border:1px solid var(--outer);border-radius:var(--radius);">
 <table>
 <thead><tr>{ths}</tr></thead>
 <tbody>{''.join(trs)}</tbody>
 </table>
 </div>
</div>
"""

    async def render_comparison_table(
        self,
        items: Any,
        criteria: Any,
        scores: Any,
        *,
        title: str = "Comparison",
        highlight_best: bool = True,
        mode: OutputMode = "auto",
    ) -> Union[str, HTMLResponse]:
        items_list = self._coerce_str_list(items)
        criteria_list = self._coerce_str_list(criteria)
        scores_dict = self._coerce_json(scores, "dict")
        if not isinstance(scores_dict, dict):
            scores_dict = {}

        cols = ["Item"] + criteria_list
        rows: List[Dict[str, Any]] = []
        for item in items_list:
            row: Dict[str, Any] = {"Item": item}
            item_scores = scores_dict.get(item, {}) if isinstance(scores_dict, dict) else {}
            if not isinstance(item_scores, dict):
                item_scores = {}
            for c in criteria_list:
                row[c] = item_scores.get(c, "\u2014")
            rows.append(row)

        resolved = self._resolve_mode(mode)
        if resolved == "text" or HTMLResponse is None:
            if highlight_best:
                best_vals = self._find_best_values(criteria_list, scores_dict, items_list)
                for r in rows:
                    for c in criteria_list:
                        v = r.get(c)
                        if self._is_best_value(c, v, best_vals):
                            r[c] = f"{v} \u2605"
            return self._markdown_table(title, cols, rows)

        best_vals_html = self._find_best_values(criteria_list, scores_dict, items_list) if highlight_best else {}
        page = self._wrap_html(
            title=title,
            body=self._html_comparison_table(title, cols, rows, best_vals_html),
        )
        return HTMLResponse(content=page, headers={"Content-Disposition": "inline"})

    # =====================================================
    # ASCII charts
    # =====================================================

    def _ascii_chart(
        self,
        x: List[Any],
        y: List[float],
        title: str,
        chart_type: str,
        x_label: str = "",
        y_label: str = "",
    ) -> str:
        if not y:
            return f"### {title}\n\nNo data to display."

        h = int(self.valves.ascii_chart_height)
        chart_type = (chart_type or "line").lower().strip()

        if chart_type == "bar":
            return self._ascii_bar_chart(x, y, title, h)
        if chart_type == "scatter":
            return self._ascii_scatter_chart(x, y, title, h)
        return self._ascii_line_chart(x, y, title, h)

    def _ascii_bar_chart(self, x: List[Any], y: List[float], title: str, height: int) -> str:
        max_y = max(y)
        min_y = min(y)
        rng = max_y - min_y if max_y != min_y else 1.0

        lines = [f"### {title}", "", "```text"]
        bar_chars = "\u2588\u2587\u2586\u2585\u2584\u2583\u2582 "

        for i in range(height, 0, -1):
            thr = min_y + (rng * i / height)
            axis = f"{thr:6.1f} \u2502"
            row = ""
            for v in y:
                if v >= thr:
                    row += "\u2588"
                elif v >= thr - (rng / height):
                    frac = (v - (thr - rng / height)) / (rng / height)
                    idx = min(int(frac * len(bar_chars)), len(bar_chars) - 1)
                    row += bar_chars[idx]
                else:
                    row += " "
                row += " "
            lines.append(axis + row)

        lines.append(" " * 8 + "\u2534" * (len(y) * 2))
        labels = ""
        for lab in x:
            labels += f"{str(lab)[:3]:^3} "
        lines.append(" " * 8 + labels)
        lines.append("```")
        return "\n".join(lines)

    def _ascii_line_chart(self, x: List[Any], y: List[float], title: str, height: int) -> str:
        max_y = max(y)
        min_y = min(y)
        rng = max_y - min_y if max_y != min_y else 1.0

        grid = [[" " for _ in range(len(y) * 2)] for _ in range(height)]
        for i, v in enumerate(y):
            row = int((max_y - v) / rng * (height - 1)) if rng > 0 else height // 2
            row = max(0, min(height - 1, row))
            col = i * 2
            grid[row][col] = "\u25cf"

            if i > 0:
                pv = y[i - 1]
                prow = int((max_y - pv) / rng * (height - 1)) if rng > 0 else height // 2
                prow = max(0, min(height - 1, prow))
                start, end = sorted([prow, row])
                for r in range(start, end + 1):
                    if r != prow and r != row:
                        grid[r][col - 1] = "\u2502"
                if prow == row:
                    grid[row][col - 1] = "\u2500"

        lines = [f"### {title}", "", "```text"]
        for i, row in enumerate(grid):
            thr = max_y - (rng * i / (height - 1)) if height > 1 else max_y
            lines.append(f"{thr:6.1f} \u2502" + "".join(row))

        lines.append(" " * 8 + "\u2534" * (len(y) * 2))
        labels = ""
        for lab in x:
            labels += f"{str(lab)[:3]:^3} "
        lines.append(" " * 8 + labels)
        lines.append("```")
        return "\n".join(lines)

    def _ascii_scatter_chart(self, x: List[Any], y: List[float], title: str, height: int) -> str:
        max_y = max(y)
        min_y = min(y)
        rng = max_y - min_y if max_y != min_y else 1.0

        grid = [[" " for _ in range(len(y) * 2)] for _ in range(height)]
        for i, v in enumerate(y):
            row = int((max_y - v) / rng * (height - 1)) if rng > 0 else height // 2
            row = max(0, min(height - 1, row))
            col = i * 2
            grid[row][col] = "\u25cf"

        lines = [f"### {title}", "", "```text"]
        for i, row in enumerate(grid):
            thr = max_y - (rng * i / (height - 1)) if height > 1 else max_y
            lines.append(f"{thr:6.1f} \u2502" + "".join(row))

        lines.append(" " * 8 + "\u2534" * (len(y) * 2))
        labels = ""
        for lab in x:
            labels += f"{str(lab)[:3]:^3} "
        lines.append(" " * 8 + labels)
        lines.append("```")
        return "\n".join(lines)

    # =====================================================
    # Public: Charts
    # =====================================================

    async def render_chart(
        self,
        x: Any,
        y: Any,
        *,
        title: str = "Chart",
        chart_type: ChartType = "line",
        mode: OutputMode = "auto",
        x_label: str = "",
        y_label: str = "",
    ) -> Union[str, HTMLResponse]:
        x_list = self._coerce_json(x, "list")
        y_list = self._coerce_float_list(y)

        if not isinstance(x_list, list):
            return "Invalid 'x': expected a list."
        if len(x_list) != len(y_list):
            return f"x and y must have the same length (got {len(x_list)} and {len(y_list)})."
        if not x_list:
            return "No data provided (x and y are empty)."

        resolved = self._resolve_mode(mode)
        if resolved == "text" or not self.valves.allow_external_cdn or HTMLResponse is None:
            return self._ascii_chart(x_list, y_list, title, chart_type, x_label, y_label)

        # Plotly embed
        chart_id = f"chart_{abs(hash(title)) % 10_000_000}_{len(x_list)}_{len(y_list)}"
        trace: Dict[str, Any] = {
            "x": x_list,
            "y": y_list,
            "type": "bar" if chart_type == "bar" else "scatter",
        }
        if chart_type == "line":
            trace["mode"] = "lines+markers"
        elif chart_type == "scatter":
            trace["mode"] = "markers"

        layout_cfg: Dict[str, Any] = {
            "title": {"text": title, "font": {"size": 16, "color": self._TEXT}},
            "paper_bgcolor": self._PANEL,
            "plot_bgcolor": self._PANEL,
            "font": {"color": self._TEXT},
            "margin": {"l": 50, "r": 20, "t": 45, "b": 45},
            "xaxis": {"gridcolor": self._OUTER},
            "yaxis": {"gridcolor": self._OUTER},
        }
        if x_label:
            layout_cfg["xaxis"]["title"] = {"text": x_label}
        if y_label:
            layout_cfg["yaxis"]["title"] = {"text": y_label}

        body = f"""
<div class="card">
 <div id="{chart_id}" style="width:{self.valves.embed_chart_width};height:{self.valves.embed_chart_height}px;"></div>
</div>
<script src="https://cdn.plot.ly/plotly-{self._PLOTLY_CDN_VERSION}.min.js"></script>
<script>
 (function(){{
 const trace = {json.dumps(trace)};
 const layout = {json.dumps(layout_cfg)};
 Plotly.newPlot("{chart_id}", [trace], layout, {{responsive:true, displayModeBar:false}});
 }})();
</script>
"""
        page = self._wrap_html(title=title, body=body)
        return HTMLResponse(content=page, headers={"Content-Disposition": "inline"})

    async def render_multi_chart(
        self,
        series: Any,
        *,
        title: str = "Chart",
        chart_type: ChartType = "line",
        mode: OutputMode = "auto",
        x_label: str = "",
        y_label: str = "",
    ) -> Union[str, HTMLResponse]:
        series_list = self._coerce_json(series, "list")
        if not isinstance(series_list, list):
            return "Invalid 'series': expected a list of objects."

        fixed: List[Dict[str, Any]] = []
        for i, s in enumerate(series_list):
            if isinstance(s, dict):
                fixed.append(s)
            else:
                return f"Invalid series item at index {i}: expected dict, got {type(s).__name__}."
        if not fixed:
            return "No valid series items found."

        resolved = self._resolve_mode(mode)
        if resolved == "text" or not self.valves.allow_external_cdn or HTMLResponse is None:
            out = f"### {title}\n\n"
            for s in fixed:
                name = str(s.get("name", "Series"))
                x_list = self._coerce_json(s.get("x", []), "list")
                y_list = self._coerce_float_list(s.get("y", []))
                if not isinstance(x_list, list):
                    x_list = []
                out += self._ascii_chart(x_list, y_list, name, chart_type)
                out += "\n\n"
            return out.rstrip() + "\n"

        traces: List[Dict[str, Any]] = []
        for s in fixed:
            name = str(s.get("name", "Series"))
            x_list = self._coerce_json(s.get("x", []), "list")
            y_list = self._coerce_float_list(s.get("y", []))
            if not isinstance(x_list, list):
                x_list = []

            trace: Dict[str, Any] = {
                "name": name,
                "x": x_list,
                "y": y_list,
                "type": "bar" if chart_type == "bar" else "scatter",
            }
            if chart_type == "line":
                trace["mode"] = "lines+markers"
            elif chart_type == "scatter":
                trace["mode"] = "markers"
            traces.append(trace)

        chart_id = f"multichart_{abs(hash(title)) % 10_000_000}_{len(traces)}"
        layout_cfg: Dict[str, Any] = {
            "title": {"text": title, "font": {"size": 16, "color": self._TEXT}},
            "paper_bgcolor": self._PANEL,
            "plot_bgcolor": self._PANEL,
            "font": {"color": self._TEXT},
            "margin": {"l": 50, "r": 20, "t": 45, "b": 45},
            "xaxis": {"gridcolor": self._OUTER},
            "yaxis": {"gridcolor": self._OUTER},
        }
        if x_label:
            layout_cfg["xaxis"]["title"] = {"text": x_label}
        if y_label:
            layout_cfg["yaxis"]["title"] = {"text": y_label}

        body = f"""
<div class="card">
 <div id="{chart_id}" style="width:{self.valves.embed_chart_width};height:{self.valves.embed_chart_height}px;"></div>
</div>
<script src="https://cdn.plot.ly/plotly-{self._PLOTLY_CDN_VERSION}.min.js"></script>
<script>
 (function(){{
 const traces = {json.dumps(traces)};
 const layout = {json.dumps(layout_cfg)};
 Plotly.newPlot("{chart_id}", traces, layout, {{responsive:true, displayModeBar:false}});
 }})();
</script>
"""
        page = self._wrap_html(title=title, body=body)
        return HTMLResponse(content=page, headers={"Content-Disposition": "inline"})

    async def render_line_chart(
        self,
        x: Any,
        y: Any,
        *,
        title: str = "Line Chart",
        height: int = 12,
        width: int = 60,
    ) -> str:
        x_list = self._coerce_json(x, "list")
        y_list = self._coerce_float_list(y)
        if not isinstance(x_list, list):
            return "Invalid 'x': expected a list."
        if not y_list:
            return "No data provided (y values are empty)."
        old = self.valves.ascii_chart_height
        self.valves.ascii_chart_height = max(5, min(int(height), 40))
        try:
            return self._ascii_line_chart(x_list, y_list, title, int(self.valves.ascii_chart_height))
        finally:
            self.valves.ascii_chart_height = old

    async def render_bar_chart(
        self,
        x: Any,
        y: Any,
        *,
        title: str = "Bar Chart",
        height: int = 12,
        width: int = 60,
    ) -> str:
        x_list = self._coerce_json(x, "list")
        y_list = self._coerce_float_list(y)
        if not isinstance(x_list, list):
            return "Invalid 'x': expected a list."
        if not y_list:
            return "No data provided (y values are empty)."
        old = self.valves.ascii_chart_height
        self.valves.ascii_chart_height = max(5, min(int(height), 40))
        try:
            return self._ascii_bar_chart(x_list, y_list, title, int(self.valves.ascii_chart_height))
        finally:
            self.valves.ascii_chart_height = old

    # =====================================================
    # Heatmaps & Matrices
    # =====================================================

    def _ascii_heatmap(self, data: List[List[float]], row_labels: List[str], col_labels: List[str], title: str) -> str:
        if not data:
            return f"### {title}\n\nNo data."

        all_vals = [v for row in data for v in row] if data else []
        min_v = min(all_vals) if all_vals else 0.0
        max_v = max(all_vals) if all_vals else 1.0
        rng = max_v - min_v if max_v != min_v else 1.0

        blocks = " \u2591\u2592\u2593\u2588"
        lines = [f"### {title}", "", "```text"]
        header = " " * 12 + " ".join(f"{str(c)[:8]:^8}" for c in col_labels)
        lines.append(header)
        lines.append("")

        for i, rl in enumerate(row_labels):
            if i >= len(data):
                break
            row = data[i]
            row_str = f"{str(rl)[:10]:10} \u2502"
            for j, _ in enumerate(col_labels):
                v = row[j] if j < len(row) else 0.0
                norm = (v - min_v) / rng if rng > 0 else 0.5
                idx = min(int(norm * (len(blocks) - 1)), len(blocks) - 1)
                row_str += f" {blocks[idx] * 2} "
            lines.append(row_str)

        lines.append("")
        lines.append(f"Range: {min_v:.2f} to {max_v:.2f}")
        lines.append("```")
        return "\n".join(lines)

    async def render_heatmap(
        self,
        data: Any,
        row_labels: Any,
        col_labels: Any,
        *,
        title: str = "Heatmap",
        mode: OutputMode = "auto",
    ) -> Union[str, HTMLResponse]:
        data_v = self._coerce_json(data, "list")
        r = self._coerce_str_list(row_labels)
        c = self._coerce_str_list(col_labels)

        fixed: List[List[float]] = []
        if isinstance(data_v, list):
            for row in data_v:
                row_l = self._coerce_json(row, "list")
                if not isinstance(row_l, list):
                    continue
                out_row: List[float] = []
                for v in row_l:
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        out_row.append(float(v))
                    else:
                        try:
                            out_row.append(float(str(v).strip()))
                        except Exception:
                            out_row.append(0.0)
                fixed.append(out_row)

        if len(fixed) > self.valves.max_rows:
            return f"Data too large: {len(fixed)} rows exceeds max_rows={self.valves.max_rows}."

        if not fixed:
            return "No valid heatmap data provided."

        # Normalise row / column labels
        if not r:
            r = [f"Row {i+1}" for i in range(len(fixed))]
        if not c:
            max_len = max((len(row) for row in fixed), default=0)
            c = [f"Col {j+1}" for j in range(max_len)]

        # Cap columns for safety
        if len(c) > self.valves.max_cols:
            c = c[: self.valves.max_cols]
            fixed = [row[: self.valves.max_cols] for row in fixed]

        resolved = self._resolve_mode(mode)
        if resolved == "text" or not self.valves.allow_external_cdn or HTMLResponse is None:
            # ASCII fallback
            return self._ascii_heatmap(fixed, r[: len(fixed)], c, title)

        # Plotly embed
        heat_id = f"heat_{abs(hash(title)) % 10_000_000}_{len(fixed)}_{len(c)}"

        # Ensure rectangular z
        z: List[List[float]] = []
        for i, row in enumerate(fixed):
            if i >= self.valves.max_rows:
                break
            rr = row[: len(c)]
            if len(rr) < len(c):
                rr = rr + [0.0] * (len(c) - len(rr))
            z.append(rr)

        trace = {
            "type": "heatmap",
            "z": z,
            "x": c,
            "y": r[: len(z)],
            "hoverongaps": False,
        }

        layout_cfg: Dict[str, Any] = {
            "title": {"text": title, "font": {"size": 16, "color": self._TEXT}},
            "paper_bgcolor": self._PANEL,
            "plot_bgcolor": self._PANEL,
            "font": {"color": self._TEXT},
            "margin": {"l": 70, "r": 20, "t": 50, "b": 60},
            "xaxis": {"gridcolor": self._OUTER, "tickangle": -20},
            "yaxis": {"gridcolor": self._OUTER},
        }

        body = f"""
<div class="card">
 <div id="{heat_id}" style="width:{self.valves.embed_chart_width};height:{self.valves.embed_chart_height}px;"></div>
</div>
<script src="https://cdn.plot.ly/plotly-{self._PLOTLY_CDN_VERSION}.min.js"></script>
<script>
 (function(){{
 const trace = {json.dumps(trace)};
 const layout = {json.dumps(layout_cfg)};
 Plotly.newPlot("{heat_id}", [trace], layout, {{responsive:true, displayModeBar:false}});
 }})();
</script>
"""
        page = self._wrap_html(title=title, body=body)
        return HTMLResponse(content=page, headers={"Content-Disposition": "inline"})

    # =====================================================
    # Timelines & Workflows (text-first, HTML pre fallback)
    # =====================================================

    def _as_markdown_codeblock(self, title: str, text: str) -> str:
        t = f"### {title}\n\n" if title else ""
        return f"{t}```text\n{text.rstrip()}\n```"

    def _as_html_pre_card(self, title: str, text: str) -> str:
        return self._wrap_html(
            title=title or "Visual",
            body=f"""
<div class="card">
 <div class="title">{html.escape(title or '')}</div>
 <pre>{html.escape(text)}</pre>
</div>
""",
        )

    async def render_timeline(
        self,
        events: Any,
        *,
        title: str = "Timeline",
        mode: OutputMode = "auto",
        show_dates: bool = True,
    ) -> Union[str, HTMLResponse]:
        """
        events: list of objects like:
        { "date": "2026-01-01", "label": "Kickoff", "detail": "Optional" }
        """
        ev = self._coerce_json(events, "list")
        if not isinstance(ev, list):
            return "Invalid 'events': expected a list of objects."

        fixed: List[Dict[str, Any]] = []
        for i, e in enumerate(ev):
            if isinstance(e, dict):
                fixed.append(e)
            else:
                return f"Invalid event at index {i}: expected dict, got {type(e).__name__}."
        if not fixed:
            return "No events provided."

        fixed = fixed[: self.valves.max_rows]

        lines: List[str] = []
        for e in fixed:
            d = str(e.get("date", "")).strip()
            lab = str(e.get("label", "")).strip() or "Event"
            detail = str(e.get("detail", "")).strip()
            left = f"{d} \u2014 " if (show_dates and d) else ""
            s = f"{left}{lab}"
            if detail:
                s += f" :: {detail}"
            lines.append(s)

        text = "\n".join(lines)
        resolved = self._resolve_mode(mode)
        if resolved == "text" or HTMLResponse is None:
            return self._as_markdown_codeblock(title, text)

        return HTMLResponse(
            content=self._as_html_pre_card(title, text),
            headers={"Content-Disposition": "inline"},
        )

    async def render_flowchart(
        self,
        steps: Any,
        *,
        title: str = "Flowchart",
        mode: OutputMode = "auto",
        direction: Literal["lr", "tb"] = "tb",
    ) -> Union[str, HTMLResponse]:
        """
        steps: list of objects like:
        { "from": "A", "to": "B", "label": "optional" }
        Produces an ASCII flow.
        """
        v = self._coerce_json(steps, "list")
        if not isinstance(v, list):
            return "Invalid 'steps': expected a list of objects."

        edges: List[Tuple[str, str, str]] = []
        for i, s in enumerate(v[: self.valves.max_rows]):
            if not isinstance(s, dict):
                return f"Invalid step at index {i}: expected dict, got {type(s).__name__}."
            a = str(s.get("from", "")).strip()
            b = str(s.get("to", "")).strip()
            lbl = str(s.get("label", "")).strip()
            if not a or not b:
                continue
            edges.append((a, b, lbl))

        if not edges:
            return "No valid edges found. Each step must include 'from' and 'to'."

        if direction == "lr":
            # naive left-to-right chain rendering (preserve first-seen order)
            order: List[str] = []
            seen: Set[str] = set()
            for a, b, _ in edges:
                if a not in seen:
                    seen.add(a)
                    order.append(a)
                if b not in seen:
                    seen.add(b)
                    order.append(b)

            # build a single-line representation
            parts: List[str] = []
            for idx, node in enumerate(order):
                parts.append(f"[{node}]")
                if idx < len(order) - 1:
                    nxt = order[idx + 1]
                    lbl = ""
                    for a, b, l in edges:
                        if a == node and b == nxt and l:
                            lbl = l
                            break
                    parts.append(f"--{lbl}-->" if lbl else "---->")
            text = " ".join(parts)
        else:
            # top-to-bottom: each edge on its own line
            lines = []
            for a, b, lbl in edges:
                mid = f" --{lbl}--> " if lbl else " --> "
                lines.append(f"[{a}]{mid}[{b}]")
            text = "\n".join(lines)

        resolved = self._resolve_mode(mode)
        if resolved == "text" or HTMLResponse is None:
            return self._as_markdown_codeblock(title, text)

        return HTMLResponse(
            content=self._as_html_pre_card(title, text),
            headers={"Content-Disposition": "inline"},
        )

    async def render_tree(
        self,
        tree: Any,
        *,
        title: str = "Tree",
        mode: OutputMode = "auto",
        root_label: str = "root",
        max_depth: int = 12,
    ) -> Union[str, HTMLResponse]:
        """
        tree: either
        - dict nested objects
        - list of edges: { "parent": "...", "child": "..." }
        """
        max_depth = max(1, min(int(max_depth), 50))

        def render_from_dict(node: Any, prefix: str = "", depth: int = 0) -> List[str]:
            if depth > max_depth:
                return [prefix + "\u2026"]
            out: List[str] = []
            if isinstance(node, dict):
                for i, (k, v) in enumerate(node.items()):
                    is_last = i == (len(node) - 1)
                    branch = "\u2514\u2500 " if is_last else "\u251c\u2500 "
                    out.append(prefix + branch + str(k))
                    ext = "  " if is_last else "\u2502 "
                    out.extend(render_from_dict(v, prefix + ext, depth + 1))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    is_last = i == (len(node) - 1)
                    branch = "\u2514\u2500 " if is_last else "\u251c\u2500 "
                    if isinstance(v, (dict, list)):
                        out.append(prefix + branch)
                    else:
                        out.append(prefix + branch + str(v))
                    ext = "  " if is_last else "\u2502 "
                    out.extend(render_from_dict(v, prefix + ext, depth + 1))
            else:
                out.append(prefix + str(node))
            return out

        def render_from_edges(edges: List[Dict[str, Any]]) -> str:
            # build adjacency
            children: Dict[str, List[str]] = {}
            all_nodes: Set[str] = set()
            child_nodes: Set[str] = set()

            for e in edges:
                p = str(e.get("parent", "")).strip()
                ch = str(e.get("child", "")).strip()
                if not p or not ch:
                    continue
                children.setdefault(p, []).append(ch)
                all_nodes.update([p, ch])
                child_nodes.add(ch)

            root = (next(iter(all_nodes - child_nodes), None) or root_label) if all_nodes else root_label

            def walk(n: str, prefix: str = "", depth: int = 0) -> List[str]:
                if depth > max_depth:
                    return [prefix + "\u2026"]
                out: List[str] = []
                kids = children.get(n, [])
                for i, k in enumerate(kids):
                    is_last = i == (len(kids) - 1)
                    branch = "\u2514\u2500 " if is_last else "\u251c\u2500 "
                    out.append(prefix + branch + k)
                    ext = "  " if is_last else "\u2502 "
                    out.extend(walk(k, prefix + ext, depth + 1))
                return out

            lines = [str(root)]
            lines.extend(walk(str(root)))
            return "\n".join(lines)

        v = self._coerce_json(tree, "any")

        text: str
        if isinstance(v, dict):
            lines = [root_label]
            lines.extend(render_from_dict(v))
            text = "\n".join(lines)
        elif isinstance(v, list) and (not v or isinstance(v[0], dict)):
            fixed_edges: List[Dict[str, Any]] = []
            for i, e in enumerate(v[: self.valves.max_rows]):
                if isinstance(e, dict):
                    fixed_edges.append(e)
                else:
                    return f"Invalid edge at index {i}: expected dict, got {type(e).__name__}."
            text = render_from_edges(fixed_edges)
        else:
            return "Invalid 'tree': expected a dict (nested) or a list of {parent, child} edges."

        resolved = self._resolve_mode(mode)
        if resolved == "text" or HTMLResponse is None:
            return self._as_markdown_codeblock(title, text)

        return HTMLResponse(
            content=self._as_html_pre_card(title, text),
            headers={"Content-Disposition": "inline"},
        )
