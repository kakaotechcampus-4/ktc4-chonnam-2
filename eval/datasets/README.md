# eval/datasets

평가 데이터 원본. A tier(AI-Hub frame sequence) / B tier(실제·YouTube 1분 clip) / C tier(팀원 SD 원본). **미디어 파일은 커밋하지 않는다** — 루트 `.gitignore`가 이 폴더의 README 외 전부를 무시한다. 무엇이 있는지는 `manifests/`가 말한다. 세부 실패 사례와 Hard-negative 데이터셋은 공개하지 않는다(`docs/product/product-strategy.md` §6).

2026-10-30에 추가한 AI-Hub 선별 MP4 원천 400개는 이 폴더 밖의 로컬 `D:/카테캠/데이터/AIHub_traffic_videos_best_100_each/`에 있다. 전체는 `a_aihub_best100_all`, 그중 Validation 중복 제거 117개는 `a_aihub_best100_val` manifest로 각각 고정했다. 삽입 실험에서 만든 영상 16개는 이 폴더의 `aihub_mixed_pilot/`에 두고 커밋하지 않는다. 구성과 결과는 [`docs/modules/eval/datasets/README.md`](../../docs/modules/eval/datasets/README.md)와 [10/30 실험 기록](../../docs/modules/eval/experiments/2026-10-30-aihub-best100-video-and-mixed.md)을 본다.

확장 합성 세트 `aihub_mixed_100_v1/`에는 서로 다른 C tier 2 정상 블박 100개를 사용한 삽입 영상 100개와 같은 배경의 정상 대조 영상 100개를 둔다. 생성 규칙과 원본 파일별 해시는 `eval/manifests/aihub_mixed_100_v1/samples.json`에 기록한다. 이 영상도 로컬에만 보관한다.

## 미디어가 없으면 건너뛰는 테스트

clone 직후에는 이 폴더에 README 밖에 없다. 아래 테스트는 로컬 미디어가 있을 때만 돌고, 없으면 **실패가 아니라 skip** 이다 — 데이터 부재가 정답지 오류로 오독되지 않게 하기 위해서다.

| 테스트 | 필요한 것 | skip 사유 문구 |
| --- | --- | --- |
| `tests/eval/test_manifests_io.py::test_real_b_youtube_data_has_no_invariant_violations` | `eval/datasets/youtube/clips/` 의 클립 123개 (`file_path` 존재 · `sha256` 대조) | `B tier 미디어 없음 (로컬 전용)` |
| `tests/eval/test_sample_aihub.py` 의 아카이브 표시 테스트 4건 | `eval/manifests/02.라벨링데이터/VL.zip` (247MB) | `VL.zip 없음 (로컬 전용)` |

나머지는 커밋된 manifest·GT 만으로 돌므로 fresh clone 에서도 전부 통과한다 (A tier GT 불변식 포함).

**어떻게 받나.** 둘 다 재배포하지 않는다 — B tier 클립은 원본 YouTube 영상에서 `clips.json` 의 `clip_rule_version` 규칙대로 다시 자르고 `sha256` 으로 대조한다. A tier 아카이브는 AI-Hub 계정으로 직접 내려받는다. 어느 쪽이든 Owner(김대원)에게 물어보는 게 빠르다.
