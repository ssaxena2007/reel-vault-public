import json
import logging
import re
import time
from google import genai
from google.genai import types

logger = logging.getLogger(__name__)

_JSON_SCHEMA = """
{
  "title": "A short, descriptive title (max 60 chars)",
  "category": "The single best-fit category — one of: Tech, Business, Life Advice, Religion & Spirituality, Health & Fitness, Finance, Science, Other",
  "content_type": "One of: Tutorial, Story, Advice, Motivation, Information, Debate, Comedy, Other",
  "summary": "2-3 sentences capturing what this is about and why it matters",
  "tags": [
    "specific-topic-tag",
    "another-tag"
  ],
  "key_learnings": [
    "The most important insight or lesson",
    "Second insight...",
    "..."
  ],
  "action_items": [
    "Concrete thing to try or do based on this content"
  ],
  "notable_quotes": [
    "Any memorable or impactful line"
  ]
}"""

_TAG_RULES = """
Tag rules for the "tags" field — this is the most important field for connecting notes:
- Generate 4 to 10 lowercase, hyphenated tags
- Be SPECIFIC: prefer "startup-fundraising" over "business", "stoicism" over "life-advice", "react-hooks" over "tech"
- Include topic tags: what is this actually about? (e.g. stoicism, productivity, ai-agents, cold-outreach, intermittent-fasting, stoicism, quran, comedy, dark-humor)
- Include vibe/mood tags if relevant: funny, inspiring, thought-provoking, controversial, wholesome
- Include audience tags if obvious: founders, students, muslims, developers, gym-goers
- Do NOT include format tags like "reel" or "video" — those are added separately
- Return tags as an array of strings, no # prefix"""

_COMMON_RULES = """
Other rules:
- key_learnings: 3 to 7 points, focus on actual value not plot summary
- action_items: can be an empty array [] if nothing actionable
- notable_quotes: can be an empty array [] if nothing quotable
- If on-screen text contains important info (formulas, steps, names), include it
- Return ONLY valid JSON with no markdown, no code fences, no extra text"""

IMAGE_PROMPT = (
    "Look at this image (or series of images) carefully — read all on-screen text, "
    "observe what's shown, and understand the message being conveyed.\n\n"
    "Extract the most valuable content and return a JSON object with exactly these fields:"
    + _JSON_SCHEMA + _TAG_RULES + _COMMON_RULES
)

VIDEO_PROMPT = (
    "Watch this video carefully — listen to what's said, read any on-screen text, "
    "and observe what's being demonstrated.\n\n"
    "Extract the most valuable content and return a JSON object with exactly these fields:"
    + _JSON_SCHEMA + _TAG_RULES + _COMMON_RULES
)

PROMPT = VIDEO_PROMPT  # backwards compat alias


def _parse_json(text: str) -> dict:
    """Strip code fences and parse JSON, with repair fallback for malformed output."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    # First try clean parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Fallback: extract the outermost {...} block and try again
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Last resort: use json_repair if available
    try:
        from json_repair import repair_json
        return json.loads(repair_json(text))
    except Exception:
        pass

    raise ValueError(f"Could not parse Gemini response as JSON: {text[:200]}")


class ReelAnalyzer:
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)

    def analyze(self, video_path: str) -> dict:
        logger.info(f"Uploading video to Gemini: {video_path}")
        with open(video_path, "rb") as f:
            video_file = self.client.files.upload(
                file=f,
                config=types.UploadFileConfig(mime_type="video/mp4"),
            )

        # Wait for processing
        while video_file.state.name == "PROCESSING":
            time.sleep(2)
            video_file = self.client.files.get(name=video_file.name)

        if video_file.state.name == "FAILED":
            raise ValueError("Gemini failed to process the video file.")

        logger.info("Video processed. Analyzing content...")
        # Retry on 429 with the wait time Gemini tells us
        for attempt in range(4):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[video_file, PROMPT],
                )
                break
            except Exception as e:
                err = str(e)
                if attempt < 3 and ("429" in err or "503" in err):
                    wait = 30
                    match = re.search(r"retry in (\d+)", err)
                    if match:
                        wait = int(match.group(1)) + 5
                    logger.warning(f"Gemini unavailable ({err[:40]}...), waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

        # Clean up uploaded file from Gemini
        try:
            self.client.files.delete(name=video_file.name)
        except Exception:
            pass

        return _parse_json(response.text)

    def analyze_images(self, image_paths: list) -> dict:
        logger.info(f"Uploading {len(image_paths)} image(s) to Gemini...")
        uploaded = []
        for path in image_paths:
            with open(path, "rb") as f:
                img_file = self.client.files.upload(
                    file=f,
                    config=types.UploadFileConfig(mime_type="image/jpeg"),
                )
            uploaded.append(img_file)

        logger.info("Images uploaded. Analyzing content...")
        for attempt in range(4):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=[*uploaded, IMAGE_PROMPT],
                )
                break
            except Exception as e:
                err = str(e)
                if attempt < 3 and ("429" in err or "503" in err):
                    wait = 30
                    match = re.search(r"retry in (\d+)", err)
                    if match:
                        wait = int(match.group(1)) + 5
                    logger.warning(f"Gemini unavailable ({err[:40]}...), waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

        for img_file in uploaded:
            try:
                self.client.files.delete(name=img_file.name)
            except Exception:
                pass

        return _parse_json(response.text)
