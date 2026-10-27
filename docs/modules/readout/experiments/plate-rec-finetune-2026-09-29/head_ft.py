"""backbone을 고정하고 neck + CTC 헤드만 미세조정한다 (이 노트북 CPU용 — 학습형 backbone forward가 8장에 10초라서).

    python head_ft.py extract            # 줄 이미지 → backbone 특징(float16) 저장, 사전학습 헤드로 정확도 재확인
    python head_ft.py extract_aug        # train·val 줄 이미지를 블랙박스 수준으로 망가뜨린 사본 특징(_low)
    python head_ft.py resplit            # train+val을 번호판 단위로 다시 나눔(test_aihub 번호 제외) → train_g · val_g
    python head_ft.py train [epochs]     # train_g로 neck + CTC 헤드 학습, val_g 최고 가중치 저장
    python head_ft.py merge              # 사전학습 전체 가중치에 학습한 헤드를 덮어써 output/head_ft/best_full.pdparams

전처리는 eval과 같다(`RecResizeImg [3, 48, 320]`). backbone은 eval 모드(BN 고정) — 특징이 제품 추론과 같다.
"""
import json
import sys
import time
from pathlib import Path

import numpy as np
import paddle
import yaml

ROOT = Path(r"D:\readout_finetune")
sys.path.insert(0, str(ROOT / "PaddleOCR"))
from ppocr.data.imaug import create_operators, transform  # noqa: E402
from ppocr.modeling.architectures import build_model  # noqa: E402

CFG = yaml.safe_load(open(ROOT / "korean_plate_rec.yml", encoding="utf-8"))
DICT = [l.rstrip("\n") for l in open(ROOT / "PaddleOCR" / CFG["Global"]["character_dict_path"], encoding="utf-8")]
CHARS = ["blank"] + DICT + [" "]          # CTCLabelDecode와 같은 순서
IDX = {c: i for i, c in enumerate(CHARS)}
FEAT = ROOT / "features"
OUT = ROOT / "output" / "head_ft"
PRETRAINED = ROOT / "pretrained" / "korean_PP-OCRv5_mobile_rec_pretrained.pdparams"
SPLITS = ("train", "val", "test_aihub")
HEAD_PREFIXES = ("head.ctc_encoder.", "head.ctc_head.")


def model():
    a = json.loads(json.dumps(CFG["Architecture"]))
    a["Head"]["out_channels_list"] = {"CTCLabelDecode": len(CHARS), "NRTRLabelDecode": len(CHARS) + 1}
    m = build_model(a)
    missing = m.set_state_dict(paddle.load(str(PRETRAINED)))
    return m


def greedy(logits):
    out = []
    for row in logits.argmax(-1):
        s, prev = [], 0
        for i in row:
            if i != prev and i != 0:
                s.append(CHARS[i])
            prev = i
        out.append("".join(s))
    return out


def ctc_forward(m, feats):
    return m.head.ctc_head(m.head.ctc_encoder(feats))


def accuracy(m, feats, labels, bs=256):
    m.eval()
    preds = []
    with paddle.no_grad():
        for i in range(0, len(feats), bs):
            logits = ctc_forward(m, paddle.to_tensor(feats[i:i + bs].astype("float32")))
            preds += greedy(logits.numpy())
    return sum(p == l for p, l in zip(preds, labels)) / len(labels), preds


def degrade(img, seed, two_line_part):
    """블랙박스 수준으로 망가뜨린다 — 번호판 높이 20~36px(2줄 한 줄이면 절반)로 줄였다 키우고, 흐림 · JPEG.
    블랙박스 GT에서 `수`의 ㅅ 삐침이 1~2px로 뭉개져 `주`로 읽혔다. AI Hub crop은 너무 선명하다."""
    import cv2
    rng = np.random.default_rng(seed)
    h, w = img.shape[:2]
    target = rng.uniform(20, 36) * (0.5 if two_line_part else 1.0)
    if h > target:
        s = target / h
        small = cv2.resize(img, (max(8, round(w * s)), max(6, round(h * s))), interpolation=cv2.INTER_AREA)
        img = cv2.resize(small, (w, h), interpolation=cv2.INTER_CUBIC)
    img = cv2.GaussianBlur(img, (0, 0), rng.uniform(0.6, 1.2))
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, int(rng.integers(30, 71))])
    return buf.tobytes()


def extract(aug=False):
    import cv2
    ops = create_operators([{"DecodeImage": {"img_mode": "BGR", "channel_first": False}},
                            {"RecResizeImg": {"image_shape": [3, 48, 320]}},
                            {"KeepKeys": {"keep_keys": ["image"]}}])
    m = model()
    m.eval()
    # 가지를 합친 추론 형태 — 사전학습 가중치로 특징 상대 오차 3.5e-5, 해독 16/16 같음, 2.6배 빠르다
    for layer in m.backbone.sublayers():
        if hasattr(layer, "rep") and callable(layer.rep):
            layer.rep()
    FEAT.mkdir(exist_ok=True)
    suffix = "_low" if aug else ""
    for split in (("train", "val") if aug else SPLITS):
        lines = [l.rstrip("\n").split("\t") for l in open(ROOT / "data" / f"{split}_list.txt", encoding="utf-8") if l.strip()]
        two = {Path(r).stem.rsplit("_", 1)[0] for r, _ in lines if Path(r).stem.endswith("_1")}
        feats, labels, t = [], [], time.time()
        for i in range(0, len(lines), 64):
            batch = []
            for n, (rel, label) in enumerate(lines[i:i + 64], start=i):
                with open(ROOT / "data" / rel, "rb") as f:
                    raw = f.read()
                if aug:
                    img = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
                    raw = degrade(img, 20260929 + n, Path(rel).stem.rsplit("_", 1)[0] in two)
                batch.append(transform({"image": raw}, ops)[0])
                labels.append(label)
            with paddle.no_grad():
                feats.append(m.backbone(paddle.to_tensor(np.stack(batch))).numpy().astype("float16"))
            print(f"{split} {min(i + 64, len(lines))}/{len(lines)} {time.time() - t:.0f}s", flush=True)
        feats = np.concatenate(feats)
        np.save(FEAT / f"{split}{suffix}.npy", feats)
        (FEAT / f"{split}{suffix}_labels.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
        acc, _ = accuracy(m, feats, labels)
        print(f"{split}: features {feats.shape}, pretrained head line acc {acc:.4f}", flush=True)


def load(split):
    return np.load(FEAT / f"{split}.npy"), json.loads((FEAT / f"{split}_labels.json").read_text(encoding="utf-8"))


def plate_of():
    """줄 이미지 id → 번호판 전체 번호(AI Hub value). 같은 차는 여러 장 찍혀 있다 — Validation 이미지의 37%가 번호 중복."""
    import re
    import zipfile
    src = Path(r"C:\Users\tlsdb\Downloads\자동차 차종-연식-번호판 인식용 영상\Validation\[라벨]자동차번호판OCR_valid.zip")
    with zipfile.ZipFile(src) as z:
        return {o["id"]: re.sub(r"\s+", "", o["value"])
                for o in (json.loads(z.read(n).decode("utf-8")) for n in z.namelist() if n.endswith(".json"))}


def resplit(val_share=0.05):
    """train+val을 **번호판 단위로** 다시 나눈다. test_aihub에 있는 번호는 train·val에서 뺀다 → train_g · val_g."""
    plate = plate_of()

    def rows(split, suffix=""):
        rels = [l.split("\t")[0] for l in open(ROOT / "data" / f"{split}_list.txt", encoding="utf-8") if l.strip()]
        x, y = load(split + suffix)
        return [plate[Path(r).stem.rsplit("_", 1)[0]] for r in rels], x, y

    tp, _, _ = rows("test_aihub")
    ap, ax, ay = [], [], []
    for split in ("train", "val"):
        p, x, y = rows(split)
        ap += p; ax.append(x); ay += y
    ax = np.concatenate(ax)
    low = (FEAT / "train_low.npy").exists()
    if low:  # 망가뜨린 사본 — 원본과 같은 순서
        lx = np.concatenate([rows(split, "_low")[1] for split in ("train", "val")])
    test_plates = set(tp)
    plates = sorted(set(ap) - test_plates)
    np.random.default_rng(20260928).shuffle(plates)
    val_plates = set(plates[:round(len(plates) * val_share)])
    idx = {"train_g": [i for i, p in enumerate(ap) if p not in test_plates and p not in val_plates],
           "val_g": [i for i, p in enumerate(ap) if p in val_plates]}
    out = {name: (ax[ii], [ay[i] for i in ii]) for name, ii in idx.items()}
    if low:  # train_g = 원본 + 사본 · val_g는 원본만 · val_g_low = 같은 번호의 사본(뭉개진 번호판 대리 지표)
        out["train_g"] = (np.concatenate([ax[idx["train_g"]], lx[idx["train_g"]]]), [ay[i] for i in idx["train_g"]] * 2)
        out["val_g_low"] = (lx[idx["val_g"]], [ay[i] for i in idx["val_g"]])
    for name, (x, y) in out.items():
        np.save(FEAT / f"{name}.npy", x)
        (FEAT / f"{name}_labels.json").write_text(json.dumps(y, ensure_ascii=False), encoding="utf-8")
    dropped = sum(1 for p in ap if p in test_plates)
    assert not ({ap[i] for i in idx["train_g"]} & ({ap[i] for i in idx["val_g"]} | test_plates))
    print(f"train_g {len(out['train_g'][1])} lines (low copies: {low}) · val_g {len(idx['val_g'])} lines ({len(val_plates)} plates) · "
          f"dropped {dropped} lines whose plate is in test_aihub", flush=True)


def train(epochs=30, bs=64, lr=2e-4, tr="train_g", va="val_g"):
    m = model()
    for name, p in m.named_parameters():
        p.stop_gradient = not name.startswith(HEAD_PREFIXES)
    params = [p for p in m.parameters() if not p.stop_gradient]
    sched = paddle.optimizer.lr.CosineAnnealingDecay(lr, T_max=epochs)
    opt = paddle.optimizer.Adam(sched, parameters=params, weight_decay=paddle.regularizer.L2Decay(3e-5))
    xtr, ytr = load(tr)
    xva, yva = load(va)
    keep = [i for i, y in enumerate(ytr) if all(c in IDX for c in y) and 0 < len(y) <= 25]
    xtr, ytr = xtr[keep], [ytr[i] for i in keep]
    base, _ = accuracy(m, xva, yva)
    print(f"train {len(ytr)} lines · val before {base:.4f}", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    best, rng = base, np.random.default_rng(20260928)
    for ep in range(1, epochs + 1):
        m.train()
        order, total, t = rng.permutation(len(ytr)), 0.0, time.time()
        for i in range(0, len(order), bs):
            idx = order[i:i + bs]
            x = paddle.to_tensor(xtr[idx].astype("float32"))
            lab = [[IDX[c] for c in ytr[j]] for j in idx]
            L = max(len(s) for s in lab)
            labels = paddle.to_tensor(np.array([s + [0] * (L - len(s)) for s in lab], "int32"))
            logits = ctc_forward(m, x)
            # ctc_loss가 softmax를 안에서 한다(PaddleOCR CTCLoss와 같음). log_softmax를 따로 쓰면 이 CPU에서
            # [64, 40, 11947] 한 번에 81초 — 원래도 필요 없다
            loss = paddle.nn.functional.ctc_loss(
                logits.transpose([1, 0, 2]), labels, paddle.full([len(idx)], logits.shape[1], "int64"),
                paddle.to_tensor([len(s) for s in lab], "int64"), blank=0, reduction="mean")
            loss.backward()
            opt.step()
            opt.clear_grad()
            total += float(loss) * len(idx)
        sched.step()
        acc, _ = accuracy(m, xva, yva)
        mark = ""
        if acc > best:
            best, mark = acc, " *"
            paddle.save({k: v for k, v in m.state_dict().items() if k.startswith(HEAD_PREFIXES)}, str(OUT / "best_head.pdparams"))
        print(f"epoch {ep} loss {total / len(ytr):.3f} val {acc:.4f}{mark} ({time.time() - t:.0f}s)", flush=True)
    print(f"best val {best:.4f} (before {base:.4f})")


def merge():
    full = paddle.load(str(PRETRAINED))
    head = paddle.load(str(OUT / "best_head.pdparams"))
    full.update(head)
    paddle.save(full, str(OUT / "best_full.pdparams"))
    m = model()
    m.set_state_dict(full)
    for split in SPLITS[1:]:
        x, y = load(split)
        print(f"{split}: merged line acc {accuracy(m, x, y)[0]:.4f}")


if __name__ == "__main__":
    {"extract": extract, "extract_aug": lambda: extract(aug=True), "resplit": resplit, "train": lambda: train(int(sys.argv[2]) if len(sys.argv) > 2 else 30), "merge": merge}[sys.argv[1]]()
