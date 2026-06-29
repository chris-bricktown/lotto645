#!/usr/bin/env python3
"""로또 6/45 당첨번호를 읽어와 lotto_data.json 을 갱신한다.

데이터 형식: [[회차, 번호1, 번호2, 번호3, 번호4, 번호5, 번호6, 보너스, "날짜"], ...]
  날짜는 추첨일 "YYYY-MM-DD".

데이터 출처: smok95/lotto (GitHub Pages 정적 JSON, CDN 제공)
  https://smok95.github.io/lotto/results/{회차}.json

dhlottery 공식 API 는 해외/클라우드 IP 를 차단(타임아웃)해 GitHub Actions
러너에서 동작하지 않으므로, 전 세계 어디서든 접근 가능한 위 GitHub Pages
정적 JSON 을 사용한다.

응답(JSON) 예시:
  {"draw_no":1230,"numbers":[3,8,9,22,28,42],"bonus_no":45,
   "date":"2026-06-27T00:00:00Z", ...}

아직 추첨하지 않은 회차는 404(Not Found)를 반환하므로,
파일에 있는 마지막 회차 다음부터 404 가 나올 때까지 이어서 가져온다.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API_URL = "https://smok95.github.io/lotto/results/{no}.json"
DATA_FILE = Path(__file__).resolve().parent / "lotto_data.json"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, */*; q=0.01",
}

# 안전장치: 한 번 실행에서 가져올 최대 회차 수
MAX_FETCH = 20


def fetch_draw(no, retries=3):
    """회차 번호로 결과 JSON 을 가져와 dict 로 반환. 미추첨(404)이면 None."""
    url = API_URL.format(no=no)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            return json.loads(raw)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # 아직 추첨하지 않은 회차 → 더 가져올 데이터 없음
                return None
            last_err = e
            time.sleep(2 * (attempt + 1))
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{no}회 조회 실패: {last_err}")


def draw_to_row(data):
    """결과 JSON dict 를 [회차, n1..n6, 보너스, "날짜"] 리스트로 변환."""
    numbers = sorted(data["numbers"])
    if len(numbers) != 6:
        raise ValueError(f"{data.get('draw_no')}회 번호 개수 이상: {numbers}")
    date = (data.get("date") or "")[:10]   # "YYYY-MM-DD"
    return [data["draw_no"], *numbers, data["bonus_no"], date]


def load_data():
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def dump_data(rows):
    """index.html 이 기대하는, 한 줄에 한 회차씩인 읽기 쉬운 형식으로 저장.

    날짜 문자열이 포함되므로 각 행을 json.dumps 로 직렬화한다.
    """
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    DATA_FILE.write_text("[" + ", \n".join(lines) + "]\n", encoding="utf-8")


def validate_contiguous(rows):
    """회차가 1회부터 빠짐없이 연속이고, 배열 위치(index+1)와 일치하는지 검증.

    index.html 이 '첫 번째 = 1회차'를 전제로 하므로, 이 규칙이 깨지면
    데이터가 잘못된 것이라 예외를 던져 워크플로를 실패시킨다.
    (예: 1230회가 1229로 잘못 기록되는 사고 방지)
    """
    for i, row in enumerate(rows):
        expected = i + 1
        if row[0] != expected:
            raise ValueError(
                f"회차 불일치: 위치 {i}(={expected}회 이어야 함)에 {row[0]}회가 있음. "
                f"데이터가 연속적이지 않습니다."
            )


def main():
    rows = load_data()
    # 시작 전, 기존 데이터가 1회부터 연속인지 먼저 확인한다.
    validate_contiguous(rows)
    last_no = rows[-1][0]
    print(f"현재 마지막 회차: {last_no}회 (총 {len(rows)}회차)")

    added = []
    for no in range(last_no + 1, last_no + 1 + MAX_FETCH):
        data = fetch_draw(no)
        if data is None:
            print(f"{no}회는 아직 추첨 전입니다. 종료.")
            break
        # 응답의 draw_no 가 요청한 회차와 일치하는지 확인한다.
        if data.get("draw_no") != no:
            raise ValueError(
                f"응답 회차 불일치: {no}회를 요청했으나 {data.get('draw_no')}회 응답."
            )
        row = draw_to_row(data)
        rows.append(row)
        added.append(row)
        date = (data.get("date") or "?")[:10]
        print(f"추가: {no}회 ({date}) -> {row[1:7]} + 보너스 {row[7]}")
        time.sleep(0.5)

    if not added:
        print("새로 추가할 회차가 없습니다.")
        return 0

    # 저장 전, 최종 데이터도 다시 연속성 검증 (불일치 시 저장하지 않고 실패).
    validate_contiguous(rows)
    dump_data(rows)
    print(f"완료: {len(added)}개 회차 추가, 총 {len(rows)}회차.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
