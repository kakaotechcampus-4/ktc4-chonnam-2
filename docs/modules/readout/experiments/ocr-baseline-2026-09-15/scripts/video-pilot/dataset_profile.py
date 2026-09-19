import collections
import json
from pathlib import Path

from PIL import Image

ROOT = Path(r"C:\Users\ymshin\Downloads\자동차 차종-연식-번호판 인식용 영상")
out = {"root": str(ROOT), "splits": {}}
all_values = []
for split in ["Training", "Validation"]:
    base = ROOT / split
    labels = next(base.glob("[[]라벨[]]*"))
    images = next(base.glob("[[]원천[]]*"))
    jsons = sorted(labels.glob("*.json"))
    jpgs = sorted(images.glob("*.jpg"))
    values = []
    ids = []
    missing_images = 0
    bad = 0
    for p in jsons:
        try:
            row = json.loads(p.read_text(encoding="utf-8"))
            values.append(row.get("value"))
            ids.append(row.get("id"))
            if not (images / row.get("imagePath", "")).exists():
                missing_images += 1
        except Exception:
            bad += 1
    sizes = collections.Counter()
    for p in jpgs[::max(1, len(jpgs)//1000)]:
        with Image.open(p) as im:
            sizes[im.size] += 1
    out["splits"][split] = {
        "json_count": len(jsons), "jpg_count": len(jpgs), "bad_json": bad,
        "missing_image_refs": missing_images, "unique_values": len(set(values)),
        "duplicate_value_rows": len(values)-len(set(values)), "unique_ids": len(set(ids)),
        "value_length_counts": dict(collections.Counter(map(len, filter(None, values)))),
        "sampled_image_sizes": {f"{w}x{h}": n for (w,h),n in sizes.most_common(20)},
        "examples": values[:10],
    }
    all_values.extend(values)
out["cross_split_overlap_values"] = len(set(all_values[:out['splits']['Training']['json_count']]) & set(all_values[out['splits']['Training']['json_count']:]))
Path("dataset-profile.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(out, ensure_ascii=False, indent=2))
