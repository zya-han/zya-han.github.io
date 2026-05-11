#!/usr/bin/env python3
"""
Remark42 API에서 댓글이 달린 포스트 목록과 댓글 수를 가져와
_data/comment_counts.yml에 저장한다.

API: GET /api/v1/list?site=SITE_ID&limit=0
  - 댓글이 하나라도 달린 포스트만 반환 (count > 0)
  - PostInfo {url, count, first_time, last_time, read_only} 배열
  - 인증 불필요

YAML 키는 사이트 상대 경로(예: /jiuyunchunjiu/)로 저장한다.
Jekyll 템플릿에서 site.data.comment_counts[post.url]로 조회하기 위함이다.
"""

import json
import os
import sys
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import yaml

SITE_BASE = os.environ.get("SITE_BASE", "https://zyahan.blog")
REMARK42_HOST = os.environ.get("REMARK42_HOST", "https://comments.zyahan.blog")
REMARK42_SITE_ID = os.environ.get("REMARK42_SITE_ID", "zyahan")
OUTPUT_FILE = "_data/comment_counts.yml"


def fetch_commented_posts():
    """Remark42의 list 엔드포인트에서 댓글 있는 포스트 전체 목록을 가져온다."""
    url = f"{REMARK42_HOST}/api/v1/list?site={REMARK42_SITE_ID}&limit=0"
    req = Request(url, headers={"Accept": "application/json"})
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def to_relative_url(full_url):
    """절대 URL을 사이트 상대 경로로 변환한다."""
    if full_url.startswith(SITE_BASE):
        rel = full_url[len(SITE_BASE):]
    else:
        # SITE_BASE와 다른 도메인이 섞여 있다면 경로만 추출
        rel = urlparse(full_url).path
    if not rel.startswith("/"):
        rel = "/" + rel
    return rel


def main():
    print(f"📡 Fetching commented posts from {REMARK42_HOST}...")

    try:
        posts = fetch_commented_posts()
    except Exception as e:
        # 네트워크/API 오류 시 기존 데이터 파일을 덮어쓰지 않고 종료한다.
        # 이전 빌드의 댓글 수가 0으로 초기화되는 것을 막기 위함이다.
        print(f"❌ Remark42 API 호출 실패: {e}")
        sys.exit(1)

    counts = {}
    for post in posts:
        rel_url = to_relative_url(post["url"])
        counts[rel_url] = post["count"]

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(
            counts,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=True,
        )

    total_posts = len(counts)
    total_comments = sum(counts.values())
    print(
        f"💾 Wrote {OUTPUT_FILE}: "
        f"{total_posts} posts with comments, {total_comments} comments total."
    )


if __name__ == "__main__":
    main()
