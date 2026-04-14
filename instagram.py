import os
import logging
import requests
from pathlib import Path
from urllib.parse import urlparse
from instagrapi import Client

logger = logging.getLogger(__name__)

SESSION_FILE = "session.json"


class InstagramBot:
    def __init__(self, username: str, password: str):
        self.client = Client()
        self.client.set_device({
            "app_version": "269.0.0.18.75",
            "android_version": 26,
            "android_release": "8.0.0",
            "dpi": "480dpi",
            "resolution": "1080x1920",
            "manufacturer": "OnePlus",
            "device": "devitron",
            "model": "6T Dev",
            "cpu": "qcom",
            "version_code": "314665256",
        })
        self._login(username, password)

    def _login(self, username: str, password: str):
        session_path = Path(SESSION_FILE)
        if session_path.exists():
            try:
                self.client.load_settings(session_path)
                self.client.account_info()
                logger.info("Restored session from file — no login needed.")
                return
            except Exception as e:
                logger.warning(f"Session invalid ({e}), falling back to fresh login.")

        self.client.login(username, password)
        self.client.dump_settings(session_path)
        logger.info("Logged in fresh and saved session.")

    def get_new_posts(self) -> list:
        """Return list of (shortcode, url, playable_url, force) tuples from DMs.
        force=True means the shortcode appeared more than once — user sent it intentionally twice.
        Covers reels (XMA types) and normal posts/carousels (media_share type).
        """
        # found entries: [shortcode, url, playable_url, starred]
        found = []
        seen = {}  # shortcode -> index in found

        try:
            raw = self.client.private_request(
                "direct_v2/inbox/",
                params={"limit": 20, "persistentBadging": True},
            )
            thread_ids = [t["thread_id"] for t in raw.get("inbox", {}).get("threads", [])]
        except Exception as e:
            logger.error(f"Failed to fetch inbox: {e}")
            return found

        logger.info(f"Found {len(thread_ids)} DM thread(s).")

        XMA_REEL_TYPES = {"xma_clip", "xma_media_share", "xma_reel_share"}

        for thread_id in thread_ids:
            try:
                raw_thread = self.client.private_request(f"direct_v2/threads/{thread_id}/")
                messages = raw_thread.get("thread", {}).get("items", [])
            except Exception as e:
                logger.warning(f"Skipping thread {thread_id}: {e}")
                continue

            for msg in messages:
                item_type = msg.get("item_type")

                # --- XMA reels (newer DM format) ---
                if item_type in XMA_REEL_TYPES:
                    xma_list = msg.get(item_type, [])
                    if isinstance(xma_list, dict):
                        xma_list = [xma_list]

                    for xma_item in xma_list:
                        if not isinstance(xma_item, dict):
                            continue

                        target_url = xma_item.get("target_url", "")
                        if not target_url:
                            continue
                        if "/reel/" not in target_url and "/p/" not in target_url:
                            continue

                        shortcode = urlparse(target_url).path.rstrip("/").split("/")[-1]
                        if not shortcode:
                            continue

                        if shortcode in seen:
                            # Seen again — mark as starred
                            found[seen[shortcode]][3] = True
                            logger.info(f"  ★ {shortcode} sent more than once — marking as starred")
                            continue

                        playable_url = xma_item.get("playable_url") or (xma_item.get("playable_url_info") or {}).get("url")
                        logger.info(f"  Found reel shortcode={shortcode} has_playable={bool(playable_url)}")
                        seen[shortcode] = len(found)
                        found.append([shortcode, target_url, playable_url, False])

                # --- Standard media_share posts (photos, carousels, older reel shares) ---
                elif item_type == "media_share":
                    ms = msg.get("media_share", {})
                    shortcode = ms.get("code")
                    if not shortcode:
                        continue

                    if shortcode in seen:
                        found[seen[shortcode]][3] = True
                        logger.info(f"  ★ {shortcode} sent more than once — marking as starred")
                        continue

                    media_type = ms.get("media_type")  # 1=photo, 2=video, 8=carousel
                    playable_url = None
                    if media_type == 2:
                        video_versions = ms.get("video_versions", [])
                        if video_versions:
                            playable_url = video_versions[0].get("url")

                    source_url = f"https://www.instagram.com/p/{shortcode}/"
                    logger.info(f"  Found post shortcode={shortcode} media_type={media_type} has_playable={bool(playable_url)}")
                    seen[shortcode] = len(found)
                    found.append([shortcode, source_url, playable_url, False])

        return [tuple(e) for e in found]

    def download_media(self, shortcode: str, playable_url: str = None, download_dir: str = "downloads") -> tuple:
        """Download media. Returns ('video', path) or ('images', [path, ...])."""
        os.makedirs(download_dir, exist_ok=True)

        # If we have a direct video URL, download it immediately
        if playable_url:
            logger.info("Downloading via direct URL...")
            dest = Path(download_dir) / f"{shortcode}.mp4"
            resp = requests.get(playable_url, stream=True, timeout=60)
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=1024 * 64):
                    f.write(chunk)
            return ("video", str(dest))

        # Otherwise fetch media info from API to determine type
        logger.info("Fetching media info from API...")
        media_pk = self.client.media_pk_from_code(shortcode)
        media = self.client.media_info(media_pk)

        if media.media_type == 2:  # video / reel
            path = self.client.video_download(media_pk, Path(download_dir))
            return ("video", str(path))

        elif media.media_type == 1:  # single photo
            path = self.client.photo_download(media_pk, Path(download_dir))
            return ("images", [str(path)])

        elif media.media_type == 8:  # carousel / album
            paths = self.client.album_download(media_pk, Path(download_dir))
            return ("images", [str(p) for p in paths])

        else:
            raise ValueError(f"Unsupported media_type={media.media_type}, skipping.")
