#!/usr/bin/env bash
# 헤드 학습 1회차(원본) 평가 → 망가뜨린 사본 특징 → 2회차 학습 → 평가. 단계마다 output/pipeline.log에 남긴다.
set -u
R=/d/readout_finetune
GT="/c/Users/tlsdb/Documents/카테캠/readout_gt_2026-09-27"
PY=$R/.venv/Scripts/python.exe
PPY=D:/paddle-env/Scripts/python.exe
LOG=$R/output/pipeline.log
export PYTHONIOENCODING=utf-8
say() { echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }

evaluate() {  # $1 = run name. output/head_ft/best_head.pdparams를 복사해 합치고 내보내고 평가한다
  local run=$1 d=$R/output/$1
  mkdir -p "$d" && cp "$R/output/head_ft/best_head.pdparams" "$d/"
  (cd "$R" && $PY - "$run" <<'EOF' >> "$LOG" 2>&1
import sys, paddle; run = sys.argv[1]; sys.argv = ["x"]; sys.path.insert(0, ".")
import head_ft as H
full = paddle.load(str(H.PRETRAINED)); full.update(paddle.load(f"output/{run}/best_head.pdparams"))
paddle.save(full, f"output/{run}/full.pdparams")
m = H.model(); m.set_state_dict(full)
for s in ("val_g", "val_g_low", "test_aihub"):
    try: x, y = H.load(s); print(f"{run} {s} line acc {H.accuracy(m, x, y)[0]:.4f}", flush=True)
    except FileNotFoundError: pass
EOF
  )
  (cd "$R/PaddleOCR" && $PY tools/export_model.py -c ../korean_plate_rec.yml \
      -o Global.pretrained_model=../output/$run/full Global.save_inference_dir=../export/$run 2>&1 | grep -E "saved|Error" >> "$LOG")
  (cd "$GT" && TRACKS=tracks_verified.json REC_MODEL_DIR=D:/readout_finetune/export/$run \
      $PPY ocr_eval2.py gt_plates.json picks_all.json C:/Users/tlsdb/Downloads paddle_$run.json > run_paddle_$run.log 2>&1)
  (cd "$GT" && TRACKS=tracks_verified.json REC_MODEL_DIR=D:/readout_finetune/export/$run \
      $PPY hangul_probe.py gt_plates.json picks_all.json C:/Users/tlsdb/Downloads hangul_probe_$run.json > run_probe_$run.log 2>&1)
  say "$run evaluated"
}

say "waiting for run 1 training"
until grep -q "^best\|Traceback" $R/output/head_train_g.log; do sleep 60; done
grep -E "^epoch|^best" $R/output/head_train_g.log >> "$LOG"
evaluate g_run1

say "extract_aug start"
(cd $R && $PY head_ft.py extract_aug > output/extract_aug.log 2>&1)
grep -E "features|Traceback" $R/output/extract_aug.log >> "$LOG"
(cd $R && $PY head_ft.py resplit 2>&1 | grep -E "^train_g|Traceback|Error" >> "$LOG")

say "run 2 training start"
(cd $R && $PY head_ft.py train 8 > output/head_train_low.log 2>&1)
grep -E "^train|^epoch|^best|Traceback" $R/output/head_train_low.log >> "$LOG"
evaluate g_run2_low
say "pipeline done"
