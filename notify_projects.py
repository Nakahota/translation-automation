
import argparse
import json
import os
import tempfile
from pathlib import Path

from discord_notifier import send_dm

BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
STATE_FILE = RESULTS_DIR / "notified_project_ids.json"

MAX_SEND_PER_RUN = 5


def load_projects() -> dict:
    """保存済みの案件分析結果を読み込む"""
    projects = {}

    for file_path in sorted(RESULTS_DIR.glob("analysis_*.json")):
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        for project in data.get("projects", []):
            project_id = project.get("project_id")

            if project_id is not None:
                projects[str(project_id)] = project

    return projects


def load_notified_ids() -> set[str]:
    """通知済み案件IDを取得する"""
    if not STATE_FILE.exists():
        raise RuntimeError(
            "通知履歴がありません。先に --init-existing を実行してください。"
        )

    with STATE_FILE.open("r", encoding="utf-8") as file:
        data = json.load(file)

    return set(data["notified_project_ids"])


def save_notified_ids(project_ids: set[str]) -> None:
    """通知履歴を安全に保存する"""
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    fd, temporary_path = tempfile.mkstemp(
        prefix=".notified_",
        dir=RESULTS_DIR,
    )

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(
                {
                    "notified_project_ids": sorted(project_ids)
                },
                file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(temporary_path, STATE_FILE)
        STATE_FILE.chmod(0o600)

    finally:
        if os.path.exists(temporary_path):
            os.unlink(temporary_path)


def initialize_history() -> None:
    """既存の分析案件を通知済みとして初期登録"""
    if STATE_FILE.exists():
        print("通知履歴はすでに初期化されています。")
        return

    projects = load_projects()
    save_notified_ids(set(projects.keys()))

    print(f"通知履歴の初期化完了: {len(projects)}件")


def format_message(project: dict) -> str:
    """Discord DM用のメッセージを生成"""
    analysis = project.get("analysis") or {}
    budget = project.get("budget") or {}
    currency = project.get("currency") or {}

    minimum = budget.get("minimum")
    maximum = budget.get("maximum")

    if minimum is None and maximum is None:
        budget_text = "不明"
    else:
        budget_text = (
            f"{minimum if minimum is not None else '?'}"
            f"〜{maximum if maximum is not None else '?'}"
            f" {currency.get('code', '')}"
        )

    title = str(project.get("title") or "タイトルなし")[:180]
    summary = str(analysis.get("summary_ja") or "記載なし")[:400]
    judgment = str(project.get("judgment") or "不明")

    message = (
        "📢 **新しい翻訳案件が見つかりました！**\n\n"
        f"**案件:** {title}\n"
        f"**予算:** {budget_text}\n"
        f"**判定:** {judgment}\n"
        f"**翻訳元:** {analysis.get('source_language', '不明')}\n"
        f"**翻訳先:** {analysis.get('target_language', '不明')}\n"
        f"**AI利用:** {analysis.get('ai_permission', '不明')}\n\n"
        f"**AIによる概要:**\n{summary}\n\n"
        f"**案件URL:** {project.get('url', '')}"
    )

    # Discordのメッセージ文字数制限を考慮
    return message[:1800]


def notify_projects() -> None:
    projects = load_projects()
    notified_ids = load_notified_ids()

    pending = [
        (project_id, project)
        for project_id, project in projects.items()
        if project_id not in notified_ids
        and "対象外" not in str(project.get("judgment", ""))
    ]

    print(f"未通知案件: {len(pending)}件")

    for project_id, project in pending[:MAX_SEND_PER_RUN]:
        # 送信失敗時は例外で停止し、次回再試行する
        send_dm(format_message(project))

        # 送信成功後だけ通知履歴に保存
        notified_ids.add(project_id)
        save_notified_ids(notified_ids)

        print(f"通知完了: 案件ID {project_id}")

    print("Discord通知処理終了")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--init-existing",
        action="store_true",
        help="過去の分析案件を通知済みとして初期登録",
    )
    args = parser.parse_args()

    if args.init_existing:
        initialize_history()
    else:
        notify_projects()


if __name__ == "__main__":
    main()
