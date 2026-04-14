"""
Run this ONCE to authenticate with Instagram and save a session file.
After this succeeds, the main bot uses the saved session.

Usage: python login.py
"""

from instagrapi import Client
from instagrapi.exceptions import ChallengeRequired
import os
import base64
from dotenv import load_dotenv

load_dotenv()


def code_handler(username, choice):
    print(f"\nInstagram sent a verification code to your {choice}.")
    return input("Enter the code here: ").strip()


def main():
    username = os.getenv("INSTAGRAM_USERNAME") or input("Instagram username: ").strip()
    password = os.getenv("INSTAGRAM_PASSWORD") or input("Instagram password: ").strip()

    cl = Client()
    cl.challenge_code_handler = code_handler

    # Mimic a real device (same as main bot)
    cl.set_device({
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

    print(f"\nLogging in as @{username}...")
    try:
        cl.login(username, password)
    except ChallengeRequired:
        print("Challenge required — Instagram wants to verify you.")
        cl.challenge_resolve(cl.last_json)

    cl.dump_settings("session.json")
    print("\nSession saved to session.json")

    # Print the base64 value to add as a GitHub secret
    with open("session.json", "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    print("\n" + "="*60)
    print("Add this as a GitHub secret named INSTAGRAM_SESSION:")
    print("="*60)
    print(encoded)
    print("="*60)


if __name__ == "__main__":
    main()
