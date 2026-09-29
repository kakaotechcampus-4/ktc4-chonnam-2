# 번들 폴더에 가상환경을 만들고 GPU 학습에 필요한 패키지를 설치한다. 한 번만 실행한다.
#   powershell -ExecutionPolicy Bypass -File setup.ps1
# RTX 50 시리즈(Blackwell)는 CUDA 12.8 이상 빌드만 돈다 — 기본값 cu129. 드라이버가 CUDA 13.1이라 맞는다.
param([string]$Cuda = "cu129", [string]$PaddleVersion = "3.3.1")
$ErrorActionPreference = "Continue"  # pip·paddle이 stderr에 안내문을 쓴다 — PS 5.1이 "Stop"이면 멈춘다
$B = $PSScriptRoot
Set-Location $B

$py = (Get-Command py -ErrorAction SilentlyContinue)
if ($py) { & py -3.12 -m venv .venv } else { & python -m venv .venv }
if (-not (Test-Path "$B\.venv\Scripts\python.exe")) { throw "Python 3.12 가상환경을 만들지 못했다 — Python 3.12를 설치한 뒤 다시 실행" }
$V = "$B\.venv\Scripts\python.exe"
& $V -c "import sys; assert sys.version_info[:2] == (3, 12), sys.version; print(sys.version)"

# scipy·paddle DLL은 Visual C++ 재배포 패키지가 있어야 뜬다 (없으면 `DLL load failed while importing _hausdorff`)
winget install -e --id Microsoft.VCRedist.2015+.x64 --accept-package-agreements --accept-source-agreements
& $V -m pip install --upgrade pip
& $V -m pip install "paddlepaddle-gpu==$PaddleVersion" -i "https://www.paddlepaddle.org.cn/packages/stable/$Cuda/"
& $V -m pip install -r "$B\PaddleOCR\requirements.txt" onnxruntime pyyaml
# 판독 경로 줄(PaddleOCR 검출기가 자르는 줄)을 만드는 데 쓴다 — 노트북 판독 경로와 같은 버전
& $V -m pip install "paddleocr==3.7.0"
# paddlex는 numpy<2.4를 요구하고, pandas 3.x는 이 환경에서 `DLL load failed while importing join`으로 죽었다 — 노트북과 같게 고정
& $V -m pip install "numpy==2.3.5" "pandas<3"

Write-Host "`n== GPU 확인 =="
& $V -c "import paddle; print('paddle', paddle.__version__, 'cuda', paddle.version.cuda(), 'gpus', paddle.device.cuda.device_count()); paddle.utils.run_check()"
