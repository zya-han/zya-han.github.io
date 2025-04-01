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


def count_tag_occurrences(tag, text):
    # 조사 포함한 한국어 형태 대응: 접두어 + 조사 포함된 단어를 정규식으로 처리
    # 예: "조조", "조조는", "조조에게", "조조를" 등
    pattern = rf"\b{re.escape(tag)}\w*\b"
    return len(re.findall(pattern, text))

# 1. 모든 포스트 로딩
posts = []
tag_document_freq = defaultdict(int)
all_tags = []

for filepath in glob.glob(os.path.join(POSTS_DIR, "*.md")):
    post_data = frontmatter.load(filepath)
    tags = post_data.get("tags", [])
    url = generate_url(filepath)
    manual_related = post_data.metadata.get("related_posts", [])

    # 모든 태그의 목록을 만들기 위한 업데이트
    all_tags.extend(tags)

    # 검색 범위: 제목 + 본문 + 태그
    text = f'{post_data.metadata.get("title")} {post_data.metadata.get("subtitle", "")} {post_data.content} {" ".join(tags)}'

    # TF 계산: 태그가 본문에 얼마나 등장했는지
    tf_dict = {}

    # 현재 포스트에 설정된 모든 태그에 대해
    for tag in tags:
        # IDF 업데이트
        tag_document_freq[tag] += 1

        # 태그가 제목+본문+태그에 등장한 횟수
        tf = count_tag_occurrences(tag, text)
        tf_dict[tag] = math.log(1 + tf) # 로그

    posts.append({
        "url": url,
        "tags": tags,
        "tf": tf_dict,
        "related_posts": manual_related
    })

# IDF 계산
idf_dict = defaultdict(float)
N = len(posts)
all_tags = set(all_tags)
for tag in all_tags:
    idf = math.log(N / (1 + tag_document_freq[tag]))
    idf_dict[tag] = idf


# 모든 포스트에 TF-IDF 벡터 할당하기
for (i, post) in enumerate(posts):
    vec_dict = {}
    for tag in post["tags"]:
        vec_dict[tag] = post["tf"][tag] * idf_dict[tag]
    
    l2_norm = sum(v*v for v in vec_dict.values()) ** 0.5

    normalized_dict = {k: v/l2_norm for (k, v) in vec_dict.items()}

    posts[i]['vector'] = normalized_dict

# 2. TF-IDF 점수로 관련 글 추천
related_dict = {}

for post in posts:
    current_url = post["url"]
    current_tags = set(post["tags"])
    current_vec = post["vector"]
    manual_related = post.get("related_posts", []) or []

    # 중복 방지를 위한 셋
    seen = set(manual_related)
    
    scores = []
    for other in posts:
        if other["url"] == current_url or other["url"] in seen:
            continue

        score = 0.0
        for tag in current_tags.intersection(other["tags"]):
            # cosine similarity
            score += current_vec[tag] * other["vector"][tag]

        if score > 0:
            scores.append((other["url"], score))

    scores.sort(key=lambda x: x[1], reverse=True)
    fill_from_auto = [url for url, _ in scores if url not in seen]

    # 최대 3개까지만
    final_related = manual_related + fill_from_auto[:MAX_RELATED - len(manual_related)]
    related_dict[current_url] = final_related

# 3. YAML로 저장
os.makedirs(os.path.dirname(OUTPUT_YML), exist_ok=True)

with open(OUTPUT_YML, "w", encoding="utf-8") as f:
    yaml.dump(related_dict, f, allow_unicode=True)

print(f"✅ 관련 글 추천 데이터가 {OUTPUT_YML}에 저장되었습니다.")
