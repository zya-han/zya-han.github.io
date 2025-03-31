import os
import glob
import yaml
import math
import re
from collections import defaultdict
import frontmatter

POSTS_DIR = "_posts"
OUTPUT_YML = "_data/tag_tfidf.yml"
MAX_RELATED = 3


# URL 수동 생성 함수
def generate_url(filename):
    basename = os.path.splitext(os.path.basename(filename))[0]
    slug = basename.split("-", 3)[-1].strip('/')
    return f'/{slug}/'


def count_tag_occurrences(tag, content):
    # 조사 포함한 한국어 형태 대응: 접두어 + 조사 포함된 단어를 정규식으로 처리
    # 예: "조조", "조조는", "조조에게", "조조를" 등
    pattern = rf"\b{re.escape(tag)}[가-힣]*\b"
    return len(re.findall(pattern, content))

# 1. 모든 포스트 로딩
posts = []
tag_document_freq = defaultdict(int)

for filepath in glob.glob(os.path.join(POSTS_DIR, "*.md")):
    post_data = frontmatter.load(filepath)
    tags = post_data.get("tags", [])
    url = generate_url(filepath)
    manual_related = post_data.metadata.get("related_posts", [])

    content = post_data.content

    # TF 계산: 태그가 본문에 얼마나 등장했는지
    tf_dict = {}
    for tag in tags:
        tf = count_tag_occurrences(tag, content)
        if tf > 0:
            tf_dict[tag] = tf
            tag_document_freq[tag] += 1

    posts.append({
        "url": url,
        "tags": tags,
        "tf": tf_dict,
        "related_posts": manual_related
    })

N = len(posts)

# 2. TF-IDF 점수로 관련 글 추천
related_dict = {}

for post in posts:
    current_url = post["url"]
    current_tags = set(post["tags"])
    current_tf = post["tf"]
    manual_related = post.get("related_posts", [])

    if manual_related:
        # ✅ 수동 추천이 존재하면 그대로 사용 (최대 3개만)
        related_dict[current_url] = manual_related[:MAX_RELATED]
        continue

    # 아니면 기존 TF-IDF 계산
    scores = []
    for other in posts:
        if other["url"] == current_url:
            continue

        score = 0.0
        for tag in current_tags.intersection(other["tags"]):
            tf = other["tf"].get(tag, 0)
            idf = math.log(N / (1 + tag_document_freq[tag]))
            score += tf * idf

        if score > 0:
            scores.append((other["url"], score))

    scores.sort(key=lambda x: x[1], reverse=True)
    related_dict[current_url] = [url for url, _ in scores[:MAX_RELATED]]


# 3. YAML로 저장
os.makedirs(os.path.dirname(OUTPUT_YML), exist_ok=True)

with open(OUTPUT_YML, "w", encoding="utf-8") as f:
    yaml.dump(related_dict, f, allow_unicode=True)

print(f"✅ 관련 글 추천 데이터가 {OUTPUT_YML}에 저장되었습니다.")
