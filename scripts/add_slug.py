import os
import re
import frontmatter

POSTS_DIR = "_zh_posts"

filename_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$")

for filename in os.listdir(POSTS_DIR):
    if filename.endswith(".md") and filename_pattern.match(filename):
        slug = filename_pattern.match(filename).group(1)
        path = os.path.join(POSTS_DIR, filename)

        with open(path, "r", encoding="utf-8") as f:
            post = frontmatter.load(f)

        if "slug" not in post.metadata:
            post["slug"] = slug
            # frontmatter.dumps()는 문자열을 반환
            new_content = frontmatter.dumps(post)
            with open(path, "w", encoding="utf-8") as f:
                f.write(new_content)
            print(f"✅ slug '{slug}' 추가됨 → {filename}")
        else:
            print(f"✔️ 이미 slug 존재 → {filename}")