# `readout` — 번호판·화면값 판독

**Owner:** 신유민 (`docs/management/ownership.md`) · **경계:** `docs/architecture/module-architecture.md` §4-모듈3 · **문서 작업공간:** `docs/modules/readout/`

## 이 폴더가 하는 일 (요약 — 원문은 §4-모듈3)

대상 차량 association·번호판 detection·multi-frame·best frame·OCR·consensus·abstain·Overlay Timestamp OCR과 검증·근거 frame refs

## 이 폴더가 알면 안 되는 것 (§4-모듈3 「알면 안 되는 것」)

최종 발생시각 source 우선순위 / 신고 요건·기한 / Report Type / 확정 번호판 값 / 사용자 workflow stage / Report Video에 사후 삽입된 Timestamp를 근거로 OCR

## 공개 함수

다른 모듈은 **공개 함수만** 호출한다. `api.py`에 있다.

```python
read_plate(request, target_hint=None, provider=None, *, run_id=None)  -> (ReadoutRun, PlateReadout | None)
read_overlay_time(request, provider=None, *, run_id=None)             -> (ReadoutRun, OverlayTimeReadout | None)
```

- `request`는 `ReadRequest(case_id, candidate_id, input_ref)`다. §4-모듈3 ③이 적은 `span`은 `plate-readout/v1.2`에서 `input_ref.span_ref`가 삭제되면서 사라졌다 — 사건 구간의 canonical reference는 `input_ref.incident_clip_ref` 하나다.
- `target_hint`는 optional이다. 없으면 자체 association을 시도하고, 어느 쪽이든 결과는 `target_association`에 남는다.
- `run_id`는 optional이다. 호출하는 쪽이 미리 발급해 넘기면 그 값이 `ReadoutRun.run_id`가 되고, 없으면 readout이 만든다(#297). 호출마다 새 값을 주는 것은 넘기는 쪽 책임이다.
- 두 번째 반환값이 `None`인 경우는 **완전 실패 하나뿐**이다. 그때도 `ReadoutRun`은 남는다.
- `list_impls()`는 아직 없다.

## OCR provider

판정(association 반영·consensus·abstain·overlay 4갈래·validation·run 조립)은 `api.py`가 한다. 프레임을 떠서 글자로 바꾸는 부분은 provider가 맡고, `provider=`로 넘긴다.

- 운영 OCR은 `paddle_provider.py`의 `PaddleOcrProvider`(PaddleOCR)다. `worker/readout_composition.py`와 `case/real_e2e.py`가 이것을 넘긴다.
- `provider=`를 넘기지 않으면 `providers.py`의 `FixtureOcrProvider`가 기본값이다. 테스트용이고, Mock Pack v5 fixture(`data/mock/readout/`)를 provider 출력으로 되읽는다.

## 상태

계약 타입(`contracts.py`) · 등재값(`registry.py`) · fixture 로더(`fixtures.py`) · 불변조건 19개(R1~R19, `invariants.py`) · 공개 함수 2개(`api.py`) · provider 경계(`providers.py`) · PaddleOCR provider(`paddle_provider.py`).

검증은 `python -m pytest tests/readout`. 폴더의 범위는 위 문서들이 정한다 — 여기에 규칙을 복제하지 않는다.
