"""
GitHub / HuggingFace / arXiv 수집기
- GitHub  : 최근 7일 생성, ⭐ 10+ 기준
- HuggingFace : 최근 7일 등록, ❤️ 5+ 기준
- arXiv   : 최근 7일 게재, cs.AI / cs.LG / cs.CL / cs.CV
"""
import os
import json
import requests
import time
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone

GH_TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS_GH = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
} if GH_TOKEN else {"Accept": "application/vnd.github+json"}

TODAY = datetime.now(timezone.utc).date()
SINCE = (TODAY - timedelta(days=7)).isoformat()
DATA_DIR = "data"

GITHUB_MIN_STARS = 10
HF_MIN_LIKES = 5

GITHUB_TOPICS = [
    "llm", "large-language-model", "generative-ai", "ai",
    "machine-learning", "deep-learning", "diffusion-model",
    "multimodal", "rag", "transformer",
]


# ── GitHub ────────────────────────────────────────────────────────────────────

def collect_github() -> list[dict]:
    repos: list[dict] = []
    seen: set[str] = set()

    for topic in GITHUB_TOPICS:
        query = f"topic:{topic} created:>{SINCE} stars:>={GITHUB_MIN_STARS}"
        url = (
            "https://api.github.com/search/repositories"
            f"?q={urllib.parse.quote(query)}&sort=stars&order=desc&per_page=50"
        )
        try:
            r = requests.get(url, headers=HEADERS_GH, timeout=15)
            if r.status_code == 403:
                print(f"  [GitHub] Rate limit for topic '{topic}', waiting...")
                time.sleep(15)
                continue
            if r.status_code != 200:
                print(f"  [GitHub] API {r.status_code} for topic '{topic}'")
                continue

            for repo in r.json().get("items", []):
                if repo["full_name"] in seen:
                    continue
                seen.add(repo["full_name"])
                repos.append({
                    "source": "github",
                    "id": repo["full_name"],
                    "title": repo["name"],
                    "url": repo["html_url"],
                    "description": repo.get("description") or "",
                    "stars": repo["stargazers_count"],
                    "forks": repo.get("forks_count", 0),
                    "language": repo.get("language") or "",
                    "topics": repo.get("topics", []),
                    "created_at": repo["created_at"][:10],
                })
        except requests.exceptions.RequestException as e:
            print(f"  [GitHub] Request error for topic '{topic}': {e}")

        time.sleep(1.2)  # GitHub 검색 API rate limit 대응

    return sorted(repos, key=lambda x: x["stars"], reverse=True)[:100]


# ── HuggingFace ───────────────────────────────────────────────────────────────

def collect_huggingface() -> list[dict]:
    models: list[dict] = []
    try:
        # trending 순으로 가져온 뒤 날짜 필터 적용 (신규 모델은 likes가 적어 createdAt 정렬로는 매칭 안 됨)
        url = (
            "https://huggingface.co/api/models"
            "?sort=trending&limit=500&full=true"
        )
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            print(f"  [HuggingFace] API {r.status_code}")
            return []

        for model in r.json():
            created = (model.get("createdAt") or "")[:10]
            if created < SINCE:
                continue
            likes = model.get("likes", 0)
            if likes < HF_MIN_LIKES:
                continue
            model_id = model.get("modelId", "")
            models.append({
                "source": "huggingface",
                "id": model_id,
                "title": model_id.split("/")[-1] if "/" in model_id else model_id,
                "url": f"https://huggingface.co/{model_id}",
                "description": (model.get("description") or model.get("pipeline_tag") or "")[:500],
                "likes": likes,
                "downloads": model.get("downloads", 0),
                "tags": model.get("tags", [])[:10],
                "pipeline_tag": model.get("pipeline_tag") or "",
                "created_at": created,
            })
    except requests.exceptions.RequestException as e:
        print(f"  [HuggingFace] Request error: {e}")

    return sorted(models, key=lambda x: x["likes"], reverse=True)[:50]


# ── arXiv ─────────────────────────────────────────────────────────────────────

def collect_arxiv() -> list[dict]:
    papers: list[dict] = []
    # 날짜 필터를 URL에 넣지 않고 Python에서 처리 (특수문자 인코딩 문제 방지)
    query = urllib.parse.quote("cat:cs.AI OR cat:cs.LG OR cat:cs.CL OR cat:cs.CV")
    url = (
        f"https://export.arxiv.org/api/query"
        f"?search_query={query}&start=0&max_results=100"
        f"&sortBy=submittedDate&sortOrder=descending"
    )
    for attempt in range(3):
        try:
            r = requests.get(url, timeout=20)
            if r.status_code == 200:
                break
            print(f"  [arXiv] API {r.status_code} (attempt {attempt + 1}/3)")
            time.sleep(5 * (attempt + 1))
        except requests.exceptions.RequestException as e:
            print(f"  [arXiv] Error (attempt {attempt + 1}/3): {e}")
            time.sleep(5 * (attempt + 1))
    else:
        return []

    try:

        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(r.text)

        for entry in root.findall("atom:entry", ns):
            title_el = entry.find("atom:title", ns)
            summary_el = entry.find("atom:summary", ns)
            id_el = entry.find("atom:id", ns)
            published_el = entry.find("atom:published", ns)

            if not all([title_el, summary_el, id_el, published_el]):
                continue

            # 날짜 필터: 7일 이내 게재된 논문만
            published = published_el.text[:10]
            if published < SINCE:
                continue

            authors = [
                a.find("atom:name", ns).text
                for a in entry.findall("atom:author", ns)
                if a.find("atom:name", ns) is not None
            ][:4]

            categories = [
                c.attrib.get("term", "")
                for c in entry.findall("atom:category", ns)
            ]

            papers.append({
                "source": "arxiv",
                "id": id_el.text.strip(),
                "title": title_el.text.strip().replace("\n", " "),
                "url": id_el.text.strip(),
                "abstract": summary_el.text.strip().replace("\n", " ")[:800],
                "authors": authors,
                "categories": categories,
                "published": published,
            })
    except ET.ParseError as e:
        print(f"  [arXiv] Parse error: {e}")

    return papers


# ── Save ──────────────────────────────────────────────────────────────────────

def save(github: list, huggingface: list, arxiv: list) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    result = {
        "collected_at": TODAY.isoformat(),
        "since": SINCE,
        "github": github,
        "huggingface": huggingface,
        "arxiv": arxiv,
    }
    date_path = f"{DATA_DIR}/{TODAY.isoformat()}.json"
    latest_path = f"{DATA_DIR}/latest.json"

    for path in [date_path, latest_path]:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"Saved: {date_path}")
    print(f"  GitHub {len(github)} | HuggingFace {len(huggingface)} | arXiv {len(arxiv)}")


if __name__ == "__main__":
    print(f"Collecting since {SINCE}...\n")

    print("[1/3] GitHub...")
    github = collect_github()
    print(f"  → {len(github)} repos\n")

    print("[2/3] HuggingFace...")
    huggingface = collect_huggingface()
    print(f"  → {len(huggingface)} models\n")

    print("[3/3] arXiv...")
    arxiv = collect_arxiv()
    print(f"  → {len(arxiv)} papers\n")

    save(github, huggingface, arxiv)
