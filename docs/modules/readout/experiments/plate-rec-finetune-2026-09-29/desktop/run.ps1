# 데이터 준비 → 전체 미세조정 → 추론 모델 내보내기. setup.ps1을 먼저 한 번 실행한다.
#   powershell -ExecutionPolicy Bypass -File run.ps1
# 단계마다 output\ 아래에 로그가 남는다. 중간에 멈췄으면 다시 실행 — 이미 만든 데이터는 건너뛴다.
param([int]$Epochs = 20, [int]$BatchSize = 32)
$ErrorActionPreference = "Continue"  # Paddle이 stderr에 안내문을 써서 PS 5.1이 "Stop"이면 멈춘다
$B = $PSScriptRoot
$V = "$B\.venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"
New-Item -ItemType Directory -Force "$B\output" | Out-Null

$ver = if (Test-Path "$B\data\PREP_VERSION") { (Get-Content "$B\data\PREP_VERSION" -Raw).Trim() } else { "" }
if ($ver -ne "detline-v2") {
    if (Test-Path "$B\data") { Remove-Item -Recurse -Force "$B\data" }   # 예전(여백 crop) 데이터는 다시 만든다
    Write-Host "== 1/3 데이터 준비 (번호판 재검출 · 판독 경로 줄 · 2줄 분할 · 번호판 단위 분할)"
    & $V "$B\prep_desktop.py" 2>&1 | Tee-Object "$B\output\prep.log"
} else { Write-Host "== 1/3 데이터 있음 — 건너뜀" }
if (-not (Test-Path "$B\data\PREP_VERSION")) { throw "데이터 준비 실패 — output\prep.log 끝부분의 Traceback을 확인" }

Write-Host "== 2/3 학습 ($Epochs epoch, batch $BatchSize)"
# 예전 학습 결과가 남아 있으면 학습이 실패해도 그걸 내보낸다 — 지우고 시작한다
foreach ($d in "$B\output\full_ft", "$B\export\full_ft") { if (Test-Path $d) { Remove-Item -Recurse -Force $d } }
Set-Location "$B\PaddleOCR"
& $V tools/train.py -c "$B\korean_plate_rec_gpu.yml" -o "Global.epoch_num=$Epochs" "Train.sampler.first_bs=$BatchSize" "Train.loader.batch_size_per_card=$BatchSize" 2>&1 |
    Tee-Object "$B\output\train.log"
if (-not (Test-Path "$B\output\full_ft\best_accuracy.pdparams")) { Set-Location $B; throw "학습 실패 — output\train.log 끝부분의 Traceback을 확인" }

Write-Host "== 3/3 내보내기 (val 최고 가중치)"
& $V tools/export_model.py -c "$B\korean_plate_rec_gpu.yml" -o "Global.pretrained_model=$B\output\full_ft\best_accuracy" "Global.save_inference_dir=$B\export\full_ft" 2>&1 |
    Tee-Object "$B\output\export.log"
if (-not (Test-Path "$B\export\full_ft\inference.pdiparams")) { Set-Location $B; throw "내보내기 실패 — output\export.log 확인" }
Set-Location $B
Select-String -Path "$B\output\train.log" -Pattern "best metric" | Select-Object -Last 1
Write-Host "`n끝. 노트북으로 가져갈 것: $B\export\full_ft  (inference.json · inference.pdiparams · inference.yml)  +  output\train.log"
