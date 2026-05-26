#!/usr/bin/env python3
"""
GA4 Data API로 인기 포스트를 가져와 _data/popular.yml에 저장한다.

기존 방식(update_popular_frontmatter.py)은 매일 상위 포스트들의 frontmatter에
popular/popular_rank/popular_views/popular_updated 필드를 다시 써넣었다.
그 결과 매일 약 10개 포스트 파일이 수정되어, 검색엔진에 "이 포스트가
갱신되었다"는 신호가 반복 발생했다 (본문은 그대로인데도).

이 스크립트는 포스트 파일을 전혀 건드리지 않고 _data/popular.yml 한 곳에만
쓴다. 또한 인기 순위(상위 포스트 URL의 순서)에 변동이 없으면 파일 자체를
다시 쓰지 않는다. 따라서 순위가 그대로인 날은 커밋도 배포도 일어나지 않는다.
"""

import os
import glob
from datetime import datetime

import yaml

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy,
)

GA4_PROPERTY_ID = os.environ.get("GA4_PROPERTY_ID", "482435885")
DAYS_AGO = int(os.environ.get("DAYS_AGO", "7"))
TOP_N = int(os.environ.get("TOP_N", "10"))

POSTS_DIRS = ["_posts", "_zh_posts", "_en_posts"]
OUTPUT_FILE = "_data/popular.yml"

EXCLUDE_PATHS = {
    "/", "/zya.han/posts",
    "/about", "/about/",
    "/contact", "/contact/",
    "/archive", "/archive/",
}


def normalize_url(path):
    """앞뒤 슬래시를 정규화한다. Jekyll의 post.url과 매칭하기 위함이다."""
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/"):
        path = path + "/"
    return path


def get_top_post_paths():
    """GA4에서 상위 조회수 포스트 경로를 가져온다. (기존 선정 로직 유지)"""
    client = BetaAnalyticsDataClient()
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[Dimension(name="pagePath")],
        metrics=[Metric(name="screenPageViews")],
        date_ranges=[DateRange(start_date=f"{DAYS_AGO}daysAgo", end_date="today")],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                desc=True,
            )
        ],
        limit=100,
    )

    try:
        response = client.run_report(request)
    except Exception as e:
        print(f"❌ GA4 API 호출 실패: {e}")
        return []

    top_paths = []
    for row in response.rows:
        path = row.dimension_values[0].value
        views = int(row.metric_values[0].value)

        if path in EXCLUDE_PATHS:
            continue
        if (
            path.startswith("/tag")
            or path.startswith("/category")
            or path.startswith("/search")
            or path.startswith("/page")
            or path == "(not set)"
            or "/404" in path
            or path.endswith(".xml")
            or path.endswith(".json")
        ):
            continue

        # 포스트 판별: 경로 깊이가 1 (기존 로직 유지)
        segments = [s for s in path.strip("/").split("/") if s]
        if len(segments) == 1:
            top_paths.append({"path": path, "views": views})

        if len(top_paths) >= TOP_N:
            break

    return top_paths


def get_post_title(url_path):
    """URL에 해당하는 포스트 파일을 찾아 title을 읽는다."""
    slug = url_path.strip("/")

    for posts_dir in POSTS_DIRS:
        if not os.path.exists(posts_dir):
            continue

        # 1순위: 파일명(YYYY-MM-DD-slug.md) 매칭
        matches = glob.glob(
            os.path.join(posts_dir, "**", f"*-{slug}.md"), recursive=True
        )
        # 2순위: frontmatter의 slug/permalink 매칭
        candidates = matches or glob.glob(
            os.path.join(posts_dir, "**", "*.md"), recursive=True
        )

        for post_file in candidates:
            try:
                with open(post_file, "r", encoding="utf-8") as f:
                    content = f.read()
            except OSError:
                continue
            if not content.startswith("---\n"):
                continue
            end = content.find("\n---\n", 4)
            if end == -1:
                continue
            try:
                fm = yaml.safe_load(content[4:end])
            except yaml.YAMLError:
                continue
            if not fm:
                continue

            if matches or fm.get("slug") == slug or fm.get("permalink") == url_path:
                return fm.get("title")

    return None


def load_existing_urls(path):
    """기존 데이터 파일에서 인기 포스트 URL의 순서 목록을 읽는다."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return None
    if not data or "posts" not in data:
        return None
    return [p.get("url") for p in data["posts"]]


def main():
    print(f"🔍 GA4에서 최근 {DAYS_AGO}일간 상위 {TOP_N}개 포스트 조회 중...")
    print(f"📊 Property ID: {GA4_PROPERTY_ID}\n")

    top_paths = get_top_post_paths()
    if not top_paths:
        print("⚠️  조회된 포스트가 없습니다. 기존 데이터 파일을 유지합니다.")
        return

    posts = []
    for i, item in enumerate(top_paths, 1):
        path = normalize_url(item["path"])
        views = item["views"]
        title = get_post_title(item["path"])

        entry = {"url": path, "rank": i, "views": views}
        if title:
            entry["title"] = title

        posts.append(entry)
        mark = "✅" if title else "⚠️  (title 못 찾음)"
        print(f"{mark} #{i:2d} | {views:>6} views | {path}")

    # 순위(URL 순서)에 변동이 없으면 파일을 다시 쓰지 않는다.
    # 조회수만 미세하게 달라진 경우의 불필요한 커밋/배포를 막기 위함이다.
    new_urls = [p["url"] for p in posts]
    if load_existing_urls(OUTPUT_FILE) == new_urls:
        print("\n📊 인기 포스트 순위에 변동이 없습니다. 파일을 유지합니다.")
        return

    data = {
        "updated": datetime.now().strftime("%Y-%m-%d"),
        "posts": posts,
    }

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        yaml.dump(
            data, f, allow_unicode=True, default_flow_style=False, sort_keys=False
        )

    print(f"\n💾 {OUTPUT_FILE}에 인기 포스트 {len(posts)}개 저장 완료.")


if __name__ == "__main__":
    main()
