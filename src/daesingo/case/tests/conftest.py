"""테스트 부트스트랩 — repo root에 아직 pyproject.toml/설치된 패키지가 없으므로,
`src/`를 sys.path에 직접 얹어서 `import daesingo.case...`가 되게 한다.

⚠️ 임시 조치다. 팀이 repo root에 공용 pyproject.toml을 만들면 이 파일은 걷어내고
`pip install -e .` 기반으로 옮겨야 한다(`docs/modules/case/checklists/phase1-completion-checklist.md`
§13 참고 — case 폴더 밖은 이번 라운드에 건드리지 않기로 했다).
"""
import sys
from pathlib import Path

_SRC_DIR = Path(__file__).resolve().parents[3]  # .../src
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

_REPO_ROOT = _SRC_DIR.parent
MOCK_ROOT = _REPO_ROOT / "data" / "mock"
