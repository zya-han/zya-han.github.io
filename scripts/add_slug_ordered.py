#!/usr/bin/env python3
"""
모든 포스트 파일에 slug 필드 추가 (필드 순서 유지)
파일명: YYYY-MM-DD-slug.md → frontmatter에 slug: slug 추가
"""

import os
import re
import yaml
import json
from collections import OrderedDict

# 모든 포스트 디렉토리
POSTS_DIRS = [
    "_posts",
    "_zh_posts",
    "_en_posts",  # 필요시 추가
]


class FlowList(list):
    """Flow style (inline)로 덤프될 리스트"""
    pass


class QuotedStr(str):
    """큰따옴표로 감싸져서 덤프될 문자열"""
    pass


def represent_flow_list(dumper, data):
    """리스트를 [item1, item2] 형식으로 출력"""
    return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=True)


def represent_quoted_str(dumper, data):
    """문자열을 "value" 형식으로 출력"""
    return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')

def load_field_order():
    """field_order.json에서 필드 순서 로드"""
    # 스크립트 파일 위치 기준으로 JSON 파일 찾기
    script_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(script_dir, 'field_order.json')
    
    # JSON 파일이 scripts/ 디렉토리에 없으면 상위 디렉토리 확인
    if not os.path.exists(json_path):
        json_path = os.path.join(os.path.dirname(script_dir), 'field_order.json')
    
    # 그래도 없으면 현재 작업 디렉토리 확인
    if not os.path.exists(json_path):
        json_path = 'field_order.json'
    
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('field_order', [])
    except FileNotFoundError:
        print(f"⚠️  field_order.json 파일을 찾을 수 없습니다: {json_path}")
        print("    기본 순서를 사용합니다.")
        # 기본 순서 (fallback)
        return [
            'layout', 'title', 'author', 'lang', 'baseurl',
            'categories', 'tags', 'date', 'image', 'insertimage',
            'description', 'featured', 'hidden', 'comments',
            'slug', 'popular', 'popular_rank', 'popular_views', 'popular_updated'
        ]
    except json.JSONDecodeError as e:
        print(f"❌ field_order.json 파싱 에러: {e}")
        return []


# 필드 순서 로드
FIELD_ORDER = load_field_order()

# YAML representer 등록
def represent_ordereddict(dumper, data):
    """OrderedDict를 순서 유지하면서 YAML로 변환"""
    return dumper.represent_dict(data.items())


yaml.add_representer(OrderedDict, represent_ordereddict)
yaml.add_representer(FlowList, represent_flow_list)
yaml.add_representer(QuotedStr, represent_quoted_str)

filename_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}-(.+)\.md$")

def parse_frontmatter(content):
    """
    파일 내용에서 frontmatter와 본문 분리
    frontmatter 순서 보존
    """
    if not content.startswith('---\n'):
        return None, content
    
    # frontmatter 끝 찾기
    end_match = re.search(r'\n---\n', content[4:])
    if not end_match:
        return None, content
    
    end_pos = end_match.start() + 4
    
    # frontmatter와 본문 분리
    frontmatter_text = content[4:end_pos]
    body = content[end_pos + 4:]  # '---\n' 건너뛰기
    
    # YAML 파싱 (순서 보존)
    try:
        # PyYAML에서 순서를 보존하려면 Loader 설정
        frontmatter_dict = yaml.load(frontmatter_text, Loader=yaml.FullLoader)
        return frontmatter_dict, body
    except yaml.YAMLError as e:
        print(f"      ❌ YAML 파싱 에러: {e}")
        return None, content

def order_frontmatter(data):
    """frontmatter를 지정된 순서대로 재정렬"""
    ordered = OrderedDict()
    
    # 1. 지정된 순서대로 필드 추가
    for field in FIELD_ORDER:
        if field in data:
            value = data[field]
            
            # categories와 tags는 FlowList로 변환 (inline 표시: [item1, item2])
            if field in ['categories', 'tags'] and isinstance(value, list):
                ordered[field] = FlowList(value)
            # title, subtitle, description은 QuotedStr로 변환 (큰따옴표로 감싸기)
            elif field in ['title', 'subtitle', 'description'] and isinstance(value, str):
                ordered[field] = QuotedStr(value)
            else:
                ordered[field] = value
    
    # 2. 순서에 없는 필드는 뒤에 추가 (알파벳순)
    remaining_fields = sorted(set(data.keys()) - set(FIELD_ORDER))
    for field in remaining_fields:
        value = data[field]
        
        # 순서에 없는 필드도 동일한 규칙 적용
        if field in ['categories', 'tags'] and isinstance(value, list):
            ordered[field] = FlowList(value)
        elif field in ['title', 'subtitle', 'description'] and isinstance(value, str):
            ordered[field] = QuotedStr(value)
        else:
            ordered[field] = value
    
    return ordered

def dump_frontmatter(data, body):
    """frontmatter와 본문을 다시 조합"""
    # frontmatter를 순서대로 정렬
    ordered_data = order_frontmatter(data)
    
    # YAML 덤프 (순서 유지, 들여쓰기 2칸)
    yaml_text = yaml.dump(
        dict(ordered_data),  # OrderedDict를 dict로 변환
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,  # 중요: 알파벳순 정렬 비활성화
        indent=2,
        width=1000  # 긴 줄 자동 줄바꿈 방지
    )
    
    # categories/tags 라인에만 대괄호 안쪽 공백 추가
    lines = yaml_text.split('\n')
    for i, line in enumerate(lines):
        if line.startswith('categories:') or line.startswith('tags:'):
            # 해당 라인의 대괄호에만 공백 추가
            line = re.sub(r'\[(?! )', '[ ', line)  # [ 뒤에 공백 추가
            line = re.sub(r'(?<! )\]', ' ]', line)  # ] 앞에 공백 추가
            lines[i] = line
    
    yaml_text = '\n'.join(lines)
    
    body_stripped = body.lstrip('\n')
    return f"---\n{yaml_text}---\n\n{body_stripped}"

total_added = 0
total_existing = 0
total_mismatch = 0
total_errors = 0

for posts_dir in POSTS_DIRS:
    if not os.path.exists(posts_dir):
        print(f"⚠️  {posts_dir} 디렉토리가 없습니다. 건너뜁니다.")
        continue
    
    print(f"\n📁 {posts_dir} 처리 중...")
    
    # 하위 디렉토리 포함 검색
    for root, dirs, files in os.walk(posts_dir):
        for filename in files:
            if filename.endswith(".md") and filename_pattern.match(filename):
                slug = filename_pattern.match(filename).group(1)
                path = os.path.join(root, filename)

                try:
                    # 파일 읽기
                    with open(path, "r", encoding="utf-8") as f:
                        content = f.read()
                    
                    # frontmatter 파싱
                    frontmatter_dict, body = parse_frontmatter(content)
                    
                    if frontmatter_dict is None:
                        print(f"   ⚠️  frontmatter 없음 → {os.path.relpath(path)}")
                        continue
                    
                    # slug 처리
                    if "slug" not in frontmatter_dict:
                        # slug 추가
                        frontmatter_dict["slug"] = slug
                        
                        # 파일 쓰기
                        new_content = dump_frontmatter(frontmatter_dict, body)
                        with open(path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        
                        print(f"   ✅ slug '{slug}' 추가됨 → {os.path.relpath(path)}")
                        total_added += 1
                    else:
                        # 기존 slug와 파일명의 slug가 다르면 경고
                        existing_slug = frontmatter_dict["slug"]
                        if existing_slug != slug:
                            print(f"   ⚠️  slug 불일치 → {os.path.relpath(path)}")
                            print(f"      파일명: '{slug}', frontmatter: '{existing_slug}'")
                            total_mismatch += 1
                        total_existing += 1
                        
                except Exception as e:
                    print(f"   ❌ 처리 실패 → {os.path.relpath(path)}: {e}")
                    total_errors += 1

print(f"\n{'='*70}")
print(f"✅ 총 {total_added}개 포스트에 slug 추가")
print(f"✔️  총 {total_existing}개 포스트는 이미 slug 존재")
if total_mismatch > 0:
    print(f"⚠️  총 {total_mismatch}개 포스트에 slug 불일치 경고")
if total_errors > 0:
    print(f"❌ 총 {total_errors}개 포스트 처리 실패")
print(f"{'='*70}")
