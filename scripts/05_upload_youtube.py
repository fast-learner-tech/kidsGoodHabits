#!/usr/bin/env python3
"""Optional: upload a finished video to YouTube through the Data API v3, marked Made for Kids.

IMPORTANT: videos uploaded through an API project that has not passed Google's audit are locked
to PRIVATE. Doing the upload manually in YouTube Studio is just as good for a small channel.
Use this script only if you have completed the audit, or for private test uploads.

Setup (one time):
  1. console.cloud.google.com -> new project -> enable "YouTube Data API v3"
  2. Credentials -> OAuth client ID -> Desktop app -> download as client_secret.json (project root)
  3. pip install google-api-python-client google-auth-oauthlib

Usage:
  python scripts/05_upload_youtube.py out/ep01_brush_teeth.mp4 "Brush Your Teeth With Pip!" description.txt
"""
import sys
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
ROOT = Path(__file__).resolve().parent.parent


def main(video: str, title: str, desc_file: str) -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(ROOT / "client_secret.json"), SCOPES)
    creds = flow.run_local_server(port=0)
    yt = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title[:100],
            "description": Path(desc_file).read_text(),
            "categoryId": "27",  # Education
            "tags": ["kids", "good habits", "daily routine", "animation for kids", "learning"],
            "defaultLanguage": "en",
        },
        "status": {
            "privacyStatus": "private",         # review in Studio, then publish
            "selfDeclaredMadeForKids": True,    # required for child-directed content (COPPA)
            "embeddable": True,
        },
    }
    media = MediaFileUpload(video, chunksize=8 * 1024 * 1024, resumable=True)
    req = yt.videos().insert(part="snippet,status", body=body, media_body=media)
    resp = None
    while resp is None:
        status, resp = req.next_chunk()
        if status:
            print(f"uploaded {int(status.progress() * 100)}%")
    print("Done. Video id:", resp["id"], "-> check it in YouTube Studio")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    main(*sys.argv[1:])
