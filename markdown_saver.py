import os
import logging
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Set OBSIDIAN_VAULT_PATH in .env to write directly to your vault.
# On GitHub Actions this falls back to the repo's vault/ folder.
VAULT_DIR = os.getenv("OBSIDIAN_VAULT_PATH", "vault")


def is_processed(shortcode: str) -> bool:
    return Path(VAULT_DIR, f"{shortcode}.md").exists()


def save(analysis: dict, shortcode: str, source_url: str = None, starred: bool = False, media_format: str = "reel") -> str:
    os.makedirs(VAULT_DIR, exist_ok=True)

    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    category = analysis.get("category", "Other")
    content_type = analysis.get("content_type", "Other")

    # Build tag list: format + category + content-type + Gemini-generated topic tags
    format_tag = media_format.lower().replace(" ", "-")  # reel, post, carousel
    category_tag = category.lower().replace(" ", "-").replace("&", "and")
    content_type_tag = content_type.lower()
    gemini_tags = [t.lower().replace(" ", "-") for t in analysis.get("tags", [])]

    all_tags = [format_tag, category_tag, content_type_tag] + gemini_tags
    # Deduplicate while preserving order
    seen_tags = set()
    unique_tags = []
    for t in all_tags:
        if t not in seen_tags:
            seen_tags.add(t)
            unique_tags.append(t)

    tags_yaml = "[" + ", ".join(unique_tags) + "]"

    lines = []

    # YAML frontmatter — Obsidian reads this as page properties
    lines.append("---")
    lines.append(f"title: \"{analysis.get('title', 'Untitled')}\"")
    lines.append(f"date: {date}")
    lines.append(f"category: {category}")
    lines.append(f"type: {content_type}")
    lines.append(f"format: {media_format}")
    if source_url:
        lines.append(f"source: \"{source_url}\"")
    if starred:
        lines.append("starred: true")
    lines.append(f"tags: {tags_yaml}")
    lines.append("---")
    lines.append("")

    lines.append(f"# {analysis.get('title', 'Untitled')}")
    lines.append("")
    lines.append(f"> {analysis.get('summary', '')}")
    lines.append("")

    key_learnings = analysis.get("key_learnings", [])
    if key_learnings:
        lines.append("## Key Learnings")
        for item in key_learnings:
            lines.append(f"- {item}")
        lines.append("")

    action_items = analysis.get("action_items", [])
    if action_items:
        lines.append("## Action Items")
        for item in action_items:
            lines.append(f"- [ ] {item}")
        lines.append("")

    quotes = analysis.get("notable_quotes", [])
    if quotes:
        lines.append("## Notable Quotes")
        for q in quotes:
            lines.append(f"> {q}")
        lines.append("")

    path = Path(VAULT_DIR) / f"{shortcode}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.info(f"Saved → {path}")
    return str(path)


def star(shortcode: str) -> str:
    """Add starred: true to the frontmatter of an already-saved note."""
    path = Path(VAULT_DIR) / f"{shortcode}.md"
    if not path.exists():
        return None

    content = path.read_text(encoding="utf-8")

    # Already starred — nothing to do
    if "starred: true" in content:
        logger.info(f"Already starred: {path}")
        return str(path)

    # Insert after the opening ---
    content = content.replace("---\n", "---\nstarred: true\n", 1)
    path.write_text(content, encoding="utf-8")
    logger.info(f"★ Starred → {path}")
    return str(path)
