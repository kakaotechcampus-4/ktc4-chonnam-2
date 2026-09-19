# Merge 전 셀프 체크 증빙 — readout (2026-09-14)

`scripts/dump_readout_evidence.py`가 **공개 함수를 실제로 불러** 만든 출력이다. 손으로 쓴 예시가
아니다. 1차 체크리스트 「Merge 전 셀프 체크 증빙」 항목에 그대로 대응한다.

재생성:

```
python scripts/dump_readout_evidence.py
```

## 파일

| 파일 | 무엇을 보여주나 | 체크리스트 |
| --- | --- | --- |
| `01-plate-happy.json` | 정상 판독 — `value` `12가3456` · `status=OK` · `abstained=false` | 증빙 ① · 확인 질문 1 |
| `02-overlay-ok.json` | overlay 읽음 — `OK`, `validation` 3종 전부 `true` | 4갈래 비교 기준 |
| `03-overlay-not-present.json` | 「없음」(사실) — `NOT_APPLICABLE` + `readout.overlay.not_present` | 증빙 ② |
| `04-overlay-presence-undetermined.json` | 「있는지 못 봄」(모름) — `UNKNOWN` + `...presence_undetermined` | 증빙 ② |
| `05-overlay-ocr-failed.json` | 「읽었으나 못 알아봄」(모름) — `UNKNOWN` + `...ocr_failed`, `format_ok=false` | 증빙 ② |
| `06-plate-abstain.json` | 보류 — `abstained=true` · `NEEDS_REVIEW` · `value` `17나28??` | 증빙 ③ |
| `07-plate-reread.json` | 재판독 성공 — `value` `17나2867` · `OK`. `06`을 고치지 않은 **새 run·새 결과** | 증빙 ③ |
| `08-plate-total-failure.txt` | 완전 실패 — `outcome=FAILED`이고 **결과 객체가 없다** | 증빙 ④ |

## Merge 중단 기준과의 대응

- **abstain인데 확정값이 함께 나옴** → `06`. `value`에 `?`가 남아 있고 `abstain_reason`은 단일 값 하나다
- **완전 실패인데 결과 객체가 생성됨** → `08`. 결과가 `None`이다
- **overlay 4갈래 중 둘 이상이 합쳐짐** → `02`~`05`. `status`와 `reason.code` 조합이 넷 다 다르다
- **미등재 값 사용** → 전 파일. `failure.kind`·`code`·`abstain_reason`·`reason.code`가 등재값뿐이다

## 자기검사

이 폴더의 출력 전부에 `invariants.check_all`(R1~R18)을 걸었다 — **위반 0건.**
fixture가 아니라 구현이 만든 값에 건 것이다.

## 다시 돌리면 달라지는 것

`run_id` · `readout_id` · `crop_ref` · `started_at` · `ended_at`은 **실행마다 바뀐다.** 오류가
아니라 규칙이다 — `run_id`는 1회성 식별자이고(`contract-readout-run.md` §4), `crop_ref`는
프레임을 다시 떠서 읽으면 새로 발급한다(`contract-plate-overlay-readout.md` §3). 이 폴더의
파일은 2026-09-14 실행분 스냅샷이다. 값의 **의미**가 바뀌면 그때는 구현이 움직인 것이다.
