"""
latest.json을 읽어 카드형 README.md를 생성합니다.
"""
import json

DATA_DIR = "data"
LATEST_PATH = f"{DATA_DIR}/latest.json"

TOP_GITHUB = 30
TOP_HF = 20
TOP_ARXIV = 20

LANG_COLORS: dict[str, str] = {
    "Python": "3776AB",
    "JavaScript": "F7DF1E",
    "TypeScript": "3178C6",
    "Rust": "DEA584",
    "Go": "00ADD8",
    "C++": "F34B7D",
    "C": "555555",
    "Java": "B07219",
    "Jupyter Notebook": "DA5B0B",
    "Shell": "89E051",
}


def lang_badge(lang: str) -> str:
    if not lang:
        return ""
    color = LANG_COLORS.get(lang, "888888")
    safe = lang.replace("-", "--").replace(" ", "_")
    return f"![{lang}](https://img.shields.io/badge/-{safe}-{color}?style=flat-square&logo={lang.lower()}&logoColor=white)"


def github_card(repo: dict, rank: int) -> str:
    lang = repo.get("language", "")
    badge = lang_badge(lang)
    stars = f"{repo['stars']:,}"
    forks = f"{repo.get('forks', 0):,}"
    topics = " ".join(f"`{t}`" for t in repo.get("topics", [])[:5])
    summary = repo.get("summary", "")
    desc = repo.get("description") or "_설명 없음_"

    return f"""\
<details>
<summary>
  <b>{rank}. <a href="{repo['url']}">{repo['title']}</a></b>
  &nbsp; ⭐ <b>{stars}</b> &nbsp; {badge}
</summary>

<br>

**📝 설명**
> {desc}

{"**💡 Claude 요약**" if summary else ""}
{">" if summary else ""} {summary if summary else ""}

| | |
|---|---|
| 📅 생성일 | `{repo['created_at']}` |
| 💻 언어 | `{lang or "N/A"}` |
| ⭐ Stars | `{stars}` |
| 🍴 Forks | `{forks}` |

{"**🏷 토픽:** " + topics if topics else ""}

&nbsp;

</details>
"""


def hf_card(model: dict, rank: int) -> str:
    pipeline = model.get("pipeline_tag", "")
    likes = f"{model.get('likes', 0):,}"
    downloads = f"{model.get('downloads', 0):,}"
    tags = " ".join(f"`{t}`" for t in model.get("tags", [])[:5])
    summary = model.get("summary", "")
    desc = (model.get("description") or "_설명 없음_")[:200]

    return f"""\
<details>
<summary>
  <b>{rank}. <a href="{model['url']}">{model['title']}</a></b>
  &nbsp; ❤️ <b>{likes}</b> &nbsp; ⬇️ {downloads}
</summary>

<br>

**📝 설명**
> {desc}

{"**💡 Claude 요약**" if summary else ""}
{">" if summary else ""} {summary if summary else ""}

| | |
|---|---|
| 📅 등록일 | `{model['created_at']}` |
| 🔧 파이프라인 | `{pipeline or "N/A"}` |
| ❤️ Likes | `{likes}` |
| ⬇️ Downloads | `{downloads}` |

{"**🏷 태그:** " + tags if tags else ""}

&nbsp;

</details>
"""


def arxiv_card(paper: dict, rank: int) -> str:
    authors = ", ".join(paper.get("authors", []))
    cats = " ".join(f"`{c}`" for c in paper.get("categories", [])[:3])
    summary = paper.get("summary", "")
    abstract = paper.get("abstract", "")[:250] + "..."

    return f"""\
<details>
<summary>
  <b>{rank}. <a href="{paper['url']}">{paper['title']}</a></b>
  &nbsp; 📅 {paper['published']}
</summary>

<br>

**📝 초록 (일부)**
> {abstract}

{"**💡 Claude 요약**" if summary else ""}
{">" if summary else ""} {summary if summary else ""}

| | |
|---|---|
| 📅 게재일 | `{paper['published']}` |
| 👤 저자 | {authors or "N/A"} |

{"**🏷 카테고리:** " + cats if cats else ""}

&nbsp;

</details>
"""


def generate() -> None:
    with open(LATEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    collected_at = data["collected_at"]
    since = data["since"]
    github_items = data["github"][:TOP_GITHUB]
    hf_items = data["huggingface"][:TOP_HF]
    arxiv_items = data["arxiv"][:TOP_ARXIV]

    lines: list[str] = []

    # ── Header ────────────────────────────────────────────────────────────────
    lines.append("# 🤖 Trending AI Sync\n")
    lines.append(
        "> 최근 7일간 생성된 AI 프로젝트를 **매일 09:00 KST** 자동으로 수집하고 "
        "**Claude**가 한국어로 요약합니다.\n"
    )
    lines.append(
        f"**수집일:** `{collected_at}` &nbsp;|&nbsp; "
        f"**수집 기준:** `{since}` 이후\n"
    )

    # ── Stats table ───────────────────────────────────────────────────────────
    lines.append("| 소스 | 수집 건수 | 기준 |")
    lines.append("|:---:|:---:|:---|")
    lines.append(f"| 🐙 GitHub | **{len(github_items)}** | ⭐ 10+ stars |")
    lines.append(f"| 🤗 HuggingFace | **{len(hf_items)}** | ❤️ 5+ likes |")
    lines.append(f"| 📄 arXiv | **{len(arxiv_items)}** | cs.AI / cs.LG / cs.CL / cs.CV |")
    lines.append("")

    # ── TOC ───────────────────────────────────────────────────────────────────
    lines.append("## 📌 목차\n")
    lines.append(f"- [🐙 GitHub Trending ({len(github_items)})](#-github-trending)")
    lines.append(f"- [🤗 HuggingFace Trending ({len(hf_items)})](#-huggingface-trending)")
    lines.append(f"- [📄 arXiv Papers ({len(arxiv_items)})](#-arxiv-papers)")
    lines.append("")

    # ── GitHub ────────────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 🐙 GitHub Trending\n")
    lines.append("> ⭐ **10+ stars** · 최근 7일 생성 · stars 내림차순\n")
    for i, repo in enumerate(github_items, 1):
        lines.append(github_card(repo, i))

    # ── HuggingFace ───────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 🤗 HuggingFace Trending\n")
    lines.append("> ❤️ **5+ likes** · 최근 7일 등록 · likes 내림차순\n")
    for i, model in enumerate(hf_items, 1):
        lines.append(hf_card(model, i))

    # ── arXiv ─────────────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append("## 📄 arXiv Papers\n")
    lines.append("> cs.AI · cs.LG · cs.CL · cs.CV · 최근 7일 게재 · 날짜 내림차순\n")
    for i, paper in enumerate(arxiv_items, 1):
        lines.append(arxiv_card(paper, i))

    # ── Footer ────────────────────────────────────────────────────────────────
    lines.append("---\n")
    lines.append(
        "*🤖 자동 생성 — [trending-ai-sync](.) &nbsp;|&nbsp; "
        "Claude `claude-opus-4-6`로 요약*"
    )

    with open("README.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(
        f"README.md 생성 완료: "
        f"GitHub {len(github_items)} + HF {len(hf_items)} + arXiv {len(arxiv_items)}"
    )


if __name__ == "__main__":
    generate()
