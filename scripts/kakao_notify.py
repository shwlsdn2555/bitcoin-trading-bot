import argparse
import json
import os
from pathlib import Path

import requests
from dotenv import load_dotenv


ENV_PATH = Path(".env")
load_dotenv(ENV_PATH)

KAKAO_ACCESS_TOKEN = os.getenv("KAKAO_ACCESS_TOKEN", "").strip()
KAKAO_REFRESH_TOKEN = os.getenv("KAKAO_REFRESH_TOKEN", "").strip()
KAKAO_REST_API_KEY = os.getenv("KAKAO_REST_API_KEY", "").strip()
KAKAO_CLIENT_SECRET = os.getenv("KAKAO_CLIENT_SECRET", "").strip()
KAKAO_ENABLED = os.getenv("KAKAO_NOTIFY_ENABLED", "false").strip().lower() == "true"
LOG_DIR = Path(os.getenv("BOT_LOG_DIR", "./logs"))
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "kakao_notify.log"


def log(message):
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(message.rstrip() + "\n")


def save_env_value(key, value):
    if not value:
        return

    lines = []
    if ENV_PATH.exists():
        lines = ENV_PATH.read_text(encoding="utf-8").splitlines()

    updated = False
    next_lines = []
    for line in lines:
        if line.startswith(f"{key}="):
            next_lines.append(f"{key}={value}")
            updated = True
        else:
            next_lines.append(line)

    if not updated:
        next_lines.append(f"{key}={value}")

    ENV_PATH.write_text("\n".join(next_lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def refresh_access_token():
    global KAKAO_ACCESS_TOKEN, KAKAO_REFRESH_TOKEN

    if not KAKAO_REST_API_KEY or not KAKAO_REFRESH_TOKEN:
        log("SKIP refresh missing KAKAO_REST_API_KEY or KAKAO_REFRESH_TOKEN")
        return False

    data = {
        "grant_type": "refresh_token",
        "client_id": KAKAO_REST_API_KEY,
        "refresh_token": KAKAO_REFRESH_TOKEN,
    }
    if KAKAO_CLIENT_SECRET:
        data["client_secret"] = KAKAO_CLIENT_SECRET

    response = requests.post(
        "https://kauth.kakao.com/oauth/token",
        headers={"Content-Type": "application/x-www-form-urlencoded;charset=utf-8"},
        data=data,
        timeout=15,
    )
    if response.status_code >= 300:
        log(f"REFRESH_FAIL {response.status_code} {response.text[:500]}")
        return False

    payload = response.json()
    new_access_token = payload.get("access_token", "").strip()
    new_refresh_token = payload.get("refresh_token", "").strip()

    if not new_access_token:
        log(f"REFRESH_FAIL missing access_token {response.text[:500]}")
        return False

    KAKAO_ACCESS_TOKEN = new_access_token
    save_env_value("KAKAO_ACCESS_TOKEN", new_access_token)

    if new_refresh_token:
        KAKAO_REFRESH_TOKEN = new_refresh_token
        save_env_value("KAKAO_REFRESH_TOKEN", new_refresh_token)

    log("REFRESH_OK")
    return True


def post_kakao_text(title, text):
    body = {
        "object_type": "text",
        "text": f"{title}\n\n{text}",
        "link": {
            "web_url": "https://github.com/shwlsdn2555/bitcoin-trading-bot",
            "mobile_web_url": "https://github.com/shwlsdn2555/bitcoin-trading-bot",
        },
        "button_title": "GitHub 보기",
    }
    return requests.post(
        "https://kapi.kakao.com/v2/api/talk/memo/default/send",
        headers={
            "Authorization": f"Bearer {KAKAO_ACCESS_TOKEN}",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
        },
        data={"template_object": json.dumps(body, ensure_ascii=False)},
        timeout=15,
    )


def send_kakao_text(title, text):
    if not KAKAO_ENABLED:
        log(f"SKIP disabled title={title}")
        return False
    if not KAKAO_ACCESS_TOKEN:
        log(f"SKIP missing KAKAO_ACCESS_TOKEN title={title}")
        return False

    response = post_kakao_text(title, text)
    if response.status_code == 401 and refresh_access_token():
        response = post_kakao_text(title, text)

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
