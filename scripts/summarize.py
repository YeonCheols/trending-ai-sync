"""
OpenAI API를 이용해 수집된 항목을 한국어로 요약합니다.
- 모델: gpt-4o
- 대상: GitHub 30개 / HuggingFace 20개 / arXiv 20개
"""
import json
import time
from openai import OpenAI

client = OpenAI()

DATA_DIR = "data"
LATEST_PATH = f"{DATA_DIR}/latest.json"

MAX_GITHUB = 30
MAX_HF = 20
MAX_ARXIV = 20

PROMPTS = {
    "github": (
        "아래 GitHub 저장소를 한국어로 2문장 이내로 간결하게 요약해줘. "
        "핵심 기능과 활용 분야 중심으로 작성해.\n\n{text}"
    ),
    "huggingface": (
        "아래 HuggingFace 모델을 한국어로 2문장 이내로 간결하게 요약해줘. "
        "모델 유형과 주요 용도 중심으로 작성해.\n\n{text}"
    ),
    "arxiv": (
        "아래 arXiv 논문을 한국어로 2문장 이내로 간결하게 요약해줘. "
        "연구 목표와 핵심 기여 중심으로 작성해.\n\n{text}"
    ),
}


def summarize(text: str, source: str) -> str:
    prompt = PROMPTS[source].format(text=text)
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"    ⚠ Summarize error: {e}")
    return ""


def build_text(item: dict, source: str) -> str:
    if source == "github":
        return (
            f"이름: {item['title']}\n"
            f"설명: {item['description']}\n"
            f"토픽: {', '.join(item.get('topics', []))}"
        )
    if source == "huggingface":
        return (
            f"모델: {item['title']}\n"
            f"설명: {item['description'][:300]}\n"
            f"파이프라인: {item.get('pipeline_tag', '')}\n"
            f"태그: {', '.join(item.get('tags', []))}"
        )
    # arxiv
    return (
        f"제목: {item['title']}\n"
        f"초록: {item['abstract'][:500]}"
    )


def run() -> None:
    with open(LATEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    targets = {
        "github": data["github"][:MAX_GITHUB],
        "huggingface": data["huggingface"][:MAX_HF],
        "arxiv": data["arxiv"][:MAX_ARXIV],
    }
    total = sum(len(v) for v in targets.values())
    done = 0

    print(f"Summarizing {total} items with gpt-4o...\n")

    for source, items in targets.items():
        for item in items:
            done += 1
            label = item.get("title", item.get("id", ""))[:60]
            print(f"  [{done}/{total}] {source.upper()}: {label}")
            item["summary"] = summarize(build_text(item, source), source)
            time.sleep(0.3)  # API rate limit 대응

    # 요약된 항목으로 latest.json 업데이트
    data["github"] = targets["github"] + data["github"][MAX_GITHUB:]
    data["huggingface"] = targets["huggingface"] + data["huggingface"][MAX_HF:]
    data["arxiv"] = targets["arxiv"] + data["arxiv"][MAX_ARXIV:]

    with open(LATEST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\nSummaries written to {LATEST_PATH}")


if __name__ == "__main__":
    run()
