"""
매일 자동으로 AI 툴 소식을 모아서 블로그 글(마크다운)을 생성하는 스크립트.

동작 순서:
1. Hacker News Algolia API에서 최근 24~48시간 내 "AI 툴/제품" 관련 글 수집 (API 키 불필요)
2. Claude API에게 넘겨서 개발자 대상 한국어 큐레이션 글 작성 요청
3. 결과를 src/content/blog/YYYY-MM-DD-ai-tools.md 로 저장 (Astro content collection이 이 폴더를 자동으로 읽어서 블로그에 반영)

필요한 환경변수:
- ANTHROPIC_API_KEY : Anthropic API 키 (GitHub repo secret으로 설정)
"""

import os
import sys
import json
import datetime
import urllib.request
import urllib.parse

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    print("ERROR: ANTHROPIC_API_KEY 환경변수가 없습니다.", file=sys.stderr)
    sys.exit(1)

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search_by_date"

# 검색할 키워드들 (필요하면 자유롭게 추가/수정 가능)
KEYWORDS = [
    "AI tool",
    "LLM",
    "Claude",
    "GPT",
    "AI agent",
    "open source AI",
]


def fetch_hn_stories(hours=30, min_points=15):
    """최근 N시간 내에 올라온, 어느정도 반응 있는 AI 관련 Show HN / 글 수집"""
    since_ts = int(
        (datetime.datetime.utcnow() - datetime.timedelta(hours=hours)).timestamp()
    )
    seen_ids = set()
    stories = []

    for kw in KEYWORDS:
        params = {
            "query": kw,
            "tags": "story",
            "numericFilters": f"created_at_i>{since_ts},points>={min_points}",
            "hitsPerPage": "10",
        }
        url = f"{HN_SEARCH_URL}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"WARN: '{kw}' 검색 실패: {e}", file=sys.stderr)
            continue

        for hit in data.get("hits", []):
            oid = hit.get("objectID")
            if oid in seen_ids:
                continue
            seen_ids.add(oid)
            stories.append(
                {
                    "title": hit.get("title"),
                    "url": hit.get("url") or f"https://news.ycombinator.com/item?id={oid}",
                    "points": hit.get("points", 0),
                    "num_comments": hit.get("num_comments", 0),
                    "hn_link": f"https://news.ycombinator.com/item?id={oid}",
                }
            )

    # 인기순 정렬 후 상위 8개만 사용 (너무 많으면 글이 늘어져서 퀄리티가 떨어짐)
    stories.sort(key=lambda s: s["points"], reverse=True)
    return stories[:8]


def call_claude(stories):
    """Claude API를 호출해서 한국어 큐레이션 블로그 글 작성"""
    stories_text = "\n".join(
        f"- {s['title']} ({s['points']}점, 댓글 {s['num_comments']}개) - {s['url']} (토론: {s['hn_link']})"
        for s in stories
    )

    system_prompt = (
        "너는 개발자 대상 AI 뉴스레터를 매일 쓰는 에디터야. "
        "아래 Hacker News에서 오늘 화제가 된 AI 관련 글/제품 목록을 받아서, "
        "한국 개발자들이 읽기 좋은 블로그 포스트를 한국어로 작성해줘.\n\n"
        "출력 형식은 반드시 아래 구조를 지켜:\n"
        "1번째 줄: '# 제목' (흥미롭게, 너무 낚시성은 금지)\n"
        "2번째 줄: 이 글 전체를 한 문장으로 요약한 설명 (블로그 미리보기용 description으로 쓰임, 40자 내외)\n"
        "3번째 줄부터: 빈 줄 하나 띄우고 본문 시작\n\n"
        "본문 요구사항:\n"
        "- 각 항목마다: 무엇인지 2~3문장 요약 + 왜 주목할만한지 1문장 + 원문 링크\n"
        "- 전체 서두에 오늘의 트렌드를 2~3문장으로 정리\n"
        "- 마크다운 형식으로 본문만 작성 (frontmatter는 스크립트가 별도로 붙임)\n"
        "- 과장광고체 금지, 담백하고 신뢰가는 톤\n"
        "- 실제 제공된 항목에 대해서만 쓰고, 없는 내용을 지어내지 말 것"
    )

    user_prompt = f"오늘 수집된 항목들:\n\n{stories_text}\n\n이 내용으로 블로그 포스트 본문(마크다운)을 작성해줘."

    body = json.dumps(
        {
            "model": "claude-sonnet-5",
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "content-type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8"))

    # content는 블록 리스트 (text 블록만 이어붙임)
    text_parts = [block["text"] for block in data.get("content", []) if block.get("type") == "text"]
    return "\n".join(text_parts).strip()


def parse_response(markdown_body, fallback_title, fallback_description):
    """생성된 본문에서 '# 제목' / 설명 줄 / 본문을 분리"""
    lines = markdown_body.splitlines()
    title = fallback_title
    description = fallback_description
    idx = 0

    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        idx = 1

    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    if idx < len(lines):
        description = lines[idx].strip()
        idx += 1

    while idx < len(lines) and not lines[idx].strip():
        idx += 1

    body = "\n".join(lines[idx:]).lstrip("\n")
    return title, description, body


def yaml_single_quote(value):
    """YAML 단일 인용 문자열로 안전하게 이스케이프"""
    return "'" + value.replace("'", "''") + "'"


def main():
    today = datetime.date.today()
    stories = fetch_hn_stories()

    if not stories:
        print("오늘은 조건에 맞는 글이 없어서 포스트를 건너뜁니다.")
        return

    raw = call_claude(stories)
    fallback_title = f"{today.isoformat()} 오늘의 AI 큐레이션"
    fallback_description = f"{today.isoformat()} Hacker News AI 소식 큐레이션"
    title, description, body = parse_response(raw, fallback_title, fallback_description)

    safe_slug = "ai-tools"
    filename = f"src/content/blog/{today.isoformat()}-{safe_slug}.md"

    frontmatter = (
        "---\n"
        f"title: {yaml_single_quote(title)}\n"
        f"description: {yaml_single_quote(description)}\n"
        f"pubDate: '{today.strftime('%b %d %Y')}'\n"
        "---\n\n"
    )

    os.makedirs("src/content/blog", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body + "\n")

    print(f"작성 완료: {filename}")


if __name__ == "__main__":
    main()
