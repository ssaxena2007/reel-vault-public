import argparse
import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv

from analyzer import ReelAnalyzer
from instagram import InstagramBot
import markdown_saver as vault

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "60"))


def check_env():
    required = ["INSTAGRAM_USERNAME", "INSTAGRAM_PASSWORD", "GEMINI_API_KEY"]
    missing = [k for k in required if not os.getenv(k)]
    if missing:
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        raise SystemExit(1)


def process_once(bot: InstagramBot, analyzer: ReelAnalyzer):
    logger.info("Checking for new posts in DMs...")
    new_posts = bot.get_new_posts()
    logger.info(f"Found {len(new_posts)} post(s) in DMs.")

    processed = 0
    for shortcode, source_url, playable_url, starred in new_posts:
        # If already saved and starred — just update the frontmatter, no re-download
        if vault.is_processed(shortcode):
            if starred:
                vault.star(shortcode)
            else:
                logger.info(f"Already saved {shortcode}, skipping.")
            continue

        media_paths = []
        try:
            logger.info(f"Downloading {shortcode}{'  ★' if starred else ''}...")
            kind, media = bot.download_media(shortcode, playable_url=playable_url)

            logger.info("Analyzing with Gemini...")
            if kind == "video":
                media_paths = [media]
                analysis = analyzer.analyze(media)
                media_format = "reel" if "/reel/" in source_url else "video"
            else:
                media_paths = media
                analysis = analyzer.analyze_images(media)
                media_format = "carousel" if len(media_paths) > 1 else "post"

            logger.info(f"  Title    : {analysis.get('title')}")
            logger.info(f"  Category : {analysis.get('category')}")
            logger.info(f"  Tags     : {', '.join(analysis.get('tags', []))}")

            path = vault.save(analysis, shortcode=shortcode, source_url=source_url, starred=starred, media_format=media_format)
            logger.info(f"Saved → {path}")
            processed += 1

        except Exception as e:
            logger.error(f"Failed processing {shortcode}: {e}", exc_info=True)
        finally:
            for p in media_paths:
                if p and Path(p).exists():
                    os.remove(p)

    return processed


def main():
    parser = argparse.ArgumentParser(description="Reel Vault — Instagram reels to markdown")
    parser.add_argument("--once", action="store_true", help="Run once and exit (GitHub Actions mode)")
    args = parser.parse_args()

    check_env()

    bot = InstagramBot(os.getenv("INSTAGRAM_USERNAME"), os.getenv("INSTAGRAM_PASSWORD"))
    analyzer = ReelAnalyzer(os.getenv("GEMINI_API_KEY"))

    if args.once:
        logger.info("Running in one-shot mode (GitHub Actions).")
        count = process_once(bot, analyzer)
        logger.info(f"Done. Processed {count} post(s).")
    else:
        logger.info("Running in continuous mode. Ctrl+C to stop.")
        while True:
            try:
                process_once(bot, analyzer)
            except Exception as e:
                logger.error(f"Unexpected error: {e}", exc_info=True)
            logger.info(f"Sleeping {POLL_INTERVAL}s...\n")
            time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
