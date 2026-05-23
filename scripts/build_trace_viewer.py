# ABOUTME: Builds a standalone trace review HTML file with embedded conversation data.
# ABOUTME: Reads trace_summaries.json and inlines conversation.jsonl content for offline review.

from __future__ import annotations

import json
import sys
from pathlib import Path


def load_conversation(trace_path: str) -> list[dict] | None:
    """Load and parse a conversation.jsonl file."""
    p = Path(trace_path)
    if not p.exists():
        return None
    messages = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            messages.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return messages


def build_standalone(
    summaries_path: Path,
    html_template_path: Path,
    output_path: Path,
    max_traces: int | None = None,
) -> None:
    """Build a standalone HTML file with embedded trace data."""
    summaries = json.loads(summaries_path.read_text())
    html = html_template_path.read_text()

    if max_traces:
        summaries = summaries[:max_traces]

    # Embed conversations into summaries
    loaded = 0
    skipped = 0
    for s in summaries:
        trace_path = s.get("trace_path", "")
        if trace_path:
            messages = load_conversation(trace_path)
            if messages:
                s["_conversation"] = messages
                loaded += 1
            else:
                skipped += 1

    # Build the data injection script
    data_script = f"""
<script>
// Auto-load embedded trace data
(function() {{
  const embeddedData = {json.dumps(summaries, separators=(',', ':'))};
  allSummaries = embeddedData;
  initApp();
}})();
</script>
"""

    # Remove the file picker loading message and inject data
    html = html.replace(
        '<div class="loading" id="loading-msg">\n'
        '      Drop <code>trace_summaries.json</code> here or use the file picker below.<br><br>\n'
        '      <input type="file" id="file-picker" accept=".json" onchange="handleFileLoad(event)">\n'
        '    </div>',
        '<div class="loading" id="loading-msg">Loading traces...</div>',
    )

    # Inject data script before closing body tag
    html = html.replace("</body>", data_script + "</body>")

    output_path.write_text(html)
    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"Built {output_path} ({size_mb:.1f} MB)")
    print(f"Embedded {loaded} conversations, skipped {skipped}")


def main() -> None:
    """CLI: python -m scripts.build_trace_viewer [summaries.json] [output.html]"""
    summaries_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("scripts/trace_summaries.json")
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("scripts/trace_viewer.html")
    html_template = Path("scripts/trace_review.html")

    if not summaries_path.exists():
        print(f"Error: {summaries_path} not found. Run trace_summarizer first.", file=sys.stderr)
        sys.exit(1)

    if not html_template.exists():
        print(f"Error: {html_template} not found.", file=sys.stderr)
        sys.exit(1)

    build_standalone(summaries_path, html_template, output_path)


if __name__ == "__main__":
    main()
