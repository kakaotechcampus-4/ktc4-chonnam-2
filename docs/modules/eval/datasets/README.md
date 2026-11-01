# eval/datasets

평가용 manifest, split/locked-test 정책, 정답지 구성 원칙에 관한 문서를 둔다. 실제 민감 원본 데이터 자체를 문서 폴더에 넣는다는 의미는 아니다.

## 현재 데이터셋 (2026-10-30 확인)

| 셋 | 입력과 규모 | 정답 | 평가 용도 |
| --- | --- | --- | --- |
| `a_aihub` | AI-Hub 프레임 시퀀스 120개, 4종 × 30 | 유형 · 일부 대상 bbox | A tier 분류 개발 평가 |
| `a_aihub_extra` | 별도 AI-Hub 프레임 시퀀스 120개, 4종 × 30 | 유형 · 일부 대상 bbox | A tier 추가 개발 표본 |
| `ab_mixed` | `a_aihub` 120개 + 검토된 YouTube 정상 클립 30개 | 4종 + `NONE` | 5×5 혼동행렬. 입력 매체가 서로 달라 해석 시 출처를 구분 |
| `a_aihub_best100_all` | 새 AI-Hub MP4 선별본 400개, 4종 × 100, 재생 길이 약 45.6분 | 영상별 위반 유형 | 전체 개발 진단. 원본 Training 271개 포함, 기존 A tier와 12개 중복. [S1/S2/S3 비교](../experiments/2026-10-31-aihub-video-search-points.md) |
| `a_aihub_best100_val` | 새 AI-Hub MP4 선별본 중 원본 `Validation` 117개, 약 16.0분 | 영상별 위반 유형 | 영상 전체에서 최상위 후보 유형을 뽑는 별도 분류 개발 평가. [S1/S2/S3 비교](../experiments/2026-10-31-aihub-video-search-points.md) |
| `b_youtube` / `b_youtube_m4` | 실제 주행 영상의 약 1분 클립 123개 / 179개 | 채점 사건 10건 / 16건, 검토된 정상 클립 113개 / 163개 | 후보 탐색·오탐·Fine 비교. `m4`는 확장판이므로 두 셋을 합산하지 않음 |
| `ctier2` / `ctier3` | 실제 블박 클립 149개 / 8개 | 채점 사건 1건 / 3건, 정상 클립 148개 / 6개 | 정상 구간 오탐 진단과 소수의 위반 사례 확인 |
| `aihub_mixed_pilot_mp2` | C tier 2 정상 블박 8개에 AI-Hub 영상 8개를 삽입한 합성 영상 + 정상 대조 8개 | 삽입 구간 · 유형 | 블박 사이 탐색 개발 진단. [10/30 결과](../experiments/2026-10-30-aihub-best100-video-and-mixed.md) |
| `aihub_mixed_100_v1` | 서로 다른 검토된 C tier 2 정상 블박 100개에 AI-Hub 영상을 4종별 25개씩 삽입한 영상 100개 + 같은 배경의 정상 대조 100개 | 삽입 구간 · 유형 · 원본 출처 | 8쌍 파일럿을 확장한 합성 탐색 개발 진단. Validation 84개 · Training 16개. [S1/S2/S3 비교](../experiments/2026-10-31-aihub-video-search-points.md): 검증 일치 45/37/78, 정상 대조 OBSERVED 8/9/29 |
| `private_aihub172_*` | 번호판 crop·차량 프레임 로컬 표본 | 문자 · 차량 bbox | readout 인식·검출 평가. private root에만 저장 |
| `mock_pack` | 계약 fixture | fixture에서 파생한 정답 | 파이프라인 연결 확인. 성능 근거 아님 |
| `locked_test` | 아직 목록 없음 | 없음 | 최종 제품 성능 주장을 위한 실제 장시간 블박 평가셋 예정 |

수치의 정본은 각 `eval/manifests/<이름>/`의 manifest·GT다. 여기의 표본 수는 서로 겹칠 수 있으므로 합계가 독립 영상 수를 뜻하지 않는다. 실행 기록과 점수는 `docs/modules/eval/experiments/` 및 `eval/results/`에서 확인한다.

### 새 AI-Hub 선별 영상의 역할

로컬 원천은 `D:/카테캠/데이터/AIHub_traffic_videos_best_100_each/manifest.csv`와 같은 폴더의 MP4다. 목록에는 **4종별 100개, 합계 400개**가 있고 원본 분할은 `Training` 271개 · `Validation` 129개다. 전체는 `a_aihub_best100_all`로 고정했다. 기존 `a_aihub`·`a_aihub_extra`와 겹치는 시퀀스 12개는 모두 Validation에 있어, 겹침을 뺀 117개(신호 37 · 중앙선 36 · 실선 35 · 안전모 9)를 `a_aihub_best100_val`로 따로 고정했다. 영상은 저장소에 복사하지 않고, 파일별 SHA-256을 manifest에 기록했다.

- 목록의 라벨은 **영상별 위반 유형**이다. 위반 onset·끝 시점, 정상 영상, 대상 bbox 정답이 없다. 따라서 이 목록만으로 Recall@3의 ±2초 매칭, 정상 영상 오탐률, target correctness를 계산하지 않는다.
- 원본 JPEG 프레임으로 만든 영상은 **재생용 10 fps**다. 재생 길이는 실제 촬영 시간이 아니다. 길이당 비용·FP/hour를 실제 블박과 같은 시간 단위로 해석하지 않는다.
- 긴 길이·대상 가시성·밝기·선명도로 선별한 400개는 무작위 대표 표본이 아니다. 117개도 원본 Validation의 일부일 뿐, 모든 모델에 대해 학습 비중복이 증명된 locked test가 아니다. 특히 안전모는 9개라 유형별 수치가 불안정하다.
- 실제 블박 영상 사이에 삽입한 혼합 영상은 **개발용 탐색 진단**으로 별도 관리한다. 삽입 시작·끝, 원본 시퀀스 ID, 배경 영상 ID, 인코딩·배속·seed를 기록하고, 정상 배경 구간을 검토한 뒤 채점한다. 삽입 경계와 화면 특성 차이가 탐색 단서가 되므로 결과를 실제 블박 성능으로 일반화하지 않는다.

최종 제품 성능은 `locked_test`의 **편집하지 않은 실제 장시간 블박 영상**에서만 주장한다(`initial-evaluation-plan.md` §3).
