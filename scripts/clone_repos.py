"""
상위 5개 GitHub 레포를 clone하고 OpenAI 분석 파일을 추가해서
내 GitHub 계정에 새 레포로 push합니다.
"""
import os
import json
import base64
import subprocess
import tempfile
import time
import requests
from openai import OpenAI

GH_TOKEN = os.environ.get("GH_TOKEN", "")
HEADERS_GH = {
    "Authorization": f"Bearer {GH_TOKEN}",
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}

openai_client = OpenAI()

DATA_DIR = "data"
LATEST_PATH = f"{DATA_DIR}/latest.json"
FORKED_PATH = f"{DATA_DIR}/forked.json"

TOP_N = 5


# ── GitHub 유틸 ───────────────────────────────────────────────────────────────

def get_my_username() -> str:
    r = requests.get("https://api.github.com/user", headers=HEADERS_GH, timeout=10)
    r.raise_for_status()
    return r.json()["login"]


def create_repo(username: str, repo_name: str, description: str) -> bool:
    """내 계정에 새 레포 생성"""
    url = "https://api.github.com/user/repos"
    payload = {
        "name": repo_name,
        "description": f"[AI Sync] {description}"[:255],
        "private": True,
        "auto_init": False,
    }
    r = requests.post(url, headers=HEADERS_GH, json=payload, timeout=10)
    if r.status_code == 201:
        return True
    if r.status_code == 422:
        print(f"    레포 이미 존재: {repo_name}")
        return True
    print(f"    [Create Repo] 실패 {r.status_code}: {r.text[:100]}")
    return False


def repo_exists(username: str, repo_name: str) -> bool:
    r = requests.get(
        f"https://api.github.com/repos/{username}/{repo_name}",
        headers=HEADERS_GH, timeout=10
    )
    return r.status_code == 200


# ── OpenAI 분석 ───────────────────────────────────────────────────────────────

def get_readme_content(owner: str, repo: str) -> str:
    """원본 레포의 README 내용 가져오기"""
    r = requests.get(
        f"https://api.github.com/repos/{owner}/{repo}/readme",
        headers=HEADERS_GH, timeout=10
    )
    if r.status_code == 200:
        content = r.json().get("content", "")
        return base64.b64decode(content).decode("utf-8", errors="ignore")[:3000]
    return ""


def analyze_with_openai(repo_info: dict, readme: str) -> str:
    prompt = f"""다음 GitHub 저장소를 한국어로 상세하게 분석해줘.

## 저장소 정보
- 이름: {repo_info['title']} ({repo_info['id']})
- 설명: {repo_info.get('description', '')}
- Stars: {repo_info.get('stars', 0):,}
- 언어: {repo_info.get('language', 'N/A')}
- 토픽: {', '.join(repo_info.get('topics', []))}

## 원본 README (일부)
{readme[:2000] if readme else '(README 없음)'}

---

아래 마크다운 형식으로 분석 결과를 작성해줘:

# 🤖 AI 분석 리포트 — {repo_info['title']}

> 원본 저장소: [{repo_info['id']}](https://github.com/{repo_info['id']}) ⭐ {repo_info.get('stars', 0):,}

## 📌 프로젝트 개요
(3-4문장으로 핵심 목적과 배경 설명)

## ✨ 주요 기능
(불릿 포인트로 4-6개)

## 🛠 기술 스택
(사용된 기술, 프레임워크, AI 모델 등)

## 💡 활용 시나리오
(어떤 상황에서, 누가 쓸 수 있는지 구체적으로)

## 🔍 주목할 점
(이 프로젝트가 특별한 이유, 기여할 수 있는 부분)

## ⚡ 빠른 시작
(설치 및 실행 방법 요약, README 기반으로)

---
*🤖 본 분석은 GPT-4o가 자동 생성했습니다. 수집일: {repo_info.get('created_at', '')}*
"""
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.choices[0].message.content.strip()


# ── Git 작업 ──────────────────────────────────────────────────────────────────

def run_cmd(cmd: list[str], cwd: str = None) -> bool:
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"    [CMD] 오류: {' '.join(cmd)}\n    {result.stderr[:200]}")
        return False
    return True


def clone_and_push(repo_info: dict, username: str, analysis: str) -> str | None:
    owner, repo_name = repo_info["id"].split("/")
    target_repo = f"ai-sync-{repo_name}"

    # 1. 내 계정에 새 레포 생성
    if not create_repo(username, target_repo, repo_info.get("description", "")):
        return None

    with tempfile.TemporaryDirectory() as tmpdir:
        clone_url = f"https://{GH_TOKEN}@github.com/{owner}/{repo_name}.git"
        push_url = f"https://{GH_TOKEN}@github.com/{username}/{target_repo}.git"

        print(f"    Cloning {repo_info['id']}...")
        if not run_cmd(["git", "clone", "--depth=1", clone_url, "repo"], cwd=tmpdir):
            return None

        repo_dir = f"{tmpdir}/repo"

        # 2. ANALYSIS.md 파일 추가
        analysis_path = f"{repo_dir}/ANALYSIS.md"
        with open(analysis_path, "w", encoding="utf-8") as f:
            f.write(analysis)

        # 3. git 설정
        run_cmd(["git", "config", "user.name", "github-actions[bot]"], cwd=repo_dir)
        run_cmd(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], cwd=repo_dir)

        # 4. 커밋
        run_cmd(["git", "add", "ANALYSIS.md"], cwd=repo_dir)
        run_cmd(["git", "commit", "-m", "chore: add AI analysis report"], cwd=repo_dir)

        # 5. 현재 브랜치 이름 확인
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=repo_dir, capture_output=True, text=True
        )
        branch = result.stdout.strip() or "main"

        # 6. shallow clone → 전체 히스토리 복원 (빈 레포 push 시 필수)
        print(f"    Unshallowing...")
        run_cmd(["git", "fetch", "--unshallow"], cwd=repo_dir)

        # 7. origin을 내 레포로 교체 후 push
        print(f"    Pushing to {username}/{target_repo} (branch: {branch})...")
        run_cmd(["git", "remote", "remove", "origin"], cwd=repo_dir)
        run_cmd(["git", "remote", "add", "origin", push_url], cwd=repo_dir)

        if not run_cmd(["git", "push", "-u", "origin", f"{branch}:{branch}", "--force"], cwd=repo_dir):
            return None

    return f"https://github.com/{username}/{target_repo}"


# ── 메인 ─────────────────────────────────────────────────────────────────────

def load_forked() -> dict:
    if os.path.exists(FORKED_PATH):
        with open(FORKED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_forked(forked: dict) -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(FORKED_PATH, "w", encoding="utf-8") as f:
        json.dump(forked, f, ensure_ascii=False, indent=2)


def run() -> None:
    with open(LATEST_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    forked = load_forked()
    username = get_my_username()
    print(f"GitHub user: {username}\n")

    # 아직 처리 안 된 상위 레포 TOP_N개 선택
    candidates = [
        r for r in data["github"]
        if r["id"] not in forked
    ][:TOP_N]

    print(f"Processing {len(candidates)} repos...\n")

    for repo_info in candidates:
        print(f"  [{repo_info['id']}] ⭐ {repo_info['stars']:,}")

        # 1. 원본 README 수집
        owner, repo_name = repo_info["id"].split("/")
        readme = get_readme_content(owner, repo_name)

        # 2. OpenAI 분석
        print(f"    Analyzing with GPT-4o...")
        analysis = analyze_with_openai(repo_info, readme)

        # 3. Clone → ANALYSIS.md 추가 → Push
        pushed_url = clone_and_push(repo_info, username, analysis)

        if pushed_url:
            print(f"    ✓ {pushed_url}")
            forked[repo_info["id"]] = {
                "repo_url": pushed_url,
                "synced_at": data["collected_at"],
                "stars": repo_info["stars"],
                "title": repo_info["title"],
            }
            save_forked(forked)
        else:
            print(f"    ✗ 실패: {repo_info['id']}")

        time.sleep(2)

    print(f"\n완료. 누적 처리 레포: {len(forked)}개")


if __name__ == "__main__":
    run()
