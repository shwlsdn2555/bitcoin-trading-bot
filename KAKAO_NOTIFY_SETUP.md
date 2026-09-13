# Kakao Notification Setup

This project can send KakaoTalk notifications through Kakao Developers.

The first target is KakaoTalk "Send to me", which sends a message to the logged-in user's My Chatroom. This is simpler than sending to friends or channels.

## What It Can Send

Before a scheduled update:

- Today's planned update.
- Current Codex 5-hour usage and weekly usage, when available from Codex automation.
- Whether work will proceed or be skipped.

After a scheduled update:

- Changed files.
- Backtests or checks that ran.
- Important metrics.
- Risks or failures.
- Next task.

## Required Kakao Setup

Create or use a Kakao Developers app.

Required app settings:

- Kakao Login enabled.
- Redirect URI registered.
- Consent item: `talk_message`.
- A valid user access token for the Kakao account that should receive the message.

The script uses KakaoTalk Message API:

```text
POST https://kapi.kakao.com/v2/api/talk/memo/default/send
```

## Environment Variables

Add these only to `.env`, never to `.env.example` with real secrets:

```text
KAKAO_NOTIFY_ENABLED=true
KAKAO_ACCESS_TOKEN=your_kakao_access_token
```

Optional later:

```text
KAKAO_REST_API_KEY=your_rest_api_key
KAKAO_REFRESH_TOKEN=your_refresh_token
```

## Test

On the server:

```bash
cd /opt/alert-bot
./venv/bin/python scripts/kakao_notify.py --title "Quant update test" --text "Kakao notification is connected."
```

If not configured, the script prints:

```text
skipped
```

and writes the reason to:

```text
logs/kakao_notify.log
```

## Important Notes

- Do not paste Kakao tokens into screenshots or chat.
- Do not commit `.env`.
- Access tokens expire. A refresh-token flow should be added before relying on Kakao notifications long term.
- If Kakao setup becomes too heavy, Discord can be used for the same start/end notifications immediately.
