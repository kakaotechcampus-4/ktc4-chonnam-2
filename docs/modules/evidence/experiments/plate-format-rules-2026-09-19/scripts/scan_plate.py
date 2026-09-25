# -*- coding: utf-8 -*-
import json, os, sys, re, collections, unicodedata

ROOT = r"D:\자동차 차종-연식-번호판 인식용 영상"
DIRS = [
    ("train", os.path.join(ROOT, "Training", "extracted", "라벨_번호판OCR")),
    ("valid", os.path.join(ROOT, "Validation", "extracted", "라벨_번호판OCR")),
]

vals = collections.Counter()      # (split, value) -> n  ; use nested
per_split = {"train": collections.Counter(), "valid": collections.Counter()}
bad = []

for split, d in DIRS:
    n = 0
    for fn in os.listdir(d):
        if not fn.endswith(".json"):
            continue
        p = os.path.join(d, fn)
        try:
            with open(p, "r", encoding="utf-8") as f:
                j = json.load(f)
        except Exception as e:
            bad.append((p, repr(e)))
            continue
        v = j.get("value")
        if v is None:
            bad.append((p, "no value"))
            continue
        v = unicodedata.normalize("NFC", v)
        per_split[split][v] += 1
        n += 1
    print(split, "files", n, file=sys.stderr)

allc = collections.Counter()
for s in per_split.values():
    allc.update(s)

def shape(v):
    out = []
    for ch in v:
        if ch.isdigit():
            out.append("D")
        elif "\uac00" <= ch <= "\ud7a3":
            out.append("H")
        elif ch == " ":
            out.append("_")
        else:
            out.append("?")
    # compress runs
    res = []
    for c in out:
        if res and res[-1][0] == c:
            res[-1][1] += 1
        else:
            res.append([c, 1])
    return "".join("%s%d" % (c, n) for c, n in res)

shapes = collections.Counter()
shape_ex = {}
shape_split = collections.defaultdict(lambda: collections.Counter())
for v, n in allc.items():
    s = shape(v)
    shapes[s] += n
    shape_ex.setdefault(s, []).append(v)
    for sp in ("train", "valid"):
        if per_split[sp][v]:
            shape_split[s][sp] += per_split[sp][v]

out = {
    "totals": {sp: sum(c.values()) for sp, c in per_split.items()},
    "distinct_values": {sp: len(c) for sp, c in per_split.items()},
    "distinct_all": len(allc),
    "bad": bad[:50],
    "shapes": [
        {
            "shape": s,
            "count": shapes[s],
            "train": shape_split[s]["train"],
            "valid": shape_split[s]["valid"],
            "distinct": len(shape_ex[s]),
            "examples": sorted(shape_ex[s])[:8],
        }
        for s in sorted(shapes, key=lambda k: -shapes[k])
    ],
}
json.dump(out, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "shapes.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
json.dump({v: n for v, n in allc.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "values.json"), "w", encoding="utf-8"), ensure_ascii=False)
json.dump({sp: dict(c) for sp, c in per_split.items()}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "values_split.json"), "w", encoding="utf-8"), ensure_ascii=False)
print(json.dumps(out["shapes"][:40], ensure_ascii=False, indent=1))
print("totals", out["totals"], "distinct", out["distinct_all"])
