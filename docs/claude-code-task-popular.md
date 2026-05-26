# 태스크: 인기 포스트 시스템을 frontmatter에서 데이터 파일로 이전

## 배경과 목적

이 Jekyll 블로그(zyahan.blog, GitHub Pages 배포)는 현재 매일 GA4 조회수를 기준으로
인기 포스트를 골라, 상위 약 10개 포스트의 **frontmatter**에 다음 필드를 써넣는다.

- `popular: true`
- `popular_rank`
- `popular_views`
- `popular_updated`

조회수와 날짜가 매일 달라지므로 매일 약 10개의 포스트 `.md` 파일이 다시 쓰여진다.
본문 내용은 그대로인데 파일만 매일 수정되니, 검색엔진(특히 네이버 Yeti)에
"이 포스트가 계속 갱신된다"는 churn 신호가 누적된다. 이것이 색인 누락의
원인 중 하나로 의심된다.

**목적**: 인기 데이터를 포스트 frontmatter가 아니라 `_data/popular.yml` 한 파일에
모아 저장하도록 바꾼다. 그러면 포스트 파일은 자동화가 전혀 건드리지 않게 되어
수정 시각이 안정적으로 유지되고, churn 신호가 사라진다. 추가로, 인기 순위에
실제 변동이 없는 날에는 아무 변경/배포도 일어나지 않도록 한다.

## 작업 전 확인 (먼저 읽고 시작할 것)

실제 코드를 먼저 읽어서 아래 가정이 맞는지 확인하라. 다르면 그에 맞춰 조정하라.

1. `scripts/update_popular_frontmatter.py`의 현재 동작. 특히 GA4에서 포스트를
   선정하는 필터 로직을 확인하라. 핵심 규칙은 "경로 깊이가 1인 URL만 포스트로
   간주"한다는 것이다(즉 `/jiuyunchunjiu/`는 포함, `/zh/...`나 `/en/...`은 제외).
   이 선정 로직은 **그대로 보존**해야 한다. 인기 포스트 선정 결과가 이전과
   동일해야 한다.
2. `.github/workflows/update-popular-frontmatter.yml`의 빌드/배포 단계 구조.
3. 인기 포스트를 렌더링하는 템플릿의 위치와 내용. `grep -rn "popular" _includes/ _layouts/`로
   찾아라. 보통 `site.posts | where: 'popular', true` 형태로 사용 중일 것이다.
   이 위젯이 무엇을 표시하는지(제목+링크만인지, 썸네일/발췌문까지인지) 확인하라.
   템플릿 수정 방식이 거기에 따라 달라진다.
4. GA4 Property ID는 `482435885`다. 워크플로의 GitHub Secret 이름은
   `GA4_SERVICE_ACCOUNT_JSON`, `ACTIONS_DEPLOY_KEY`다(기존 워크플로와 동일).

## 작업 순서

### 1단계: 기존 자동화 제거 (가장 먼저)

다음 두 파일을 삭제하라.

- `.github/workflows/update-popular-frontmatter.yml`
- `scripts/update_popular_frontmatter.py`

이 워크플로를 지우는 순간부터 매일의 frontmatter churn이 멈춘다. 이 단계를
건너뛰고 새 시스템만 추가하면 두 시스템이 함께 돌면서 기존 것이 계속 frontmatter를
갱신하므로 작업이 무의미해진다. 반드시 먼저 제거하라.

### 2단계: 새 스크립트 생성

`scripts/update_popular.py`를 아래 내용으로 생성하라.

```python
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
```

### 3단계: 새 워크플로 생성

`.github/workflows/update-popular.yml`을 아래 내용으로 생성하라.

**주의**: 빌드/배포 단계를 워크플로 안에 그대로 유지하라. 기본 `GITHUB_TOKEN`으로
푸시한 커밋은 다른 워크플로(`deploy.yml`)를 트리거하지 못한다(GitHub의 루프 방지
정책). 그래서 이 워크플로는 스스로 빌드하고 배포해야 한다. "deploy.yml이
처리하니 빌드 단계를 빼서 단순화하자"는 식으로 바꾸지 말 것. 배포가 누락된다.

```yaml
name: Update Popular Posts and Deploy

on:
  # 매일 UTC 23:00 (KST 8:00) - 혼잡 시간 피함
  schedule:
    - cron: '0 23 * * *'

  # 수동 실행 가능
  workflow_dispatch:

jobs:
  update-and-deploy:
    runs-on: ubuntu-latest

    permissions:
      contents: write  # 파일 커밋을 위해 필요

    steps:
      - name: 📥 Checkout repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: 🐍 Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'
          cache-dependency-path: requirements.txt

      - name: 📊 Install Python dependencies
        run: pip install google-analytics-data PyYAML --break-system-packages

      - name: 🔥 Update popular posts data
        env:
          GOOGLE_APPLICATION_CREDENTIALS_JSON: ${{ secrets.GA4_SERVICE_ACCOUNT_JSON }}
          GA4_PROPERTY_ID: '482435885'
          DAYS_AGO: '7'
          TOP_N: '10'
        run: |
          echo "$GOOGLE_APPLICATION_CREDENTIALS_JSON" > ga4_credentials.json
          export GOOGLE_APPLICATION_CREDENTIALS="ga4_credentials.json"
          python scripts/update_popular.py
          rm ga4_credentials.json

      - name: 🔍 Check for changes
        id: check_changes
        run: |
          if git diff --quiet _data/popular.yml 2>/dev/null; then
            echo "changed=false" >> $GITHUB_OUTPUT
          else
            echo "changed=true" >> $GITHUB_OUTPUT
          fi

      - name: 💾 Commit and push if changed
        if: steps.check_changes.outputs.changed == 'true'
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add _data/popular.yml
          git commit -m "🔥 Update popular posts ($(date +'%Y-%m-%d'))" || exit 0
          git push

      - name: 🧱 Setup Ruby
        if: steps.check_changes.outputs.changed == 'true'
        uses: ruby/setup-ruby@v1
        with:
          ruby-version: '3.2.7'
          bundler-cache: true

      - name: 💎 Install Ruby dependencies
        if: steps.check_changes.outputs.changed == 'true'
        run: bundle install

      - name: 🏗️ Build site with Jekyll
        if: steps.check_changes.outputs.changed == 'true'
        env:
          JEKYLL_ENV: production
        run: bundle exec jekyll build -d ./_site

      - name: 📅 Set current date
        if: steps.check_changes.outputs.changed == 'true'
        run: echo "DEPLOY_DATE=$(date +'%Y-%m-%d')" >> $GITHUB_ENV

      - name: 🚀 Deploy to gh-pages branch
        if: steps.check_changes.outputs.changed == 'true'
        uses: peaceiris/actions-gh-pages@v4
        with:
          deploy_key: ${{ secrets.ACTIONS_DEPLOY_KEY }}
          publish_dir: ./_site
          external_repository: zya-han/zya-han.github.io
          publish_branch: gh-pages
          user_name: 'github-actions[bot]'
          user_email: 'github-actions[bot]@users.noreply.github.com'
          commit_message: '🚀 Deploy: Update popular posts (${{ env.DEPLOY_DATE }})'
          enable_jekyll: false
          cname: zyahan.blog

      - name: 📊 No changes
        if: steps.check_changes.outputs.changed == 'false'
        run: echo "📊 인기 포스트 순위에 변동이 없습니다. 배포를 건너뜁니다."
```

### 4단계: 데이터 파일 형식

`_data/popular.yml`은 스크립트가 생성/갱신한다. 형식은 다음과 같다.

```yaml
updated: '2026-05-16'
posts:
  - url: /jiuyunchunjiu/
    rank: 1
    views: 1234
    title: "조조가 헌제에게 바쳤다는 그 술"
  - url: /castration/
    rank: 2
    views: 987
    title: "궁형은 정말로 사형보다 치욕스러운 형벌이었을까?"
```

스크립트가 처음 실행되기 전 빌드가 깨지지 않도록, 위 형식의 최소 예시 파일을
한 번 커밋해 두어라(워크플로 첫 실행 시 실제 데이터로 덮어쓰여진다).

### 5단계: 인기 포스트 위젯 템플릿 수정 (저장소 확인 필요)

작업 전 확인 3번에서 찾은 템플릿을 수정하라. 현재는 다음과 비슷할 것이다.

```liquid
{% assign popular_posts = site.posts | where: 'popular', true | sort: 'popular_rank' %}
{% for post in popular_posts %}
  <a href="{{ post.url }}">{{ post.title }}</a>
{% endfor %}
```

데이터 파일은 이미 rank 순서로 저장되므로 템플릿에서 정렬이 필요 없다.

**위젯이 제목+링크만 표시하는 경우** (가장 흔함):

```liquid
{% if site.data.popular and site.data.popular.posts %}
  {% for item in site.data.popular.posts %}
    <a href="{{ site.baseurl }}{{ item.url }}">{{ item.title }}</a>
  {% endfor %}
{% endif %}
```

**위젯이 썸네일/발췌문 등 포스트 객체 전체를 쓰는 경우** (예: postbox.html include):

```liquid
{% for item in site.data.popular.posts %}
  {% assign post = site.posts | where: 'url', item.url | first %}
  {% if post %}
    {% include postbox.html post=post %}
  {% endif %}
{% endfor %}
```

실제 위젯이 표시하는 내용을 보고 둘 중 적절한 형태를 선택하되, 기존 위젯의
HTML 구조(클래스, 래퍼 등)는 최대한 보존하라. 인기 포스트가 한국어 포스트만
대상이므로(선정 로직이 경로 깊이 1만 포함), `site.posts`(한국어 컬렉션)에서의
조회로 충분하다.

## 하지 말아야 할 것

- **기존 frontmatter 필드를 일괄 삭제하지 말 것.** 현재 약 10개 포스트에 남아 있는
  `popular`/`popular_rank`/`popular_views`/`popular_updated`는 그대로 두어라.
  새 시스템이 이 필드를 읽지도 쓰지도 않으므로 더 이상 변하지 않고 얼어붙는다.
  churn을 일으키지 않는다. 지금 일괄 삭제하면 10개 포스트를 한 번 더 수정하게
  되는데, 검색엔진 색인 회복기에는 그 한 번의 변경조차 피하는 편이 안전하다.
  (회복이 안정된 뒤 별도 작업으로 정리할 예정이다.)
- **`field_order.json`을 수정하지 말 것.** 위 frontmatter 필드를 남겨 두므로
  순서 정의도 유지한다.
- **이 작업과 무관한 다른 리팩토링을 섞지 말 것.** featuredbox/postbox의 wrapfooter
  중복 추출, CSS 변수 도입 등은 이번 커밋에 포함하지 마라. 이 블로그는 현재
  검색엔진 색인 회복을 관찰 중이며, 색인 추이를 이 변경의 효과와 깔끔하게
  연결해서 판단해야 한다. 변경 범위를 이 태스크로 한정하라.
- 워크플로의 빌드/배포 단계를 "단순화"하지 말 것 (3단계 주의 참고).

## 검증

1. 로컬 또는 CI에서 `python scripts/update_popular.py`가 GA4 자격증명 환경에서
   정상 실행되고 `_data/popular.yml`이 채워지는지 확인. (GA4 자격증명이 없는 로컬
   환경이면 이 단계는 CI의 workflow_dispatch 실행으로 대체.)
2. `bundle exec jekyll build`가 에러 없이 빌드되는지 확인.
3. 빌드 결과에서 인기 포스트 위젯이 정상적으로 렌더링되는지 확인(제목과 링크가
   올바르게 나오는지).
4. 새 시스템이 어떤 포스트 `.md` 파일도 수정하지 않는지 확인. 즉
   `update_popular.py` 실행 후 `git status`에 포스트 파일 변경이 없어야 하고,
   오직 `_data/popular.yml`만 변경 후보여야 한다.
5. 기존 워크플로 `update-popular-frontmatter.yml`이 삭제되어 더 이상 실행되지
   않는지 확인.

## 커밋 전략

이 태스크를 하나의 논리적 변경으로 묶어 커밋하라(파일 삭제, 새 스크립트/워크플로
추가, 데이터 파일 추가, 템플릿 수정). 다른 변경과 섞지 마라. 커밋 메시지 예시:

```
♻️ Move popular posts from frontmatter to _data/popular.yml

매일 포스트 frontmatter를 갱신하던 방식을 데이터 파일 한 곳에 저장하는 방식으로
변경. 포스트 파일이 더 이상 매일 수정되지 않아 검색엔진 churn 신호 제거.
순위 변동이 없는 날은 커밋/배포도 생략.
```

작업 완료 후, 새 워크플로를 GitHub Actions에서 workflow_dispatch로 한 번 수동
실행하여 실제 GA4 데이터로 `_data/popular.yml`이 채워지고 사이트가 정상 배포되는지
최종 확인하라.
