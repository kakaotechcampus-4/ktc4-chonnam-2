import json, sys
rows = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8", errors="replace") if l.startswith("{")]
methods = [m for m in rows[0] if isinstance(rows[0][m], dict) and "accepted" in rows[0][m]]
full = [r for r in rows if r["kind"] == "full"]
print(f"items={len(rows)} full={len(full)}")
print("| 방법 | 맞게 읽음 (full) | 틀린 값 확정 (전체) | 보류 |")
for m in methods:
    ok = sum(r[m]["correct"] for r in full)
    wa = sum(bool(r[m]["wrong_accept"]) for r in rows)
    ab = sum(not r[m]["accepted"] for r in rows)
    print(f"| {m} | {ok}/{len(full)} | {wa} | {ab} |")
if len(sys.argv) > 2:
    m = sys.argv[2]
    for r in rows:
        x = r[m]; tag = "OK" if x["correct"] else ("WRONG-ACCEPT" if x["wrong_accept"] else "abstain")
        print(f"  {r['video'][:17]:17} {r['kind']:10} gt={r['gt']}  {m}={x['text'] or '-'}  {tag}")
