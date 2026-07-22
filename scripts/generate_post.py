"""
매일 자동으로 AI 툴 소식을 모아서 블로그 글(마크다운)을 생성하는 스크립트.

동작 순서:
1. Hacker News Algolia API에서 최근 24~48시간 내 "AI 툴/제품" 관련 글 수집 (API 키 불필요)
2. Claude API에게 넘겨서 개발자 대상 한국어 큐레이션 글 작성 요청
3. 결과를 _posts/YYYY-MM-DD-ai-tools.md 로 저장 (Jekyll이 이 폴더를 자동으로 읽어서 블로그에 반영)

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
        "요구사항:\n"
        "- 제목은 흥미롭게, 너무 낚시성은 금지\n"
        "- 각 항목마다: 무엇인지 2~3문장 요약 + 왜 주목할만한지 1문장 + 원문 링크\n"
        "- 전체 서두에 오늘의 트렌드를 2~3문장으로 정리\n"
        "- 마크다운 형식으로, Jekyll frontmatter 없이 본문만 작성 (frontmatter는 스크립트가 별도로 붙임)\n"
        "- 과장광고체 금지, 담백하고 신뢰가는 톤\n"
        "- 실제 제공된 항목에 대해서만 쓰고, 없는 내용을 지어내지 말 것"
    )

    user_prompt = f"오늘 수집된 항목들:\n\n{stories_text}\n\n이 내용으로 블로그 포스트 본문(마크다운)을 작성해줘."

    body = json.dumps(
        {
            "model": "claude-sonnet-5",
            "max_tokens": 2000,
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


def extract_title(markdown_body, fallback):
    """생성된 본문 첫 줄이 '# 제목' 형태면 그걸 title로 쓰고 본문에서는 제거"""
    lines = markdown_body.splitlines()
    if lines and lines[0].startswith("# "):
        title = lines[0][2:].strip()
        rest = "\n".join(lines[1:]).lstrip("\n")
        return title, rest
    return fallback, markdown_body


def main():
    today = datetime.date.today()
    stories = fetch_hn_stories()

    if not stories:
        print("오늘은 조건에 맞는 글이 없어서 포스트를 건너뜁니다.")
        return

    body = call_claude(stories)
    fallback_title = f"{today.isoformat()} 오늘의 AI 툴 큐레이션"
    title, body = extract_title(body, fallback_title)

    safe_slug = "ai-tools"
    filename = f"_posts/{today.isoformat()}-{safe_slug}.md"

    frontmatter = (
        "---\n"
        "layout: post\n"
        f"title: \"{title}\"\n"
        f"date: {today.isoformat()} 08:00:00 +0900\n"
        "categories: [ai-tools]\n"
        "---\n\n"
    )

    os.makedirs("_posts", exist_ok=True)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(frontmatter + body + "\n")

    print(f"작성 완료: {filename}")


if __name__ == "__main__":
    main()
