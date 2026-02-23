#!/usr/bin/env python3
"""
GA4 Data API로 인기 포스트를 가져와서
각 포스트의 frontmatter에 popular: true 추가
"""

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest,
    DateRange,
    Dimension,
    Metric,
    OrderBy
)
import yaml
import json
import os
import glob
import re
from datetime import datetime
from collections import OrderedDict


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

# 환경 변수에서 설정 값 가져오기
GA4_PROPERTY_ID = os.environ.get('GA4_PROPERTY_ID', '482435885')
DAYS_AGO = int(os.environ.get('DAYS_AGO', '7'))
TOP_N = int(os.environ.get('TOP_N', '10'))

# 포스트 디렉토리 (다국어 지원)
POSTS_DIRS = [
    '_posts',
    '_zh_posts',  # 중국어 포스트
    '_en_posts',  # 영어 포스트 (있다면)
]


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


def parse_frontmatter(content):
    """파일 내용에서 frontmatter와 본문 분리 (순서 보존)"""
    if not content.startswith('---\n'):
        return None, content
    
    end_match = re.search(r'\n---\n', content[4:])
    if not end_match:
        return None, content
    
    end_pos = end_match.start() + 4
    frontmatter_text = content[4:end_pos]
    body = content[end_pos + 4:]
    
    try:
        frontmatter_dict = yaml.load(frontmatter_text, Loader=yaml.FullLoader)
        return frontmatter_dict, body
    except yaml.YAMLError:
        return None, content


def order_frontmatter(data):
    """frontmatter를 지정된 순서대로 재정렬"""
    ordered = OrderedDict()
    
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
    ordered_data = order_frontmatter(data)
    
    yaml_text = yaml.dump(
        dict(ordered_data),
        allow_unicode=True,
        default_flow_style=False,
        sort_keys=False,
        indent=2,
        width=1000
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


def get_top_post_paths():
    """GA4에서 상위 조회수 포스트 경로 가져오기"""
    
    client = BetaAnalyticsDataClient()
    
    request = RunReportRequest(
        property=f"properties/{GA4_PROPERTY_ID}",
        dimensions=[
            Dimension(name="pagePath"),
            Dimension(name="pageTitle")
        ],
        metrics=[
            Metric(name="screenPageViews")
        ],
        date_ranges=[
            DateRange(
                start_date=f"{DAYS_AGO}daysAgo",
                end_date="today"
            )
        ],
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                desc=True
            )
        ],
        limit=100
    )
    
    try:
        response = client.run_report(request)
    except Exception as e:
        print(f"❌ GA4 API 호출 실패: {e}")
        return []
    
    # 포스트 경로 추출
    top_paths = []
    
    for row in response.rows:
        path = row.dimension_values[0].value
        views = int(row.metric_values[0].value)
        
        # 제외할 페이지
        EXCLUDE_PATHS = [
            '/',
            '/zya.han/posts',
            '/about', '/about/',
            '/contact', '/contact/',
            '/archive', '/archive/',
        ]
        
        if path in EXCLUDE_PATHS:
            continue
        
        # 패턴으로 제외
        if (path.startswith('/tag') or 
            path.startswith('/category') or
            path.startswith('/search') or
            path.startswith('/page') or
            path == '(not set)' or
            '/404' in path or
            path.endswith('.xml') or
            path.endswith('.json')):
            continue
        
        # 포스트 판별: 경로 깊이가 1
        path_segments = [s for s in path.strip('/').split('/') if s]
        is_post = len(path_segments) == 1
        
        if is_post:
            top_paths.append({
                'path': path,
                'views': views
            })
        
        if len(top_paths) >= TOP_N:
            break
    
    return top_paths


def find_post_file_by_path(url_path):
    """
    URL 경로로 포스트 MD 파일 찾기
    
    예: /geunyeo/ → _posts/*/2024-12-13-geunyeo.md
    """
    slug = url_path.strip('/')
    
    for posts_dir in POSTS_DIRS:
        if not os.path.exists(posts_dir):
            continue
        
        # 패턴 1: YYYY-MM-DD-slug.md 직접 매칭
        pattern1 = os.path.join(posts_dir, '**', f'*-{slug}.md')
        matches = glob.glob(pattern1, recursive=True)
        if matches:
            return matches[0]
        
        # 패턴 2: frontmatter의 slug 필드 확인
        all_posts = glob.glob(os.path.join(posts_dir, '**', '*.md'), recursive=True)
        for post_file in all_posts:
            try:
                with open(post_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                frontmatter_dict, _ = parse_frontmatter(content)
                if frontmatter_dict is None:
                    continue
                
                # slug 필드 확인
                if frontmatter_dict.get('slug') == slug:
                    return post_file
                
                # permalink 필드 확인
                if frontmatter_dict.get('permalink') == url_path:
                    return post_file
                
            except Exception:
                continue
    
    return None


def clear_all_popular_flags():
    """모든 포스트에서 popular: true 제거"""
    
    cleared_count = 0
    
    for posts_dir in POSTS_DIRS:
        if not os.path.exists(posts_dir):
            continue
        
        all_posts = glob.glob(os.path.join(posts_dir, '**', '*.md'), recursive=True)
        
        for post_file in all_posts:
            try:
                with open(post_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                frontmatter_dict, body = parse_frontmatter(content)
                if frontmatter_dict is None:
                    continue
                
                # popular 관련 필드가 있으면 제거
                changed = False
                for key in ['popular', 'popular_rank', 'popular_views', 'popular_updated']:
                    if key in frontmatter_dict:
                        del frontmatter_dict[key]
                        changed = True
                
                if changed:
                    new_content = dump_frontmatter(frontmatter_dict, body)
                    with open(post_file, 'w', encoding='utf-8') as f:
                        f.write(new_content)
                    cleared_count += 1
                    
            except Exception as e:
                print(f"⚠️  {post_file} 처리 실패: {e}")
                continue
    
    if cleared_count > 0:
        print(f"🧹 {cleared_count}개 포스트에서 popular 플래그 제거")
    
    return cleared_count


def add_popular_flag(post_file, rank, views):
    """포스트 frontmatter에 popular: true 추가"""
    
    try:
        with open(post_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        frontmatter_dict, body = parse_frontmatter(content)
        if frontmatter_dict is None:
            return False
        
        # popular 필드 추가
        frontmatter_dict['popular'] = True
        frontmatter_dict['popular_rank'] = rank
        frontmatter_dict['popular_views'] = views
        frontmatter_dict['popular_updated'] = datetime.now().strftime('%Y-%m-%d')
        
        new_content = dump_frontmatter(frontmatter_dict, body)
        with open(post_file, 'w', encoding='utf-8') as f:
            f.write(new_content)
        
        return True
        
    except Exception as e:
        print(f"❌ {post_file} 업데이트 실패: {e}")
        return False


def main():
    print(f"🔍 GA4에서 최근 {DAYS_AGO}일간 상위 {TOP_N}개 포스트 조회 중...")
    print(f"📊 Property ID: {GA4_PROPERTY_ID}\n")
    
    # 1. GA4에서 인기 포스트 경로 가져오기
    top_paths = get_top_post_paths()
    
    if not top_paths:
        print("⚠️  조회된 포스트가 없습니다.")
        return
    
    print(f"📈 GA4에서 {len(top_paths)}개 인기 포스트 발견\n")
    
    # 2. 기존 모든 popular 플래그 제거
    print("🧹 기존 popular 플래그 제거 중...")
    clear_all_popular_flags()
    print()
    
    # 3. 상위 포스트에 popular: true 추가
    print(f"✨ 상위 {len(top_paths)}개 포스트에 popular 플래그 추가 중...\n")
    
    success_count = 0
    not_found_count = 0
    
    for i, item in enumerate(top_paths, 1):
        path = item['path']
        views = item['views']
        
        # URL 경로로 MD 파일 찾기
        post_file = find_post_file_by_path(path)
        
        if post_file:
            if add_popular_flag(post_file, i, views):
                print(f"✅ #{i:2d} | {views:>6} views | {path:<30} → {os.path.basename(post_file)}")
                success_count += 1
            else:
                print(f"❌ #{i:2d} | {views:>6} views | {path:<30} → 업데이트 실패")
        else:
            print(f"⚠️  #{i:2d} | {views:>6} views | {path:<30} → MD 파일을 찾을 수 없음")
            not_found_count += 1
    
    # 결과 요약
    print(f"\n{'='*80}")
    print(f"✅ 성공: {success_count}개 포스트에 popular 플래그 추가")
    if not_found_count > 0:
        print(f"⚠️  경고: {not_found_count}개 포스트의 MD 파일을 찾지 못함")
    print(f"{'='*80}\n")
    
    if success_count > 0:
        print("💡 Jekyll에서 사용법:")
        print("   {% assign popular_posts = site.posts | where: 'popular', true %}")
        print("   {% for post in popular_posts %}")
        print("     {{ post.title }}")
        print("   {% endfor %}")


if __name__ == '__main__':
    main()
