#!/usr/bin/env python3
"""동행복권(dhlottery) 공식 API에서 최신 로또 6/45 당첨번호를 읽어와
lotto_data.json 을 갱신한다.

데이터 형식: [[회차, 번호1, 번호2, 번호3, 번호4, 번호5, 번호6, 보너스], ...]

공식 API:
  https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={회차}

응답(JSON) 예시:
  {"returnValue":"success","drwNoDate":"2026-06-27","drwNo":1230,
   "drwtNo1":3,"drwtNo2":8,"drwtNo3":9,"drwtNo4":22,"drwtNo5":28,
   "drwtNo6":42,"bnusNo":45, ...}

아직 추첨하지 않은 회차는 {"returnValue":"fail"} 를 반환하므로,
파일에 있는 마지막 회차 다음부터 fail 이 나올 때까지 이어서 가져온다.
"""

import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={no}"
DATA_FILE = Path(__file__).resolve().parent / "lotto_data.json"

# 일부 환경(클라우드/해외 IP)에서는 dhlottery 가 봇 요청을 차단하므로
# 일반 브라우저처럼 보이는 헤더를 사용한다.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "ko-KR,ko;q=0.9",
    "Referer": "https://www.dhlottery.co.kr/gameResult.do?method=byWin",
}

# 안전장치: 한 번 실행에서 가져올 최대 회차 수
MAX_FETCH = 20


def fetch_draw(no, retries=3):
    """회차 번호로 공식 API 를 호출해 dict 를 반환. 미추첨이면 None."""
    url = API_URL.format(no=no)
    last_err = None
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            if data.get("returnValue") != "success":
                return None
            return data
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError) as e:
            last_err = e
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"{no}회 조회 실패: {last_err}")


def draw_to_row(data):
    """API 응답 dict 를 [회차, n1..n6, 보너스] 리스트로 변환."""
    return [
        data["drwNo"],
        data["drwtNo1"], data["drwtNo2"], data["drwtNo3"],
        data["drwtNo4"], data["drwtNo5"], data["drwtNo6"],
        data["bnusNo"],
    ]


def load_data():
    with DATA_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def dump_data(rows):
    """index.html 이 기대하는, 한 줄에 한 회차씩인 읽기 쉬운 형식으로 저장."""
    lines = ["[" + ", ".join(str(v) for v in row) + "]" for row in rows]
    DATA_FILE.write_text("[" + ", \n".join(lines) + "]\n", encoding="utf-8")


def main():
    rows = load_data()
    by_no = {row[0]: row for row in rows}
    last_no = max(by_no)
    print(f"현재 마지막 회차: {last_no}회")

    added = []
    for no in range(last_no + 1, last_no + 1 + MAX_FETCH):
        data = fetch_draw(no)
        if data is None:
            print(f"{no}회는 아직 추첨 전입니다. 종료.")
            break
        row = draw_to_row(data)
        by_no[row[0]] = row
        added.append(row)
        date = data.get("drwNoDate", "?")
        print(f"추가: {no}회 ({date}) -> {row[1:7]} + 보너스 {row[7]}")
        time.sleep(0.5)

    if not added:
        print("새로 추가할 회차가 없습니다.")
        return 0

    rows = [by_no[n] for n in sorted(by_no)]
    dump_data(rows)
    print(f"완료: {len(added)}개 회차 추가, 총 {len(rows)}회차.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
