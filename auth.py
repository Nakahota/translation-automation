import json
import os
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import urlencode, urlparse, parse_qs

import requests
from dotenv import load_dotenv

load_dotenv()

CLIENT_ID = os.environ["FREELANCER_CLIENT_ID"]
CLIENT_SECRET = os.environ["FREELANCER_CLIENT_SECRET"]
REDIRECT_URI = os.environ["FREELANCER_REDIRECT_URI"]

AUTHORIZE_URL = "https://accounts.freelancer.com/oauth/authorise"
TOKEN_URL = "https://accounts.freelancer.com/oauth/token"

STATE = secrets.token_urlsafe(32)
TOKEN_FILE = Path(".freelancer_tokens.json")

redirect = urlparse(REDIRECT_URI)

if redirect.hostname not in ("127.0.0.1", "localhost"):
    raise ValueError("Redirect URI must use localhost")

if redirect.scheme != "http" or not redirect.port:
    raise ValueError("Invalid local Redirect URI")


class CallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)

        if parsed.path != redirect.path:
            self.send_error(404)
            return

        params = parse_qs(parsed.query)

        if "error" in params:
            print("OAuth認証が拒否されました")
            self.respond("Authorization denied", 400)
            return

        received_state = params.get("state", [""])[0]
        code = params.get("code", [""])[0]

        if not secrets.compare_digest(received_state, STATE):
            print("stateが一致しません")
            self.respond("Invalid OAuth state", 400)
            return

        if not code:
            self.respond("Authorization code missing", 400)
            return

        try:
            response = requests.post(
                TOKEN_URL,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                },
                timeout=30,
            )
            response.raise_for_status()

            token_data = response.json()

            if not token_data.get("access_token"):
                raise ValueError("アクセストークンがありません")

            # トークンをGit管理対象外のファイルに保存
            TOKEN_FILE.touch(mode=0o600, exist_ok=True)
            TOKEN_FILE.chmod(0o600)
            TOKEN_FILE.write_text(
                json.dumps(token_data, indent=2),
                encoding="utf-8",
            )

            print("アクセストークン取得成功！")
            print("保存先:", TOKEN_FILE)
            self.respond("OAuth authentication successful!")

        except (requests.RequestException, ValueError) as error:
            # 認証コードやトークンを含むレスポンスは表示しない
            print("トークン取得に失敗しました")
            print("エラー種別:", type(error).__name__)
            self.respond("Token exchange failed", 500)

    def respond(self, message, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(message.encode("utf-8"))


params = {
    "response_type": "code",
    "client_id": CLIENT_ID,
    "redirect_uri": REDIRECT_URI,
    "scope": "basic",
    "state": STATE,
}

authorization_url = AUTHORIZE_URL + "?" + urlencode(params)

server = HTTPServer(
    (redirect.hostname, redirect.port),
    CallbackHandler,
)

print("OAuthサーバー起動")
print("認証URLをブラウザで開いてください")
print("※ URLや認可コードは共有しないでください")

# WSLからWindowsのブラウザを起動
import subprocess

subprocess.Popen([
    "/mnt/c/Windows/System32/rundll32.exe",
    "url.dll,FileProtocolHandler",
    authorization_url,
])

print("\n自動で開かない場合は以下のURLを開いてください:")
print(authorization_url)

try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\nOAuthサーバーを停止しました")
finally:
    server.server_close()