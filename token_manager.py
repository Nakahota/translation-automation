
import json
import os
import tempfile
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
TOKEN_FILE = BASE_DIR / ".freelancer_tokens.json"

load_dotenv(BASE_DIR / ".env")

TOKEN_URL = "https://accounts.freelancer.com/oauth/token"

# 有効期限の5分前に更新する
REFRESH_MARGIN = 300


def save_tokens(tokens: dict) -> None:
    """トークンを安全に保存する"""
    fd, temporary_path = tempfile.mkstemp(
        prefix=".tokens_",
        dir=BASE_DIR,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(tokens, f, indent=2)

        os.replace(temporary_path, TOKEN_FILE)
        TOKEN_FILE.chmod(0o600)

    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def refresh_access_token(tokens: dict) -> dict:
    """Freelancer OAuthトークンを更新する"""
    refresh_token = tokens.get("refresh_token")

    if not refresh_token:
        raise RuntimeError(
            "リフレッシュトークンがありません。再認証が必要です。"
        )

    print("Freelancer OAuthトークンを更新中...")

    try:
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": os.environ["FREELANCER_CLIENT_ID"],
                "client_secret": os.environ["FREELANCER_CLIENT_SECRET"],
            },
            timeout=30,
        )
        response.raise_for_status()
        new_tokens = response.json()

    except requests.HTTPError as error:
        status = error.response.status_code if error.response else "不明"
        raise RuntimeError(
            f"トークン更新に失敗しました。HTTPステータス: {status}"
        ) from None

    except requests.RequestException:
        raise RuntimeError(
            "トークン更新中に通信エラーが発生しました。"
        ) from None

    if not isinstance(new_tokens, dict):
        raise RuntimeError("トークン応答の形式が不正です。")

    if not new_tokens.get("access_token"):
        raise RuntimeError(
            "新しいアクセストークンを取得できませんでした。"
        )

    try:
        expires_in = int(new_tokens["expires_in"])
        if expires_in <= 0:
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise RuntimeError(
            "有効期限情報が不正です。トークンは更新せず保持します。"
        ) from None

    updated_tokens = {
        **tokens,
        **new_tokens,
        "expires_at": int(time.time()) + expires_in,
    }

    # 新しいrefresh_tokenが返らない場合は既存の値を維持
    if not new_tokens.get("refresh_token"):
        updated_tokens["refresh_token"] = refresh_token

    save_tokens(updated_tokens)

    print("Freelancer OAuthトークン更新成功")

    return updated_tokens


def get_access_token() -> str:
    """有効なアクセストークンを返す"""
    with TOKEN_FILE.open("r", encoding="utf-8") as f:
        tokens = json.load(f)

    expires_at = tokens.get("expires_at")

    # 有効期限まで5分以上ある場合はそのまま利用
    if expires_at is not None:
        remaining = int(expires_at) - time.time()

        if remaining > REFRESH_MARGIN:
            return tokens["access_token"]

    # 期限切れが近い、または期限情報がない場合は更新
    updated_tokens = refresh_access_token(tokens)

    return updated_tokens["access_token"]
