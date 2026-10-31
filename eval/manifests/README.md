# eval/manifests

정답지(GT)와 입력 목록의 버전을 관리한다. 사건(event)·시퀀스(sequence)·클립(clip)의 단위가 다른 셋을 혼동하지 않는다. 전체 현황은 [`docs/modules/eval/datasets/README.md`](../../docs/modules/eval/datasets/README.md)에 있다.

2026-10-30 추가한 `a_aihub_best100_all`은 AI-Hub 선별 MP4 400개(유형별 100개, 원본 Training 포함)이고, `a_aihub_best100_val`은 기존 A tier와 겹치는 시퀀스 12개를 뺀 원본 Validation 117개다. 두 셋은 포함 관계이므로 점수를 합산하지 않는다. `aihub_mixed_pilot_mp2`는 이 영상 8개를 검토된 정상 블박 클립 8개 사이에 삽입한 합성 진단의 입력 목록이다. 영상 파일은 이 폴더에 두지 않는다.

`aihub_mixed_100_v1`은 서로 다른 검토된 C tier 2 정상 블박 100개와 AI-Hub 원본 100개(유형별 25개)를 짝지은 확장 합성 세트다. 삽입 100개와 같은 배경의 정상 대조 100개를 기록하며, 기존 8쌍 파일럿의 배경은 제외한다. 원본 출처, 삽입 구간, 파일 해시를 각 항목에 남긴다.
