"""ocr_eval2 결과에 번호 형식 검사(plate_rule.py)를 걸기 전과 후를 나란히 센다.

    python rule_compare.py <paddle_*.json> [...]

MIN_USED=3이면 검증 프레임이 그보다 적은 확정도 보류로 센다(전·후 공통).
후: 확정했지만 형식에 어긋나면 보류로 돌린다. 정답/오답은 확정된 것만 센다.
"""
import json
import os
import sys

from plate_rule import valid

MIN_USED = int(os.environ.get("MIN_USED", "0"))


def score(rows, m, rule):
    ok = wa = ab = 0
    for r in rows:
        x = r[m]
        acc = x["accepted"] and r["used"] >= MIN_USED and (not rule or valid(x["text"]))
        if not acc:
            ab += 1
        elif r["kind"] == "full" and x["correct"]:
            ok += 1
        wa += acc and bool(x["wrong_accept"])
    return ok, wa, ab


for f in sys.argv[1:]:
    rows = json.load(open(f, encoding="utf-8"))
    full = sum(r["kind"] == "full" for r in rows)
    methods = [m for m in rows[0] if isinstance(rows[0][m], dict) and "accepted" in rows[0][m]]
    print(f"\n{f}  items={len(rows)} full={full}")
    print("| 방법 | 전: 맞음 / 확정 오답 / 보류 | 후: 맞음 / 확정 오답 / 보류 |")
    for m in methods:
        b, a = score(rows, m, False), score(rows, m, True)
        print(f"| {m} | {b[0]}/{full} · {b[1]} · {b[2]} | {a[0]}/{full} · {a[1]} · {a[2]} |")
