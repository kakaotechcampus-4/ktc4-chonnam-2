# Evaluation Harness v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `python -m eval.run --impl <이름표>`와 `python -m eval.score`로 가짜 구현을 채점해 결과 JSON을 내는 오프라인 채점 하니스를 만든다.

**Architecture:** runner와 scorer를 분리한다(v4 §9-2). runner는 impl 출력을 `{meta, raw, normalized}` envelope으로 저장하고, scorer는 `normalized`만 읽는다. 계약이 바뀌어도 scorer와 과거 결과가 살아남고, `raw` 보존 덕에 새 지표를 낼 때 유료 API를 다시 부르지 않는다. runner는 GT를 모르며, 가짜 구현만 GT 파일을 스스로 읽는다.

**Tech Stack:** Python 3.11 · 표준 라이브러리만 · pytest 9.1. 외부 의존성을 추가하지 않는다 — `scripts/check_boundaries.py`가 stdlib만 쓰는 기존 관례를 따르고, 의존성 결정은 실제로 필요해질 때 한다.

**Spec:** `docs/modules/eval/harness-v1-design.md`

**계획 문서 위치:** 기본값 `docs/superpowers/plans/` 대신 스펙과 형제로 두었다. 이 레포는 문서 폴더 규칙을 `docs/README.md`가 소유하며 새 최상위 `docs/` 하위 트리를 임의로 만들지 않는다(CLAUDE.md).

## Global Constraints

- **위반유형 baseline enum은 정확히 4개다** (v4 §3-5): `SIGNAL` · `CENTER_LINE_CROSSING` · `SOLID_LINE_LANE_CHANGE` · `MOTORCYCLE_HELMET_NON_USE`. 다른 이름을 쓰지 않는다.
- **runner는 GT를 impl에 전달하지 않는다.** 가짜 구현만 GT 파일을 직접 읽고, 레지스트리에서 `fake:` 접두어로 격리한다.
- **데이터가 없는 지표는 `0`이 아니라 `null` + 사유 문자열이다.**
- **ref는 파싱하지 않는다.** `input_ref`·자산 ref는 불투명 문자열로 통과시킨다.
- **`eval`은 `case`·`evidence`·`web`을 import하지 않는다** (v4 §6-1). `data/mock/`의 파일을 **읽는 것**은 허용되지만 그쪽 코드를 import하지 않는다.
- **`predictions/`와 `results/`는 커밋한다.** `datasets/`와 `*.private.json`, `events_draft.json`은 커밋하지 않는다.
- 문서·주석은 한국어, 폴더·파일 이름은 영어(레포 관례).

---

## File Structure

| 파일 | 책임 |
| --- | --- |
| `eval/__init__.py` | 패키지 표시. 버전 상수 |
| `eval/paths.py` | 저장소 루트·manifest·prediction·result 경로 해석. 다른 모듈은 경로를 직접 조립하지 않는다 |
| `eval/enums.py` | baseline 위반유형 4종과 `NONE`. 단일 정의처 |
| `eval/manifests_io.py` | manifest·GT 로드와 불변식 검증 |
| `eval/runners/registry.py` | 이름표 → 호출 가능 객체 |
| `eval/runners/normalize.py` | impl 원문 → `normalized` 뷰. Mock Pack 형태 어댑터 포함 |
| `eval/runners/impls/fake_always_correct.py` | GT를 그대로 되돌려주는 치트 |
| `eval/runners/impls/fake_always_wrong.py` | 의도적으로 틀린 답 |
| `eval/run.py` | runner CLI → `predictions/<run_id>.json` |
| `eval/scorers/candidate.py` | Recall@K · span error · FP/clip |
| `eval/scorers/classification.py` | recall_macro · precision_macro · 5×5 confusion · target correctness |
| `eval/scorers/plate.py` | 스키마와 계산 로직. 데이터 없으면 `null` + 사유 |
| `eval/score.py` | scorer CLI → `results/<run_id>.<gt>.json` |
| `eval/tools/sample_aihub.py` | VL.zip 샘플링 → `a_aihub/sequences.json` · `gt/gt_classification.json` |
| `tests/eval/*` | 위 각각의 테스트 |

---

## Task 1: 패키지 골격과 manifest 정리

**Files:**
- Create: `pyproject.toml`
- Create: `eval/__init__.py`, `eval/paths.py`, `eval/enums.py`
- Move: `eval/manifests/set1/` → `eval/manifests/b_youtube/`
- Test: `tests/eval/test_paths.py`

**Interfaces:**
- Consumes: 없음 (첫 태스크)
- Produces:
  - `eval.paths.REPO_ROOT: str`
  - `eval.paths.manifest_dir(name: str) -> str`
  - `eval.paths.predictions_dir() -> str`
  - `eval.paths.results_dir() -> str`
  - `eval.enums.VIOLATION_TYPES: tuple[str, ...]` (4종)
  - `eval.enums.CLASS_LABELS: tuple[str, ...]` (4종 + `"NONE"`)

- [ ] **Step 1: manifest 폴더를 tier 단위 이름으로 옮긴다**

```bash
cd "C:/Users/Daewon/Desktop/개발/카테캠/대신고"
git mv eval/manifests/set1 eval/manifests/b_youtube 2>/dev/null || mv eval/manifests/set1 eval/manifests/b_youtube
ls eval/manifests/
```

`set1`은 아직 커밋되지 않은 상태일 수 있다. `git mv`가 실패하면 일반 `mv`를 쓴다.

- [ ] **Step 2: 실패하는 테스트를 쓴다**

`tests/eval/test_paths.py`:

```python
import os
from eval import paths
from eval import enums


def test_manifest_dir_points_at_b_youtube():
    d = paths.manifest_dir("b_youtube")
    assert os.path.isdir(d)
    assert os.path.isfile(os.path.join(d, "clips.json"))


def test_violation_types_are_the_four_baseline_names():
    assert enums.VIOLATION_TYPES == (
        "SIGNAL",
        "CENTER_LINE_CROSSING",
        "SOLID_LINE_LANE_CHANGE",
        "MOTORCYCLE_HELMET_NON_USE",
    )


def test_class_labels_add_none_for_confusion_matrix():
    assert enums.CLASS_LABELS == enums.VIOLATION_TYPES + ("NONE",)
```

- [ ] **Step 3: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_paths.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval'`

- [ ] **Step 4: 최소 구현을 쓴다**

`pyproject.toml`:

```toml
[project]
name = "daesingo-eval"
version = "0.1.0"
description = "대신고 오프라인 채점 하니스. 제품 런타임이 아니다."
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools.packages.find]
include = ["eval*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`eval/__init__.py`:

```python
"""대신고 오프라인 채점 하니스.

제품 런타임이 아니다. `case`·`evidence`·`web`을 알지 못하며,
`search`/`readout`의 public capability만 호출한다 (module-architecture.md §4-모듈7).
"""

__version__ = "0.1.0"
```

`eval/enums.py`:

```python
"""위반유형 baseline enum.

정답지는 docs/architecture/module-architecture.md §3-5이다.
이 파일은 그 목록의 코드 사본이며, 어긋나면 문서가 이긴다.
"""

VIOLATION_TYPES = (
    "SIGNAL",
    "CENTER_LINE_CROSSING",
    "SOLID_LINE_LANE_CHANGE",
    "MOTORCYCLE_HELMET_NON_USE",
)

# Classification confusion matrix는 4종 + NONE의 5×5다 (v4 §9-3).
CLASS_LABELS = VIOLATION_TYPES + ("NONE",)
```

`eval/paths.py`:

```python
"""경로 해석. 다른 모듈은 경로를 직접 조립하지 않는다."""
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EVAL_ROOT = os.path.join(REPO_ROOT, "eval")


def manifest_dir(name):
    """tier 단위 manifest 폴더. 예: 'b_youtube', 'a_aihub'."""
    return os.path.join(EVAL_ROOT, "manifests", name)


def predictions_dir():
    return os.path.join(EVAL_ROOT, "predictions")


def results_dir():
    return os.path.join(EVAL_ROOT, "results")


def datasets_dir():
    return os.path.join(EVAL_ROOT, "datasets")
```

- [ ] **Step 5: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_paths.py -v`
Expected: 3 passed

- [ ] **Step 6: 커밋한다**

```bash
git add pyproject.toml eval/__init__.py eval/paths.py eval/enums.py tests/eval/test_paths.py eval/manifests/
git commit -m "feat(eval): 패키지 골격과 tier 단위 manifest 배치"
```

---

## Task 2: manifest·GT 로더와 불변식 검증

**Files:**
- Create: `eval/manifests_io.py`
- Test: `tests/eval/test_manifests_io.py`

**Interfaces:**
- Consumes: `eval.paths.manifest_dir`, `eval.enums.VIOLATION_TYPES`
- Produces:
  - `load_clips(manifest_name: str) -> dict` — `{"meta": {...}, "clips": [...]}`
  - `load_gt(manifest_name: str, stage: str) -> dict` — `{"meta": {...}, "items": [...]}`
  - `check_invariants(manifest_name: str, stage: str, verify_hashes: int = 0) -> list[str]` — 위반 메시지 목록. 빈 리스트면 정상

`check_invariants`가 검사하는 것:
1. GT `items` 수 == `meta.coverage.clips_total`
2. targets 있는 item 수 == `meta.coverage.clips_with_events`
3. 모든 `violation_type`이 baseline 4종에 속함
4. 모든 target에 대해 `t_start_sec < t_end_sec`
5. target span이 해당 클립 길이 안에 있음
6. `clips[].file_path`가 실제로 존재함
7. `verify_hashes > 0`이면 그만큼의 클립에 대해 sha256 대조

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_manifests_io.py`:

```python
from eval import manifests_io


def test_load_clips_returns_55_entries():
    data = manifests_io.load_clips("b_youtube")
    assert data["meta"]["tier"] == "B"
    assert len(data["clips"]) == 55


def test_load_gt_candidate_has_coverage_block():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    cov = gt["meta"]["coverage"]
    assert cov["clips_total"] == 55
    assert cov["clips_reviewed"] == 55
    assert cov["negatives_confirmed"] is True


def test_real_b_youtube_data_has_no_invariant_violations():
    problems = manifests_io.check_invariants("b_youtube", "candidate", verify_hashes=3)
    assert problems == [], "위반: " + "; ".join(problems)


def test_bad_violation_type_is_reported(tmp_path, monkeypatch):
    # baseline 밖의 이름이 들어오면 잡아낸다.
    gt = {
        "meta": {"gt_version": "gx", "tier": "B", "stage": "candidate",
                 "coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 1, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0",
                   "targets": [{"event_id": "E0", "violation_type": "LANE_CHANGE",
                                "t_start_sec": 1.0, "t_end_sec": 2.0,
                                "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("LANE_CHANGE" in p for p in problems)


def test_span_outside_clip_is_reported():
    gt = {
        "meta": {"coverage": {"clips_total": 1, "clips_reviewed": 1,
                              "clips_with_events": 1, "negatives_confirmed": True}},
        "items": [{"clip_id": "C0", "source_video_id": "V0",
                   "targets": [{"event_id": "E0", "violation_type": "SIGNAL",
                                "t_start_sec": 55.0, "t_end_sec": 70.0,
                                "t_onset_sec": 60.0, "scoring": "INCLUDED"}]}],
    }
    clips = {"meta": {"tier": "B"},
             "clips": [{"clip_id": "C0", "duration_sec": 60,
                        "file_path": __file__, "sha256": "", "split": "DEV",
                        "source_video_id": "V0"}]}
    problems = manifests_io.validate(clips, gt, verify_hashes=0)
    assert any("클립 길이" in p for p in problems)
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_manifests_io.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.manifests_io'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/manifests_io.py`:

```python
"""manifest·GT 로드와 불변식 검증.

지표 정의는 여기 없다. 이 모듈은 「정답지가 스스로 모순되지 않는가」만 본다.
"""
import hashlib
import json
import os

from eval import paths
from eval.enums import VIOLATION_TYPES


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_clips(manifest_name):
    return _read_json(os.path.join(paths.manifest_dir(manifest_name), "clips.json"))


def load_gt(manifest_name, stage):
    return _read_json(
        os.path.join(paths.manifest_dir(manifest_name), "gt", "gt_%s.json" % stage)
    )


def _sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def validate(clips, gt, verify_hashes=0):
    """위반 메시지 목록을 돌려준다. 빈 리스트면 정상."""
    problems = []
    by_id = {c["clip_id"]: c for c in clips["clips"]}
    items = gt["items"]
    cov = gt["meta"].get("coverage")

    if cov is None:
        problems.append("meta.coverage 가 없다 — 검토 실적을 확인할 수 없다")
    else:
        if cov["clips_total"] != len(items):
            problems.append(
                "meta.coverage.clips_total=%d 인데 items=%d" % (cov["clips_total"], len(items))
            )
        n_with = len([i for i in items if i["targets"]])
        if cov["clips_with_events"] != n_with:
            problems.append(
                "meta.coverage.clips_with_events=%d 인데 실제=%d"
                % (cov["clips_with_events"], n_with)
            )
        if cov["clips_reviewed"] < cov["clips_total"]:
            problems.append(
                "미검토 클립 %d개 — negative 를 정답으로 쓸 수 없다"
                % (cov["clips_total"] - cov["clips_reviewed"])
            )

    for item in items:
        clip = by_id.get(item["clip_id"])
        if clip is None:
            problems.append("%s: GT 항목이 clips.json 에 없다" % item["clip_id"])
            continue
        for t in item["targets"]:
            if t["violation_type"] not in VIOLATION_TYPES:
                problems.append(
                    "%s: %r 는 baseline 4종이 아니다" % (item["clip_id"], t["violation_type"])
                )
            if not t["t_start_sec"] < t["t_end_sec"]:
                problems.append(
                    "%s: t_start_sec >= t_end_sec (%s, %s)"
                    % (item["clip_id"], t["t_start_sec"], t["t_end_sec"])
                )
            if t["t_start_sec"] < 0 or t["t_end_sec"] > clip["duration_sec"]:
                problems.append(
                    "%s: span [%s, %s] 이 클립 길이 %s 를 벗어난다"
                    % (item["clip_id"], t["t_start_sec"], t["t_end_sec"], clip["duration_sec"])
                )

    for c in clips["clips"]:
        if not os.path.exists(os.path.join(paths.REPO_ROOT, c["file_path"])) \
                and not os.path.exists(c["file_path"]):
            problems.append("%s: file_path 가 존재하지 않는다 (%s)" % (c["clip_id"], c["file_path"]))

    for c in clips["clips"][:verify_hashes]:
        p = os.path.join(paths.REPO_ROOT, c["file_path"])
        if os.path.exists(p) and c.get("sha256"):
            if _sha256(p) != c["sha256"]:
                problems.append("%s: sha256 불일치" % c["clip_id"])

    return problems


def check_invariants(manifest_name, stage, verify_hashes=0):
    return validate(load_clips(manifest_name), load_gt(manifest_name, stage), verify_hashes)
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_manifests_io.py -v`
Expected: 5 passed

실제 B tier 데이터에서 `test_real_b_youtube_data_has_no_invariant_violations`가 실패하면 **구현이 아니라 데이터를 고친다.** 이 테스트가 잡아내는 것이 바로 `check_boundaries.py`가 못 보는 공백이다(스펙 §8).

- [ ] **Step 5: 커밋한다**

```bash
git add eval/manifests_io.py tests/eval/test_manifests_io.py
git commit -m "feat(eval): manifest·GT 로더와 불변식 검증"
```

---

## Task 3: normalized 뷰와 어댑터

**Files:**
- Create: `eval/runners/__init__.py`, `eval/runners/normalize.py`
- Test: `tests/eval/test_normalize.py`

**Interfaces:**
- Consumes: `eval.enums`
- Produces:
  - `NORMALIZER_VERSION: str` = `"n1"`
  - `normalize_candidate(raw: list) -> list` — 각 항목 `{"clip_id": str, "candidates": [{"rank": int, "t_start_sec": float, "t_end_sec": float, "event_type": str, "score": float}]}`
  - `normalize_classification(raw: list) -> list` — 각 항목 `{"sequence_id": str, "predicted": str, "target_bbox": list | None}`
  - `from_mock_pack(obj: dict) -> list` — Mock Pack의 평평한 `prediction` 객체를 candidate normalized 항목 1건으로 변환

`from_mock_pack`은 스펙 §2-4의 결정을 구현한다. Mock Pack 쪽 형식을 바꾸지 않고 읽기만 한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_normalize.py`:

```python
from eval.runners import normalize


def test_normalize_candidate_passes_through_shape():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 1, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "event_type": "SIGNAL", "score": 0.9}]}]
    out = normalize.normalize_candidate(raw)
    assert out == raw


def test_normalize_candidate_sorts_and_renumbers_rank():
    raw = [{"clip_id": "C1",
            "candidates": [{"rank": 9, "t_start_sec": 3.0, "t_end_sec": 4.0,
                            "event_type": "SIGNAL", "score": 0.2},
                           {"rank": 4, "t_start_sec": 1.0, "t_end_sec": 2.0,
                            "event_type": "SIGNAL", "score": 0.8}]}]
    out = normalize.normalize_candidate(raw)
    ranks = [c["rank"] for c in out[0]["candidates"]]
    assert ranks == [1, 2]
    assert out[0]["candidates"][0]["score"] == 0.8


def test_from_mock_pack_reads_team_fixture_shape():
    obj = {"scenario_id": "scenario_happy_001",
           "prediction": {"candidate_id": "cand_h001", "rank": 1,
                          "visual_event_type": "SOLID_LINE_LANE_CHANGE",
                          "plate_value": "12가 3476",
                          "occurred_at": "2026-08-24T18:31:30+09:00"}}
    out = normalize.from_mock_pack(obj)
    assert len(out) == 1
    assert out[0]["clip_id"] == "scenario_happy_001"
    c = out[0]["candidates"][0]
    assert c["rank"] == 1
    assert c["event_type"] == "SOLID_LINE_LANE_CHANGE"


def test_normalize_classification_shape():
    raw = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [1, 2, 3, 4]}]
    out = normalize.normalize_classification(raw)
    assert out[0]["sequence_id"] == "S1"
    assert out[0]["predicted"] == "SIGNAL"
    assert out[0]["target_bbox"] == [1, 2, 3, 4]
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_normalize.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.runners'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/runners/__init__.py`:

```python
"""runner — impl 을 호출해 immutable prediction 을 만든다.

runner 는 GT 를 모른다. 가짜 구현만 GT 파일을 스스로 읽는다.
"""
```

`eval/runners/normalize.py`:

```python
"""impl 원문 → scorer 가 읽는 얇은 뷰.

scorer 는 계약을 직접 읽지 않는다. 계약 간 필드명이 갈리는 문제
(docs/mock/CONTRACT_CONFLICTS.md §4)를 이 경계에서 흡수한다.
"""

NORMALIZER_VERSION = "n1"


def normalize_candidate(raw):
    """clip 단위 후보 목록. score 내림차순으로 rank 를 1부터 다시 매긴다."""
    out = []
    for item in raw:
        cands = sorted(item["candidates"], key=lambda c: -c["score"])
        out.append({
            "clip_id": item["clip_id"],
            "candidates": [
                {"rank": i + 1,
                 "t_start_sec": float(c["t_start_sec"]),
                 "t_end_sec": float(c["t_end_sec"]),
                 "event_type": c["event_type"],
                 "score": float(c["score"])}
                for i, c in enumerate(cands)
            ],
        })
    return out


def normalize_classification(raw):
    """시퀀스 단위 분류 결과."""
    return [
        {"sequence_id": item["sequence_id"],
         "predicted": item["predicted"],
         "target_bbox": item.get("target_bbox")}
        for item in raw
    ]


def from_mock_pack(obj):
    """Mock Pack v1 의 평평한 prediction 객체를 candidate normalized 로 옮긴다.

    data/mock/eval/prediction_*.json 은 `case` Owner 의 산출물이며 형식을
    바꾸라고 요구하지 않는다 (harness-v1-design.md §2-4). 여기서 읽기만 한다.
    시나리오 1건이므로 clip_id 자리에 scenario_id 를 쓴다.
    """
    p = obj["prediction"]
    return [{
        "clip_id": obj["scenario_id"],
        "candidates": [{
            "rank": int(p["rank"]),
            "t_start_sec": 0.0,
            "t_end_sec": 0.0,
            "event_type": p["visual_event_type"],
            "score": 1.0,
        }],
    }]
```

`from_mock_pack`의 span이 `0.0`인 것은 의도다 — Mock Pack fixture에 구간이 없다. span error 지표는 이 입력에서 `null`이 된다(Task 6).

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_normalize.py -v`
Expected: 4 passed

- [ ] **Step 5: 커밋한다**

```bash
git add eval/runners/ tests/eval/test_normalize.py
git commit -m "feat(eval): normalized 뷰와 Mock Pack 어댑터"
```

---

## Task 4: 레지스트리와 가짜 구현 2종

**Files:**
- Create: `eval/runners/registry.py`, `eval/runners/impls/__init__.py`, `eval/runners/impls/fake_always_correct.py`, `eval/runners/impls/fake_always_wrong.py`
- Test: `tests/eval/test_registry.py`

**Interfaces:**
- Consumes: `eval.manifests_io.load_gt`, `eval.enums.VIOLATION_TYPES`
- Produces:
  - `registry.get(name: str) -> callable` — 없으면 `KeyError`
  - `registry.names() -> list[str]`
  - impl 호출 규약: `impl(scope: dict) -> list` (raw). `scope`는 `{"manifest": str, "stage": str}`를 반드시 포함한다.

가짜 구현은 `scope["manifest"]`와 `scope["stage"]`로 GT를 **스스로** 읽는다. runner는 GT를 넘기지 않는다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_registry.py`:

```python
import pytest
from eval.runners import registry


def test_both_fakes_are_registered_under_fake_prefix():
    names = registry.names()
    assert "fake:always_correct" in names
    assert "fake:always_wrong" in names
    assert all(n.startswith("fake:") for n in names)


def test_unknown_impl_raises():
    with pytest.raises(KeyError):
        registry.get("does_not_exist")


def test_always_correct_reproduces_gt_spans():
    impl = registry.get("fake:always_correct")
    raw = impl({"manifest": "b_youtube", "stage": "candidate"})
    by_clip = {r["clip_id"]: r for r in raw}
    # GT 에 사건이 있는 클립은 후보를 돌려주고, 없는 클립은 빈 목록이다.
    assert by_clip["YT_0001_C08"]["candidates"][0]["event_type"] == "SIGNAL"
    assert by_clip["YT_0001_C00"]["candidates"] == []


def test_always_wrong_never_matches_gt_type():
    impl = registry.get("fake:always_wrong")
    raw = impl({"manifest": "b_youtube", "stage": "candidate"})
    by_clip = {r["clip_id"]: r for r in raw}
    assert by_clip["YT_0001_C08"]["candidates"][0]["event_type"] != "SIGNAL"


def test_always_correct_does_not_receive_gt_from_caller():
    # scope 에 GT 를 넣지 않아도 동작해야 한다 — impl 이 스스로 읽는다.
    impl = registry.get("fake:always_correct")
    scope = {"manifest": "b_youtube", "stage": "candidate"}
    assert "gt" not in scope
    assert impl(scope)
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.runners.registry'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/runners/impls/__init__.py`:

```python
"""가짜 구현 모음.

여기의 구현은 GT 를 직접 읽는 치트다. 실제 구현은 절대 여기 두지 않는다.
"""
```

`eval/runners/impls/fake_always_correct.py`:

```python
"""GT 를 그대로 되돌려주는 치트 구현.

지표 계산이 「정답일 때 만점」을 내는지 확인하는 용도다.
GT 를 스스로 읽는다 — runner 가 넘겨주지 않는다.
"""
from eval import manifests_io


def run(scope):
    gt = manifests_io.load_gt(scope["manifest"], scope["stage"])
    out = []
    for item in gt["items"]:
        cands = [
            {"rank": i + 1,
             "t_start_sec": t["t_start_sec"],
             "t_end_sec": t["t_end_sec"],
             "event_type": t["violation_type"],
             "score": 1.0 - i * 0.01}
            for i, t in enumerate(item["targets"])
        ]
        out.append({"clip_id": item["clip_id"], "candidates": cands})
    return out
```

`eval/runners/impls/fake_always_wrong.py`:

```python
"""의도적으로 틀린 답을 내는 치트 구현.

지표 계산이 오류를 실제로 잡아내는지 확인하는 용도다.
심는 오류: 유형 오분류 + 구간을 GT 밖으로 밀기 + negative 클립에 오탐.
"""
from eval import manifests_io
from eval.enums import VIOLATION_TYPES


def _other_type(t):
    for name in VIOLATION_TYPES:
        if name != t:
            return name
    raise AssertionError("baseline 이 1종뿐일 수 없다")


def run(scope):
    gt = manifests_io.load_gt(scope["manifest"], scope["stage"])
    out = []
    for item in gt["items"]:
        if item["targets"]:
            cands = [
                {"rank": i + 1,
                 "t_start_sec": float(t["t_end_sec"]) + 5.0,
                 "t_end_sec": float(t["t_end_sec"]) + 8.0,
                 "event_type": _other_type(t["violation_type"]),
                 "score": 0.5 - i * 0.01}
                for i, t in enumerate(item["targets"])
            ]
        else:
            # negative 클립에 오탐을 심는다 — FP/clip 이 0 이 아니어야 한다.
            cands = [{"rank": 1, "t_start_sec": 1.0, "t_end_sec": 3.0,
                      "event_type": VIOLATION_TYPES[0], "score": 0.5}]
        out.append({"clip_id": item["clip_id"], "candidates": cands})
    return out
```

`eval/runners/registry.py`:

```python
"""이름표 → 호출 가능 객체.

entry_points·동적 로딩을 쓰지 않는다 (harness-v1-design.md §2-3).
가짜 구현은 `fake:` 접두어로 격리한다.
"""
from eval.runners.impls import fake_always_correct, fake_always_wrong

_REGISTRY = {
    "fake:always_correct": fake_always_correct.run,
    "fake:always_wrong": fake_always_wrong.run,
}


def get(name):
    if name not in _REGISTRY:
        raise KeyError(
            "알 수 없는 impl 이름표: %r (등록된 것: %s)" % (name, ", ".join(names()))
        )
    return _REGISTRY[name]


def names():
    return sorted(_REGISTRY)
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_registry.py -v`
Expected: 5 passed

- [ ] **Step 5: 커밋한다**

```bash
git add eval/runners/registry.py eval/runners/impls/ tests/eval/test_registry.py
git commit -m "feat(eval): impl 레지스트리와 가짜 구현 2종"
```

---

## Task 5: runner CLI — prediction envelope

**Files:**
- Create: `eval/run.py`
- Test: `tests/eval/test_run.py`

**Interfaces:**
- Consumes: `registry.get`, `normalize.normalize_candidate`, `normalize.normalize_classification`, `normalize.NORMALIZER_VERSION`, `manifests_io.load_clips`, `paths.predictions_dir`
- Produces:
  - `build_envelope(impl_name: str, manifest: str, stage: str, run_id: str) -> dict`
  - `main(argv: list | None = None) -> int`
  - 파일 `eval/predictions/<run_id>.json`

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_run.py`:

```python
import json
import os
from eval import run, paths


def test_envelope_has_meta_raw_normalized():
    env = run.build_envelope("fake:always_correct", "b_youtube", "candidate", "run_test_001")
    assert set(env) == {"meta", "raw", "normalized"}
    assert env["meta"]["impl"] == "fake:always_correct"
    assert env["meta"]["stage"] == "candidate"
    assert env["meta"]["manifest"] == "b_youtube"
    assert env["meta"]["normalizer_version"] == "n1"
    assert env["meta"]["manifest_version"] == "m1"


def test_envelope_raw_is_preserved_not_replaced_by_normalized():
    env = run.build_envelope("fake:always_correct", "b_youtube", "candidate", "run_test_002")
    assert env["raw"] is not env["normalized"]
    assert len(env["raw"]) == 55


def test_main_writes_prediction_file(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    rc = run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
                   "--stage", "candidate", "--run-id", "run_test_003"])
    assert rc == 0
    p = os.path.join(str(tmp_path), "run_test_003.json")
    with open(p, encoding="utf-8") as f:
        env = json.load(f)
    assert env["meta"]["run_id"] == "run_test_003"


def test_unknown_impl_returns_nonzero(capsys):
    rc = run.main(["--impl", "nope", "--manifest", "b_youtube", "--stage", "candidate"])
    assert rc != 0
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_run.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.run'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/run.py`:

```python
"""runner CLI.

    python -m eval.run --impl fake:always_correct --manifest b_youtube --stage candidate

prediction 은 immutable 이다. 같은 run_id 로 덮어쓰지 않는다.
"""
import argparse
import datetime
import json
import os
import subprocess
import sys

from eval import manifests_io, paths
from eval.runners import normalize, registry

_NORMALIZERS = {
    "candidate": normalize.normalize_candidate,
    "classification": normalize.normalize_classification,
}


def _git_commit():
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             cwd=paths.REPO_ROOT, capture_output=True, text=True)
        return out.stdout.strip() or "unknown"
    except OSError:
        return "unknown"


def _new_run_id():
    return "run_" + datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


def build_envelope(impl_name, manifest, stage, run_id):
    impl = registry.get(impl_name)
    scope = {"manifest": manifest, "stage": stage}
    raw = impl(scope)
    normalized = _NORMALIZERS[stage](raw)
    clips_meta = manifests_io.load_clips(manifest)["meta"]
    return {
        "meta": {
            "run_id": run_id,
            "impl": impl_name,
            "impl_version": "v1",
            "stage": stage,
            "manifest": manifest,
            "manifest_version": clips_meta.get("manifest_version"),
            "clip_rule_version": clips_meta.get("clip_rule_version"),
            "normalizer_version": normalize.NORMALIZER_VERSION,
            "code_commit": _git_commit(),
            "created_at": datetime.datetime.now().astimezone().isoformat(),
        },
        "raw": raw,
        "normalized": normalized,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.run")
    ap.add_argument("--impl", required=True)
    ap.add_argument("--manifest", required=True)
    ap.add_argument("--stage", required=True, choices=sorted(_NORMALIZERS))
    ap.add_argument("--run-id", default=None)
    args = ap.parse_args(argv)

    run_id = args.run_id or _new_run_id()
    try:
        env = build_envelope(args.impl, args.manifest, args.stage, run_id)
    except KeyError as e:
        print("실패: %s" % e, file=sys.stderr)
        return 2

    outdir = paths.predictions_dir()
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, run_id + ".json")
    if os.path.exists(out):
        print("실패: %s 가 이미 있다. prediction 은 덮어쓰지 않는다." % out, file=sys.stderr)
        return 3
    with open(out, "w", encoding="utf-8") as f:
        json.dump(env, f, ensure_ascii=False, indent=2)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_run.py -v`
Expected: 4 passed

- [ ] **Step 5: 실제로 한 줄 실행이 되는지 확인한다**

Run: `python -m eval.run --impl fake:always_correct --manifest b_youtube --stage candidate`
Expected: `eval/predictions/run_<timestamp>.json` 경로가 출력된다. `ownership.md` §3 김대원 ⑤의 「한 줄로 도는 상태」가 여기서 충족된다.

- [ ] **Step 6: 커밋한다**

```bash
git add eval/run.py tests/eval/test_run.py
git commit -m "feat(eval): runner CLI 와 prediction envelope"
```

---

## Task 6: candidate scorer

**Files:**
- Create: `eval/scorers/__init__.py`, `eval/scorers/candidate.py`
- Test: `tests/eval/test_scorer_candidate.py`

**Interfaces:**
- Consumes: `normalized` 목록(Task 3 형태), `manifests_io.load_gt`
- Produces:
  - `score(normalized: list, gt: dict, ks=(1, 3, 10), iou_threshold=0.5) -> dict`

반환 형태:

```python
{
  "recall_at": {"1": 0.0~1.0, "3": ..., "10": ...},
  "span_error_sec": {"mean": float | None, "median": float | None},
  "fp_per_clip": float,
  "n_events": int, "n_negative_clips": int,
  "by_type": {"SIGNAL": {"recall_at": {...}, "n": int}, ...},
  "coverage": str | None,
}
```

매칭 규칙: 예측 span과 GT span의 IoU가 `iou_threshold` 이상이고 `event_type`이 같으면 적중. `scoring == "BOUNDARY_EXCLUDED"`인 GT target은 Recall 분모에서 제외한다(클립 경계에 걸쳐 있어 공정하지 않다).

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_scorer_candidate.py`:

```python
from eval import manifests_io
from eval.runners import registry, normalize
from eval.scorers import candidate


def _run(impl_name):
    raw = registry.get(impl_name)({"manifest": "b_youtube", "stage": "candidate"})
    return normalize.normalize_candidate(raw)


def test_always_correct_gets_perfect_recall():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["recall_at"]["1"] == 1.0
    assert r["recall_at"]["3"] == 1.0
    assert r["fp_per_clip"] == 0.0


def test_always_wrong_gets_zero_recall_and_positive_fp():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_wrong"), gt)
    assert r["recall_at"]["3"] == 0.0
    assert r["fp_per_clip"] > 0.0


def test_boundary_excluded_targets_are_not_counted():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    n_included = sum(1 for i in gt["items"] for t in i["targets"]
                     if t.get("scoring") != "BOUNDARY_EXCLUDED")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert r["n_events"] == n_included


def test_by_type_breakdown_lists_only_present_types():
    gt = manifests_io.load_gt("b_youtube", "candidate")
    r = candidate.score(_run("fake:always_correct"), gt)
    assert set(r["by_type"]) == {"SIGNAL", "SOLID_LINE_LANE_CHANGE"}


def test_zero_span_predictions_report_null_span_error():
    gt = {"meta": {"coverage": {}},
          "items": [{"clip_id": "C0", "source_video_id": "V", "targets": [
              {"event_id": "E", "violation_type": "SIGNAL", "t_start_sec": 1.0,
               "t_end_sec": 2.0, "t_onset_sec": 1.5, "scoring": "INCLUDED"}]}]}
    norm = [{"clip_id": "C0", "candidates": [
        {"rank": 1, "t_start_sec": 0.0, "t_end_sec": 0.0,
         "event_type": "SIGNAL", "score": 1.0}]}]
    r = candidate.score(norm, gt)
    assert r["span_error_sec"]["mean"] is None
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_scorer_candidate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.scorers'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/scorers/__init__.py`:

```python
"""scorer — prediction 의 normalized 뷰 + GT → metrics.

scorer 는 계약을 직접 읽지 않는다. normalized 뷰만 본다.
"""
```

`eval/scorers/candidate.py`:

```python
"""Candidate 단계 지표.

지표 정의의 원문은 module-architecture.md §9-3 과
modules/eval/initial-evaluation-plan.md §2 다. 여기서 새로 만들지 않는다.
"""
import statistics


def _iou(a_start, a_end, b_start, b_end):
    inter = max(0.0, min(a_end, b_end) - max(a_start, b_start))
    union = max(a_end, b_end) - min(a_start, b_start)
    if union <= 0:
        return 0.0
    return inter / union


def score(normalized, gt, ks=(1, 3, 10), iou_threshold=0.5):
    by_clip = {n["clip_id"]: n["candidates"] for n in normalized}

    events = []          # (clip_id, target)
    negative_clips = []
    for item in gt["items"]:
        included = [t for t in item["targets"] if t.get("scoring") != "BOUNDARY_EXCLUDED"]
        if item["targets"]:
            for t in included:
                events.append((item["clip_id"], t))
        else:
            negative_clips.append(item["clip_id"])

    hits = {k: 0 for k in ks}
    span_errors = []
    by_type = {}

    for clip_id, t in events:
        vt = t["violation_type"]
        slot = by_type.setdefault(vt, {"hits": {k: 0 for k in ks}, "n": 0})
        slot["n"] += 1
        cands = by_clip.get(clip_id, [])
        for k in ks:
            topk = [c for c in cands if c["rank"] <= k]
            matched = next(
                (c for c in topk
                 if c["event_type"] == vt
                 and _iou(c["t_start_sec"], c["t_end_sec"],
                          t["t_start_sec"], t["t_end_sec"]) >= iou_threshold),
                None,
            )
            if matched is not None:
                hits[k] += 1
                slot["hits"][k] += 1
                if k == min(ks) or True:
                    pass
        # span error 는 rank1 후보 기준. 폭이 0 인 예측(Mock Pack 유래)은 제외한다.
        if cands:
            top = cands[0]
            if top["t_end_sec"] > top["t_start_sec"]:
                span_errors.append(abs(top["t_start_sec"] - t["t_start_sec"]))

    n_events = len(events)
    fp = 0
    for clip_id in negative_clips:
        fp += len(by_clip.get(clip_id, []))

    return {
        "recall_at": {str(k): (hits[k] / n_events if n_events else None) for k in ks},
        "span_error_sec": {
            "mean": statistics.fmean(span_errors) if span_errors else None,
            "median": statistics.median(span_errors) if span_errors else None,
        },
        "fp_per_clip": (fp / len(negative_clips)) if negative_clips else None,
        "n_events": n_events,
        "n_negative_clips": len(negative_clips),
        "by_type": {
            vt: {"recall_at": {str(k): v["hits"][k] / v["n"] for k in ks}, "n": v["n"]}
            for vt, v in sorted(by_type.items())
        },
        "coverage": None if n_events else "NO_EVENTS — GT 에 채점할 사건이 없다",
    }
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_scorer_candidate.py -v`
Expected: 5 passed

- [ ] **Step 5: 죽은 분기를 지운다**

Step 3의 `if k == min(ks) or True: pass`는 아무 일도 하지 않는다. 삭제하고 테스트를 다시 돌린다.

Run: `python -m pytest tests/eval/test_scorer_candidate.py -v`
Expected: 5 passed

- [ ] **Step 6: 커밋한다**

```bash
git add eval/scorers/ tests/eval/test_scorer_candidate.py
git commit -m "feat(eval): candidate scorer — Recall@K · span error · FP/clip"
```

---

## Task 7: A tier 샘플링 도구

**Files:**
- Create: `eval/tools/__init__.py`, `eval/tools/sample_aihub.py`
- Create (생성물): `eval/manifests/a_aihub/sequences.json`, `eval/manifests/a_aihub/gt/gt_classification.json`
- Test: `tests/eval/test_sample_aihub.py`

**Interfaces:**
- Consumes: `eval.enums.VIOLATION_TYPES`, `eval.paths`
- Produces:
  - `TYPE_MAP: dict[str, str]` — AI-Hub 한글 폴더명 → baseline enum
  - `sample(zip_path: str, per_type: int, seed: int) -> tuple[dict, dict]` — `(sequences, gt)`
  - `main(argv=None) -> int`

`TYPE_MAP`은 확인된 폴더명 그대로다:

```
신호위반       → SIGNAL
중앙선침범     → CENTER_LINE_CROSSING
진로변경위반   → SOLID_LINE_LANE_CHANGE
안전모미착용   → MOTORCYCLE_HELMET_NON_USE
```

**샘플링 규칙(GT의 일부):** 유형별로 `per_type`개 시퀀스를 뽑는다. 같은 시퀀스의 프레임이 흩어지지 않도록 **시퀀스 단위**로 뽑는다. `seed`를 고정해 재현 가능하게 하고, `sequences.json`의 `meta.sampling`에 기록한다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_sample_aihub.py`:

```python
import os
import pytest
from eval import paths
from eval.enums import VIOLATION_TYPES
from eval.tools import sample_aihub

VL = os.path.join(paths.REPO_ROOT, "eval", "manifests", "02.라벨링데이터", "VL.zip")
needs_archive = pytest.mark.skipif(not os.path.exists(VL), reason="VL.zip 없음 (로컬 전용)")


def test_type_map_covers_exactly_the_four_baseline_types():
    assert sorted(sample_aihub.TYPE_MAP.values()) == sorted(VIOLATION_TYPES)


@needs_archive
def test_sample_is_deterministic_for_same_seed():
    a, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    b, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    ids_a = [s["sequence_id"] for s in a["sequences"]]
    ids_b = [s["sequence_id"] for s in b["sequences"]]
    assert ids_a == ids_b


@needs_archive
def test_sample_balances_by_type():
    seqs, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    counts = {}
    for s in seqs["sequences"]:
        counts[s["violation_type"]] = counts.get(s["violation_type"], 0) + 1
    assert set(counts) == set(VIOLATION_TYPES)
    assert all(v == 3 for v in counts.values())


@needs_archive
def test_sampling_rule_is_recorded_in_meta():
    seqs, _ = sample_aihub.sample(VL, per_type=3, seed=42)
    s = seqs["meta"]["sampling"]
    assert s["seed"] == 42
    assert s["per_type"] == 3
    assert s["rule_version"]


@needs_archive
def test_gt_labels_are_baseline_enum_and_carry_source_tier():
    _, gt = sample_aihub.sample(VL, per_type=3, seed=42)
    assert gt["meta"]["stage"] == "classification"
    for item in gt["items"]:
        assert item["label"] in VIOLATION_TYPES
        assert item["source_tier"] == "A"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_sample_aihub.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'eval.tools'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/tools/__init__.py`:

```python
"""데이터 준비 도구. 채점 경로가 아니다."""
```

`eval/tools/sample_aihub.py`:

```python
"""AI-Hub A tier 아카이브에서 평가용 시퀀스를 뽑는다.

51.4GB 아카이브를 풀지 않는다. 라벨 zip 만 읽어 GT 를 만들고,
이미지는 필요할 때 sequence 의 archive_path 로 꺼낸다.

샘플링 규칙은 GT 의 일부다 — seed 와 rule_version 을 meta 에 남긴다.
"""
import argparse
import collections
import json
import os
import random
import sys
import zipfile

from eval import paths

RULE_VERSION = "s1"

TYPE_MAP = {
    "신호위반": "SIGNAL",
    "중앙선침범": "CENTER_LINE_CROSSING",
    "진로변경위반": "SOLID_LINE_LANE_CHANGE",
    "안전모미착용": "MOTORCYCLE_HELMET_NON_USE",
}

# 위반 차량 bbox 를 가진 객체 이름. 확인된 목록 그대로다.
TARGET_OBJECTS = (
    "신호 위반 차량(이륜차 포함)",
    "중앙선침범 위반 차량(이륜차 포함)",
    "진로변경 위반 차량(이륜차 포함)",
    "안전모 미착용 이륜차",
)
NORMAL_OBJECT_PREFIX = "정상 차량"


def _index(zf):
    """{(top, sub, sequence_id): [entry, ...]}"""
    idx = collections.defaultdict(list)
    for name in zf.namelist():
        if not name.endswith(".json"):
            continue
        parts = name.split("/")
        if len(parts) < 4:
            continue
        idx[(parts[0], parts[1], parts[2])].append(name)
    return idx


def sample(zip_path, per_type, seed):
    zf = zipfile.ZipFile(zip_path)
    idx = _index(zf)

    by_type = collections.defaultdict(list)
    for key in sorted(idx):
        top = key[0]
        if top in TYPE_MAP:
            by_type[TYPE_MAP[top]].append(key)

    rng = random.Random(seed)
    sequences = []
    gt_items = []
    for vtype in sorted(by_type):
        keys = sorted(by_type[vtype])
        picked = rng.sample(keys, min(per_type, len(keys)))
        for top, sub, seq_id in sorted(picked):
            frames = sorted(idx[(top, sub, seq_id)])
            first = json.loads(zf.read(frames[0]).decode("utf-8"))
            cond = first.get("condition", {})

            target_bbox = None
            target_frame = None
            distractors = 0
            for fname in frames:
                d = json.loads(zf.read(fname).decode("utf-8"))
                anns = d["Annotation"]["annotations"]
                for a in anns:
                    if a["Object Name"] in TARGET_OBJECTS and "Bbox Cordinate" in a:
                        if target_bbox is None:
                            target_bbox = a["Bbox Cordinate"]
                            target_frame = os.path.basename(fname).replace(".json", ".jpg")
                if target_bbox is not None:
                    distractors = sum(
                        1 for a in anns if a["Object Name"].startswith(NORMAL_OBJECT_PREFIX)
                    )
                    break

            sequences.append({
                "sequence_id": seq_id,
                "violation_type": vtype,
                "sub_type": sub,
                "frame_count": len(frames),
                "condition": {
                    "weather": cond.get("Weather"),
                    "day_night": cond.get("DayNights"),
                    "road_type": cond.get("roadType"),
                },
                "archive": os.path.basename(zip_path).replace("VL", "VS"),
                "archive_path": "%s/%s/%s" % (top, sub, seq_id),
                "split": "DEV",
            })
            gt_items.append({
                "sequence_id": seq_id,
                "label": vtype,
                "target_bbox": target_bbox,
                "target_frame": target_frame,
                "distractor_count": distractors,
                # scorer 는 (normalized, gt) 두 개만 받는다. 조건별 지표를
                # 내려면 GT 가 자족적이어야 하므로 sequences 와 같은 값을
                # 여기에도 싣는다 (Task 8 classification.score 가 읽는다).
                "condition": {
                    "weather": cond.get("Weather"),
                    "day_night": cond.get("DayNights"),
                    "road_type": cond.get("roadType"),
                },
                "source_tier": "A",
            })

    seqs = {
        "meta": {
            "manifest_version": "m1",
            "tier": "A",
            "source": "aihub",
            "sampling": {
                "rule_version": RULE_VERSION,
                "seed": seed,
                "per_type": per_type,
                "strategy": "type-stratified, sequence-level",
            },
        },
        "sequences": sequences,
    }
    gt = {
        "meta": {"gt_version": "g1", "tier": "A", "stage": "classification",
                 "coverage": {"sequences_total": len(gt_items),
                              "sampling_rule_version": RULE_VERSION,
                              "sampling_seed": seed}},
        "items": gt_items,
    }
    return seqs, gt


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.tools.sample_aihub")
    ap.add_argument("--zip", default=os.path.join(
        paths.REPO_ROOT, "eval", "manifests", "02.라벨링데이터", "VL.zip"))
    ap.add_argument("--per-type", type=int, default=30)
    ap.add_argument("--seed", type=int, default=20260906)
    args = ap.parse_args(argv)

    if not os.path.exists(args.zip):
        print("실패: %s 가 없다" % args.zip, file=sys.stderr)
        return 2

    seqs, gt = sample(args.zip, args.per_type, args.seed)
    outdir = paths.manifest_dir("a_aihub")
    os.makedirs(os.path.join(outdir, "gt"), exist_ok=True)
    with open(os.path.join(outdir, "sequences.json"), "w", encoding="utf-8") as f:
        json.dump(seqs, f, ensure_ascii=False, indent=2)
    with open(os.path.join(outdir, "gt", "gt_classification.json"), "w", encoding="utf-8") as f:
        json.dump(gt, f, ensure_ascii=False, indent=2)
    print("시퀀스 %d개 / GT %d건" % (len(seqs["sequences"]), len(gt["items"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/test_sample_aihub.py -v`
Expected: 5 passed (VL.zip이 없는 환경에서는 4 skipped + 1 passed)

- [ ] **Step 5: 실제로 GT를 만든다**

Run: `python -m eval.tools.sample_aihub --per-type 30 --seed 20260906`
Expected: `시퀀스 120개 / GT 120건`

- [ ] **Step 6: 커밋한다**

```bash
git add eval/tools/ tests/eval/test_sample_aihub.py eval/manifests/a_aihub/
git commit -m "feat(eval): A tier 샘플링 도구와 classification GT"
```

---

## Task 8: classification·plate scorer와 score CLI

**Files:**
- Create: `eval/scorers/classification.py`, `eval/scorers/plate.py`, `eval/score.py`
- Test: `tests/eval/test_scorer_classification.py`, `tests/eval/test_score_cli.py`

**Interfaces:**
- Consumes: Task 3의 `normalize_classification`, Task 7의 `gt_classification.json`
- Produces:
  - `classification.score(normalized: list, gt: dict) -> dict`
  - `plate.score(normalized: list, gt: dict | None) -> dict`
  - `score.main(argv=None) -> int` → `eval/results/<run_id>.<gt_version>.json`

`classification.score` 반환:

```python
{
  "recall_macro": float, "precision_macro": float,
  "confusion": {"SIGNAL": {"SIGNAL": 3, "NONE": 1, ...}, ...},  # 5×5
  "target_correctness": float | None,
  "by_condition": {"day_night": {"주간": {"accuracy": float, "n": int}, ...}},
  "n": int, "coverage": str | None,
}
```

`plate.score`는 GT가 없으면 전부 `null`을 돌려준다 — 0이 아니다.

- [ ] **Step 1: 실패하는 테스트를 쓴다**

`tests/eval/test_scorer_classification.py`:

```python
from eval.scorers import classification, plate

GT = {"meta": {"gt_version": "g1", "tier": "A", "stage": "classification"},
      "items": [
          {"sequence_id": "S1", "label": "SIGNAL", "target_bbox": [0, 0, 10, 10],
           "distractor_count": 1, "source_tier": "A"},
          {"sequence_id": "S2", "label": "CENTER_LINE_CROSSING", "target_bbox": None,
           "distractor_count": 0, "source_tier": "A"},
          {"sequence_id": "S3", "label": "NONE", "target_bbox": None,
           "distractor_count": 0, "source_tier": "B"},
      ]}


def test_perfect_prediction_scores_one():
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": [0, 0, 10, 10]},
            {"sequence_id": "S2", "predicted": "CENTER_LINE_CROSSING", "target_bbox": None},
            {"sequence_id": "S3", "predicted": "NONE", "target_bbox": None}]
    r = classification.score(norm, GT)
    assert r["recall_macro"] == 1.0
    assert r["precision_macro"] == 1.0


def test_confusion_matrix_is_five_by_five():
    norm = [{"sequence_id": "S1", "predicted": "SIGNAL", "target_bbox": None},
            {"sequence_id": "S2", "predicted": "SIGNAL", "target_bbox": None},
            {"sequence_id": "S3", "predicted": "NONE", "target_bbox": None}]
    r = classification.score(norm, GT)
    assert len(r["confusion"]) == 5
    assert all(len(row) == 5 for row in r["confusion"].values())
    assert r["confusion"]["CENTER_LINE_CROSSING"]["SIGNAL"] == 1


def test_target_correctness_is_null_when_no_gt_bbox():
    norm = [{"sequence_id": "S2", "predicted": "CENTER_LINE_CROSSING", "target_bbox": [1, 1, 2, 2]}]
    gt = {"meta": GT["meta"], "items": [GT["items"][1]]}
    r = classification.score(norm, gt)
    assert r["target_correctness"] is None


def test_plate_without_gt_reports_null_not_zero():
    r = plate.score([], None)
    assert r["exact_accuracy"] is None
    assert r["wrong_accept_rate"] is None
    assert r["abstention_recall"] is None
    assert "NO_C_TIER_DATA" in r["coverage"]
```

`tests/eval/test_score_cli.py`:

```python
import json
import os
from eval import run, score, paths


def test_score_cli_writes_results_with_coverage(tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "predictions_dir", lambda: str(tmp_path))
    monkeypatch.setattr(paths, "results_dir", lambda: str(tmp_path))
    run.main(["--impl", "fake:always_correct", "--manifest", "b_youtube",
              "--stage", "candidate", "--run-id", "run_cli_001"])
    rc = score.main(["--prediction", "run_cli_001"])
    assert rc == 0
    out = os.path.join(str(tmp_path), "run_cli_001.g1.json")
    with open(out, encoding="utf-8") as f:
        res = json.load(f)
    assert res["candidate"]["recall_at"]["1"] == 1.0
    assert res["plate"]["exact_accuracy"] is None
    assert res["meta"]["impl"] == "fake:always_correct"
```

- [ ] **Step 2: 테스트가 실패하는지 확인한다**

Run: `python -m pytest tests/eval/test_scorer_classification.py tests/eval/test_score_cli.py -v`
Expected: FAIL — `ImportError: cannot import name 'classification'`

- [ ] **Step 3: 최소 구현을 쓴다**

`eval/scorers/classification.py`:

```python
"""Classification 단계 지표 (v4 §9-3).

confusion matrix 는 4종 + NONE 의 5×5 다.
"""
import collections

from eval.enums import CLASS_LABELS


def _macro(per_label):
    vals = [v for v in per_label.values() if v is not None]
    return sum(vals) / len(vals) if vals else None


def score(normalized, gt):
    gt_by_id = {i["sequence_id"]: i for i in gt["items"]}
    pred_by_id = {n["sequence_id"]: n for n in normalized}

    confusion = {a: {b: 0 for b in CLASS_LABELS} for a in CLASS_LABELS}
    tp = collections.Counter()
    fp = collections.Counter()
    fn = collections.Counter()
    by_cond = collections.defaultdict(lambda: {"correct": 0, "n": 0})

    target_hits = 0
    target_total = 0

    for sid, item in gt_by_id.items():
        truth = item["label"]
        pred = pred_by_id.get(sid, {}).get("predicted", "NONE")
        if truth in confusion and pred in confusion[truth]:
            confusion[truth][pred] += 1
        if pred == truth:
            tp[truth] += 1
        else:
            fn[truth] += 1
            fp[pred] += 1

        cond = item.get("condition") or {}
        dn = cond.get("day_night")
        if dn:
            by_cond[dn]["n"] += 1
            if pred == truth:
                by_cond[dn]["correct"] += 1

        gt_box = item.get("target_bbox")
        if gt_box:
            target_total += 1
            if pred_by_id.get(sid, {}).get("target_bbox") == gt_box:
                target_hits += 1

    recall = {}
    precision = {}
    for label in CLASS_LABELS:
        denom_r = tp[label] + fn[label]
        denom_p = tp[label] + fp[label]
        recall[label] = tp[label] / denom_r if denom_r else None
        precision[label] = tp[label] / denom_p if denom_p else None

    return {
        "recall_macro": _macro(recall),
        "precision_macro": _macro(precision),
        "recall_by_label": recall,
        "confusion": confusion,
        "target_correctness": (target_hits / target_total) if target_total else None,
        "by_condition": {
            "day_night": {k: {"accuracy": v["correct"] / v["n"], "n": v["n"]}
                          for k, v in sorted(by_cond.items())}
        },
        "n": len(gt_by_id),
        "coverage": None if gt_by_id else "NO_SEQUENCES — GT 가 비어 있다",
    }
```

`eval/scorers/plate.py`:

```python
"""Plate 단계 지표.

A tier 는 번호판이 비식별 처리되어 문자 정답이 없다
(harness-v1-design.md §4-3). C tier 가 들어오기 전까지 전부 null 이다.
0 으로 적지 않는다 — 데이터가 없는 것과 성능이 나쁜 것은 다른 사실이다.
"""

NO_DATA = ("NO_C_TIER_DATA — plate text GT 부재. "
           "A tier 는 번호판 마스킹(harness-v1-design.md §4-3)")


def score(normalized, gt):
    if not gt or not gt.get("items"):
        return {"exact_accuracy": None, "wrong_accept_rate": None,
                "abstention_recall": None, "n": 0, "coverage": NO_DATA}

    total = correct = wrong_accept = 0
    abstain_total = abstain_correct = 0
    by_id = {n["sequence_id"]: n for n in normalized}
    for item in gt["items"]:
        truth = item.get("plate_text")
        pred = by_id.get(item["sequence_id"], {}).get("plate_value")
        if truth is None:
            abstain_total += 1
            if pred is None:
                abstain_correct += 1
            continue
        total += 1
        if pred == truth:
            correct += 1
        elif pred is not None:
            wrong_accept += 1

    return {
        "exact_accuracy": (correct / total) if total else None,
        "wrong_accept_rate": (wrong_accept / total) if total else None,
        "abstention_recall": (abstain_correct / abstain_total) if abstain_total else None,
        "n": total + abstain_total,
        "coverage": None,
    }
```

`eval/score.py`:

```python
"""scorer CLI.

    python -m eval.score --prediction run_20260906_001

prediction 을 읽어 stage 에 맞는 scorer 를 돌리고 results 를 쓴다.
데이터가 없는 stage 는 null + 사유로 채운다.
"""
import argparse
import json
import os
import sys

from eval import manifests_io, paths
from eval.scorers import candidate, classification, plate


def _load_prediction(run_id):
    with open(os.path.join(paths.predictions_dir(), run_id + ".json"), encoding="utf-8") as f:
        return json.load(f)


def build_result(env):
    stage = env["meta"]["stage"]
    manifest = env["meta"]["manifest"]
    gt = manifests_io.load_gt(manifest, stage)
    norm = env["normalized"]

    result = {
        "meta": {
            "run_id": env["meta"]["run_id"],
            "impl": env["meta"]["impl"],
            "stage": stage,
            "manifest": manifest,
            "gt_version": gt["meta"]["gt_version"],
            "normalizer_version": env["meta"]["normalizer_version"],
            "code_commit": env["meta"]["code_commit"],
        },
        "candidate": None,
        "classification": None,
        "plate": plate.score(norm, None),
    }
    if stage == "candidate":
        result["candidate"] = candidate.score(norm, gt)
        result["classification"] = {
            "coverage": "NOT_RUN — stage=candidate 실행이다"
        }
    elif stage == "classification":
        result["classification"] = classification.score(norm, gt)
        result["candidate"] = {"coverage": "NOT_RUN — stage=classification 실행이다"}
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(prog="eval.score")
    ap.add_argument("--prediction", required=True, help="run_id")
    args = ap.parse_args(argv)

    try:
        env = _load_prediction(args.prediction)
    except OSError as e:
        print("실패: %s" % e, file=sys.stderr)
        return 2

    result = build_result(env)
    outdir = paths.results_dir()
    os.makedirs(outdir, exist_ok=True)
    out = os.path.join(outdir, "%s.%s.json" % (args.prediction, result["meta"]["gt_version"]))
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 테스트가 통과하는지 확인한다**

Run: `python -m pytest tests/eval/ -v`
Expected: 전부 통과

- [ ] **Step 5: 두 가짜 구현을 끝까지 돌려 대비를 확인한다**

```bash
python -m eval.run --impl fake:always_correct --manifest b_youtube --stage candidate --run-id demo_correct
python -m eval.run --impl fake:always_wrong   --manifest b_youtube --stage candidate --run-id demo_wrong
python -m eval.score --prediction demo_correct
python -m eval.score --prediction demo_wrong
```

Expected: `demo_correct`는 `recall_at["1"] == 1.0`, `fp_per_clip == 0.0`. `demo_wrong`은 `recall_at["3"] == 0.0`, `fp_per_clip > 0`. **이 대비가 지표 계산이 맞다는 증거다**(`ownership.md` §3 김대원 ⑤).

- [ ] **Step 6: 커밋한다**

```bash
git add eval/scorers/classification.py eval/scorers/plate.py eval/score.py tests/eval/ eval/predictions/ eval/results/
git commit -m "feat(eval): classification·plate scorer 와 score CLI"
```

---

## Self-Review 결과

**스펙 커버리지**

| 스펙 절 | 담당 태스크 |
| --- | --- |
| §1 v1 범위 (Candidate·Classification·Plate) | Task 6 · 8 |
| §2-1 envelope | Task 3 · 5 |
| §2-2 tier 단위 묶음 | Task 1 |
| §2-3 딕셔너리 레지스트리 | Task 4 |
| §2-4 두 prediction 형식 공존 | Task 3 (`from_mock_pack`) |
| §2-5 runner는 GT를 모른다 | Task 4 (테스트로 강제) |
| §3-1 폴더 · §3-2 흐름 | Task 1 · 5 · 8 |
| §4-1 B tier 승계 | Task 2 |
| §4-2 A tier 샘플링이 GT의 일부 | Task 7 |
| §4-3 Plate 불가 | Task 8 (`plate.NO_DATA`) |
| §5 결측은 null + 사유 | Task 6 · 8 |
| §6 가짜 구현 대비 · GT 불변식 | Task 2 · 6 · 8 |
| §7 공개/비공개 분리 | 이미 적용됨 (`.gitignore`) |
| §7-1 `meta.coverage` | Task 2 (불변식으로 검사) |

**미커버 항목:** §9 후속 항목(F1~F5)과 §10 열린 결정은 v1 구현 대상이 아니다 — 의도적으로 태스크를 만들지 않았다.

**타입 일관성 확인:** `normalized` 항목 키가 stage마다 다르다(`clip_id` vs `sequence_id`). Task 3에서 정의하고 Task 6·8이 각각 자기 stage 것만 읽는다. `score(normalized, gt)` 시그니처는 세 scorer가 동일하다.

---

## 실행 방법 선택

Plan complete and saved to `docs/modules/eval/harness-v1-plan.md`. 두 가지 실행 방식이 있습니다.

**1. Subagent-Driven (추천)** — 태스크마다 새 subagent를 띄우고 사이사이 검토합니다. 반복이 빠릅니다.

**2. Inline Execution** — 이 세션에서 executing-plans로 직접 실행하고 체크포인트마다 멈춥니다.

어느 쪽으로 할까요?
