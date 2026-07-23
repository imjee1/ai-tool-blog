# 오늘의 AI 툴 — 자동 블로그

매일 아침 Hacker News에서 화제가 된 AI 툴/제품을 수집해서, Claude API가 한국어 큐레이션 글을 써서
자동으로 블로그에 올리는 프로젝트입니다. **한번 세팅하면 그 뒤로는 손댈 일이 거의 없습니다.**

Astro로 만든 정적 사이트이며, GitHub Actions가 매일 글을 쓰고 빌드해서 GitHub Pages에 배포합니다.

## 어떻게 도나요

```
GitHub Actions (매일 새벽, 크론)
   → scripts/generate_post.py 실행
     → Hacker News에서 AI 관련 인기글 수집 (무료, API 키 불필요)
     → Claude API로 한국어 블로그 글 작성
     → src/content/blog/에 마크다운 파일 생성
   → 자동 커밋 & 푸시
   → Astro 빌드 (npm run build)
   → GitHub Pages에 자동 배포
```

## 세팅 방법 (처음 한 번만 하면 됩니다)

### 1. GitHub 저장소 만들기
- GitHub에서 새 저장소 생성 (예: `ai-tool-blog`)
- 이 폴더 전체를 그 저장소에 push

```bash
cd ai-tool-blog
git init
git add .
git commit -m "init"
git branch -M main
git remote add origin https://github.com/내아이디/ai-tool-blog.git
git push -u origin main
```

### 2. Anthropic API 키를 GitHub Secret으로 등록
1. 저장소 페이지 → **Settings → Secrets and variables → Actions**
2. **New repository secret** 클릭
3. Name: `ANTHROPIC_API_KEY`
4. Value: 본인의 Anthropic API 키 (console.anthropic.com에서 발급)

### 3. GitHub Pages 켜기 — "GitHub Actions"로 설정
1. 저장소 페이지 → **Settings → Pages**
2. Source를 **GitHub Actions**로 선택 (Jekyll 시절의 "Deploy from a branch"가 아닙니다!)
3. 몇 분 후 `https://내아이디.github.io/저장소이름/` 에서 블로그 확인 가능

### 4. 저장소 이름이 `ai-tool-blog`가 아니라면
`astro.config.mjs`의 `site`와 `base` 값을 본인의 GitHub 아이디/저장소 이름에 맞게 수정하세요.

```js
export default defineConfig({
  site: 'https://내아이디.github.io',
  base: '/저장소이름/',
  ...
});
```

### 5. 잘 도는지 수동으로 먼저 테스트
- 저장소 → **Actions** 탭 → `Daily AI tool post` 워크플로우 선택 → **Run workflow** 버튼으로 바로 1회 실행해볼 수 있습니다.
- 문제없이 돌면 `src/content/blog/` 폴더에 오늘 날짜 파일이 생기고, 빌드 후 블로그에 반영됩니다.

## 로컬에서 미리보기

```bash
npm install
npm run dev
```

Node.js 20 이상이 필요합니다 (권장: 22 이상).

## 이후 운영
- **아무것도 안 해도 매일 자동으로 올라갑니다.** (한국시간 오전 8시)
- 글 톤이나 형식을 바꾸고 싶으면 `scripts/generate_post.py` 안의 `system_prompt` 부분만 수정하면 됩니다.
- 검색 키워드(`KEYWORDS` 리스트)를 조정해서 다루는 주제를 좁히거나 넓힐 수 있습니다.
- 디자인을 바꾸고 싶으면 `src/components/`, `src/styles/global.css`, `src/layouts/BlogPost.astro`를 수정하세요.

## 수익화 아이디어 (나중에)
- 글 안에 제휴 링크(예: 소개한 툴의 추천인 링크) 자연스럽게 삽입
- 트래픽 어느 정도 쌓이면 애드센스 붙이기
- "이 주의 AI 툴 TOP 5" 같은 걸 묶어서 뉴스레터로 재발행 (이메일 구독 기반 수익화)

## 주의할 점
- Hacker News API는 무료지만, 매일 같은 소스만 쓰면 콘텐츠가 비슷해질 수 있어요. 반응 보면서 소스(Product Hunt, GitHub Trending 등)를 추가하는 걸 추천합니다.
- 완전 방치보다는, 초반 1~2주는 매일 글이 잘 나오는지 한 번씩 확인하는 걸 권장합니다.
