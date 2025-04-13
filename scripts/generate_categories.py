import yaml
import os

def generate_category_files(data_path, output_dir, base_permalink):
    with open(data_path, 'r', encoding='utf-8') as f:
        categories = yaml.safe_load(f)

    os.makedirs(output_dir, exist_ok=True)

    for cat_name, info in categories.items():
        filename = f"{cat_name}.md".replace(" ", "-")
        filepath = os.path.join(output_dir, filename)

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('---\n')
            f.write('layout: category\n')
            lang = info.get("lang", "zh" if base_permalink.startswith("/zh") else "ko")
            f.write(f'lang: {lang}\n')
            f.write(f'title: "{info.get("title", cat_name)}"\n')
            f.write(f'category: "{cat_name}"\n')
            f.write(f'permalink: {info.get("permalink", "")}\n')
            f.write(f'description: "{info.get("description", "")}"\n')
            f.write(f'image: {info.get("image", "")}\n')
            if "shortlink" in info:
                f.write(f'shortlink: {info["shortlink"]}\n')
            f.write('---\n')

    print(f"✅ {output_dir} 디렉토리에 카테고리 파일 생성 완료!")

# 한글 카테고리
generate_category_files('_data/category_ko.yml', '_categories', '/category')

# 중국어 카테고리
generate_category_files('_data/category_zh.yml', '_zh_categories', '/zh/category')