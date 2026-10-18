
import os
import requests

from dotenv import load_dotenv

load_dotenv()

DISCORD_API_URL = "https://discord.com/api/v10"


def send_dm(message: str) -> None:
    """個人Discord Botから自分宛てにDMを送信する"""

    bot_token = os.environ["DISCORD_BOT_TOKEN"]
    user_id = os.environ["DISCORD_USER_ID"]

    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json",
    }

    # 1. DMチャンネルを取得・作成
    response = requests.post(
        f"{DISCORD_API_URL}/users/@me/channels",
        headers=headers,
        json={
            "recipient_id": user_id,
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"DMチャンネル取得失敗: HTTP {response.status_code}"
        )

    channel_id = response.json()["id"]

    # 2. DMを送信
    response = requests.post(
        f"{DISCORD_API_URL}/channels/{channel_id}/messages",
        headers=headers,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=15,
    )

    if not response.ok:
        raise RuntimeError(
            f"DM送信失敗: HTTP {response.status_code}"
        )

    print("Discord DM送信成功！")


if __name__ == "__main__":
    send_dm(
        "✅ Translation Automation Botの起動テスト成功！\n"
        "翻訳案件の自動通知を準備しています。"
    )
