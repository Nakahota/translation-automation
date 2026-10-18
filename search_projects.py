
import json
import re
from pathlib import Path
from token_manager import get_access_token

from freelancersdk.session import Session
from freelancersdk.resources.projects.projects import search_projects
from freelancersdk.resources.projects.helpers import (
    create_get_projects_project_details_object,
)

TOKEN_FILE = Path(".freelancer_tokens.json")

SEARCH_QUERIES = [
    "Japanese",
    "translation",
]

LANGUAGE_PATTERN = re.compile(r"japanese|日本語", re.IGNORECASE)

TRANSLATION_PATTERN = re.compile(
    r"translat|localiz|localis|翻訳|ローカライズ",
    re.IGNORECASE,
)

# 英語から日本語への翻訳だと明示されている案件を優先
DIRECTION_PATTERN = re.compile(
    r"(english\s*(?:to|[-→>])\s*japanese)"
    r"|(?:english[\s/\-]+japanese\s+translat)"
    r"|(?:英語\s*(?:から|→|⇒)\s*日本語)",
    re.IGNORECASE,
)



def get_session():
    access_token = get_access_token()

    return Session(oauth_token=access_token)



def search_translation_projects(session):
    unique_projects = {}

    project_details = create_get_projects_project_details_object(
        full_description=True,
        jobs=True,
    )

    for query in SEARCH_QUERIES:
        print(f"検索中: {query}")

        result = search_projects(
            session,
            query=query,
            active_only=True,
            limit=100,
            project_details=project_details,
        )

        projects = result.get("projects", [])

        print(f"  取得件数: {len(projects)}")

        for project in projects:
            project_id = project.get("id")

            if project_id is not None:
                unique_projects[project_id] = project

    return list(unique_projects.values())



def classify_project(project):
    title = project.get("title") or ""
    description = (
        project.get("description")
        or project.get("preview_description")
        or ""
    )

    text = f"{title} {description}"

    # 1. 日本語に関係する案件か
    if not LANGUAGE_PATTERN.search(text):
        return None

    # 2. タイトルに翻訳・ローカライズ関連の単語があるか
    translation_title = re.search(
        r"translat\w*|locali[sz]\w*|subtitl\w*",
        title,
        re.IGNORECASE,
    )

    if not translation_title:
        return None

    # 3. 明らかに日本語→英語の案件を除外
    reverse_direction = re.search(
        r"japanese\s*(?:to|into|[-→>])\s*english",
        text,
        re.IGNORECASE,
    )

    if reverse_direction:
        return None

    # 4. 英語→日本語が明示されている
    if DIRECTION_PATTERN.search(text):
        return "英語→日本語の可能性が高い"

    # 5. 日本語への翻訳が明示されている
    target_japanese = re.search(
        r"(?:to|into)\s+japanese\b",
        text,
        re.IGNORECASE,
    )

    if target_japanese:
        return "日本語への翻訳・原文言語は要確認"

    # 6. その他の日本語翻訳候補
    return "日本語翻訳関連・翻訳方向は要確認"



def display_project(project, category):
    title = project.get("title", "タイトルなし")
    description = (
        project.get("description")
        or project.get("preview_description")
        or ""
    )

    budget = project.get("budget") or {}
    currency = project.get("currency") or {}

    minimum = budget.get("minimum", "?")
    maximum = budget.get("maximum", "?")
    currency_code = currency.get("code", "通貨不明")

    print("\n" + "=" * 60)
    print("判定:", category)
    print("タイトル:", title)
    print(f"予算: {minimum} - {maximum} {currency_code}")
    print("概要:", description[:500])
    print(
        "URL:",
        f"https://www.freelancer.com/projects/{project['id']}",
    )


def main():
    session = get_session()

    projects = search_translation_projects(session)

    print(f"\n重複除去後: {len(projects)}件")

    candidates = []

    for project in projects:
        category = classify_project(project)

        if category:
            candidates.append((project, category))

    # 翻訳方向が明示されている案件を先に表示
    candidates.sort(
        key=lambda item: (
            item[1] != "英語→日本語の可能性が高い"
        )
    )

    print(f"翻訳候補: {len(candidates)}件")

    for project, category in candidates:
        display_project(project, category)

    if not candidates:
        print(
            "今回取得した案件に一致する候補はありませんでした。"
        )


if __name__ == "__main__":
    main()
