import os
import yaml
import re
from collections import Counter

POSTS_DIR = "_posts"
OUTPUT_FILE = "_data/tag_counts.yml"

def extract_tags_from_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    # YAML front matter 추출
    match = re.match(r'^---\n(.*?)\n---\n', content, re.DOTALL)
    if not match:
        return []

    front_matter = yaml.safe_load(match.group(1))
    tags = front_matter.get("tags", [])

    # 문자열이면 리스트로 변환
    if isinstance(tags, str):
        tags = [tags]

    return tags

def build_tag_counts():
    tag_counter = Counter()

    for root, _, files in os.walk(POSTS_DIR):
        for filename in files:
            if filename.endswith(".md") or filename.endswith(".markdown"):
                filepath = os.path.join(root, filename)
                tags = extract_tags_from_file(filepath)
                tag_counter.update(tags)

    return tag_counter

def save_to_yaml(tag_counts, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        yaml.dump(dict(tag_counts), f, allow_unicode=True, sort_keys=True)

if __name__ == "__main__":
    tag_counts = build_tag_counts()
    save_to_yaml(tag_counts, OUTPUT_FILE)
    print(f"✅ Generated tag count YAML at {OUTPUT_FILE}")