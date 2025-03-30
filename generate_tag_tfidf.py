import os
import re
import yaml
from collections import defaultdict, Counter
from math import log
from pathlib import Path

POSTS_DIR = "_posts"
TAG_COUNT_FILE = "_data/tag_counts.yml"
TFIDF_FILE = "_data/tag_tfidf.yml"

def extract_tags_and_body(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not match:
        return None, [], content
    front_matter = yaml.safe_load(match.group(1))
    tags = front_matter.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]
    
    url = front_matter.get("permalink")
    if not url:
        rel_path = Path(filepath).relative_to(POSTS_DIR)
        slug = rel_path.stem
        parts = slug.split('-')  # e.g. 2024-12-01-intelligent-women
        if len(parts) >= 4:
            rest = '-'.join(parts[3:])
            url = f"/{rest}/"
        else:
            url = f"/{slug}/"

    return url, tags, content

def compute_tfidf():
    tag_document_frequency = Counter()
    post_tag_counts = {}  # url: Counter(tag -> count)
    total_docs = 0

    for root, _, files in os.walk(POSTS_DIR):
        for file in files:
            if not file.endswith((".md", ".markdown")):
                continue
            path = os.path.join(root, file)
            url, tags, body = extract_tags_and_body(path)
            if not url or not tags:
                continue
            body_lower = body.lower()
            tag_counts = Counter()
            for tag in tags:
                matches = re.findall(r'\b' + re.escape(tag.lower()), body_lower)
                tag_counts[tag.lower()] = len(matches) if matches else 1
            post_tag_counts[url] = tag_counts
            for tag in set(tag_counts.keys()):
                tag_document_frequency[tag] += 1
            total_docs += 1

    # IDF 계산
    idf_scores = {
        tag: log(total_docs / df)
        for tag, df in tag_document_frequency.items()
    }

    # TF-IDF 계산
    post_tfidf = {}
    for url, tag_counts in post_tag_counts.items():
        total_tags = sum(tag_counts.values())
        raw_tfidf = {}
        for tag, count in tag_counts.items():
            tf = count / total_tags
            raw_tfidf[tag] = tf * idf_scores.get(tag, 0)

        norm = sum(v * v for v in raw_tfidf.values()) ** 0.5 or 1.0
        tfidf = {tag: round(value / norm, 6) for tag, value in raw_tfidf.items()}
        post_tfidf[url] = tfidf

    return tag_document_frequency, post_tfidf

def save_yaml(data, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, sort_keys=True)

if __name__ == "__main__":
    tag_counts, tfidf_data = compute_tfidf()
    save_yaml(tag_counts, TAG_COUNT_FILE)
    save_yaml(tfidf_data, TFIDF_FILE)
    print("✅ TF-IDF 데이터 생성 완료!")
