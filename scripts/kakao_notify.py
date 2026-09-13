import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


load_dotenv()

KAKAO_ACCESS_TOKEN = os.getenv("KAKAO_ACCESS_TOKEN", "").strip()
KAKAO_ENABLED = os.getenv("KAKAO_NOTIFY_ENABLED", "false").strip().lower() == "true"
LOG_DIR = Path(os.getenv("BOT_LOG_DIR", "./logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "kakao_notify.log"


def log(message):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")


def send_kakao_text(title, text):
    if not KAKAO_ENABLED:
        log(f"SKIP disabled title={title}")
        return False
    if not KAKAO_ACCESS_TOKEN:
        log(f"SKIP missing KAKAO_ACCESS_TOKEN title={title}")
        return False

    body = {
        "object_type": "text",
        "text": f"{title}\n\n{text}",
        "link": {
            "web_url": "https://github.com/shwlsdn2555/bitcoin-trading-bot",
            "mobile_web_url": "https://github.com/shwlsdn2555/bitcoin-trading-bot",
        },
        "button_title": "GitHub 보기",
    }
    response = requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={
            "Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        data={"template_object": json.dumps(body, ensure_ascii=False)},
        timeout=15,
    )
    if response.status_code >= 300:
        log(f"FAIL {response.status_code} {response.text[:500]}")
        return False
    log(f"OK title={title}")
    return True


def parse_args():
    parser = argparse.ArgumentParser(description="Send a KakaoTalk 'message to me' notification.")
    parser.add_argument("--title", required=True)
    parser.add_argument("--text", required=True)
    return parser.parse_args()


def main():
    args = parse_args()
    ok = send_kakao_text(args.title, args.text)
    print("sent" if ok else "skipped")


if __name__ == "__main__":
    main()
