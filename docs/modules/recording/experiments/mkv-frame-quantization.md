# MKV millisecond frame coverage 조사와 제한적 정규화

## 원인 조사

동일 원본의 MOV·MKV를 Python 3.12.14 / FFmpeg·ffprobe 9.0.1로 조사했다.
원본 두 파일의 SHA-256·크기·mtime은 조사 전후 동일했다.

| 관측 | MOV | MKV |
| --- | --- | --- |
| time_base | 1/30013 | 1/1000 |
| frame 수 | 601 | 601 |
| 인접 PTS 간격 | 1000 tick × 600 | 33 tick × 409, 34 tick × 191 |
| 관측 duration | 1000 tick × 601 | 33 tick × 601 |
| 다음 PTS − 현재 PTS − duration | 0 tick × 600 | 0 tick × 409, +1 tick × 191 |
| PTS 누락 / best_effort_timestamp와 불일치 | 0 / 0 | 0 / 0 |

MKV의 모든 상대 PTS는 MOV 상대 PTS를 millisecond로 반올림한 값과 일치했다.
최대 시각 차이는 0.49968347049611833 MKV tick이다.
MOV를 임시 공간에서 H.264/libx264·veryfast·CRF23·160×90·audio off·passthrough로
재인코딩한 MKV도 같은 분포를 보였다. 이 재인코딩은 warning 로그가 0 bytes였고
unset timestamp 경고도 없었다. 생성 비교 파일은 조사 종료 시 정리했다.

따라서 관측한 1-tick 불일치는 정상 재인코딩에서도 재현되는 time-base 양자화다.
과거 원본 생성 당시의 unset timestamp 경고 자체가 무해했다는 일반 보증은 아니다.
현재 decoded frame 시각과 비교 파일을 근거로 이번 coverage 패턴을 분류했다.

## 허용 조건

- 기존 정확한 연속 coverage 경로는 유지한다.
- 불일치가 있는 source는 Matroska이며 time_base가 정확히 1/1000이어야 한다.
- 최소 3 frame, 엄격히 증가하는 PTS, 일정한 frame 길이와 양의 duration 근거가 필요하다.
- 모든 PTS가 하나의 일정 주기를 nearest-tick으로 반올림한 결과와 양립해야 한다.
  각 frame의 주기 허용 구간을 Fraction으로 교차하며 공통 구간이 없으면 거부한다.
  ffprobe의 추정 fps를 길이로 복사하거나 새 fps를 생성 설정에 적용하지 않는다.
- 개별 중간 frame의 `next_pts - pts - observed_duration`은 절댓값 1 tick 이하여야 한다.
- 위 조건을 통과하면 PTS는 그대로 두고 중간 coverage만 다음 관측 PTS까지 정규화한다.
  마지막 frame duration은 관측값 그대로 사용하며 근거가 없으면 계속 실패한다.

gap, 역전·중복, 1 tick 초과 차이, 양자화 패턴에 맞지 않는 단발 1-tick gap은 거부한다.
거친 time_base에서 1 tick을 큰 시간 허용치로 확대하지 않는다. VFR 등 다른 패턴으로
허용을 일반화하지 않는다. timestamp만으로 같은 패턴을 흉내 낸 모든 입력 이상을
구별할 수는 없으므로, 이 검사는 영상 내용의 무결성 보증을 대신하지 않는다.

## 출력 검증

실제 MKV 인코딩 결과 MP4에도 duration/다음 PTS가 ±1 tick 어긋나는 사례가 있었다.
일반 MP4 입력에는 source 완화 규칙을 적용하지 않는다. 출력 정규화는 검증된
millisecond Matroska에서 선택한 frame 수 및 상대 PTS와 **정확히 일치**할 때만 허용한다.
출력 역시 중간 frame 차이가 최대 1 tick이어야 하며 마지막 duration 근거가 필요하다.
기존 codec·해상도·frame 수·duration·bytes·faststart·원본 전후 검사와 failure code는 유지한다.

## 검증 범위

최소 양자화 fixture는 수정 전 실패를 확인했다. 양·음 1 tick, legacy pkt_duration,
실제 gap·중복·역전·마지막 duration 누락·출력 PTS 불일치를 검사한다.
합성 30fps H.264 MKV는 공개 등록 → Timeline → resolve_span → AnalysisSource/open →
IncidentClip → Frame 읽기와 원본 불변·cleanup을 검사한다.
실제 MOV/MKV 비교는 동일 analysis 0–20초, incident 1–2초 조건으로 수행한다.
요청 범위가 아닌 frame 경계의 실제 범위와 출력 duration을 계속 기록한다.

실제 두 Benchmark 모두 실패 없이 relative-only FALLBACK으로 완료됐고 두 resolve는
COMPLETE였다. SHA-256·크기·mtime 불변 검사를 모두 통과했다.

| 결과 | MOV | MKV |
| --- | --- | --- |
| AnalysisSource 실제 범위(초) | 0–20.024655982407623 | 0–20.024 |
| AnalysisSource duration / bytes | 20.024656 / 3580717 | 20.024 / 3581197 |
| IncidentClip 실제 범위(초) | 1.0328857495085464–2.0324526038716555 | 1–2.032 |
| IncidentClip duration / bytes | 0.999567 / 280648 | 1.031 / 290181 |
| 읽은 frame offset(초) | 1.0328857495085464 | 1.0 |

millisecond 반올림은 요청 경계에서 frame 선택을 바꿀 수 있다. 두 컨테이너의 결과를
같은 frame·같은 bytes라고 주장하지 않는다. MKV IncidentClip의 source coverage 1.032초와
출력 format duration 1.031초의 차이는 기존 출력 검증 허용 범위 내이며, 둘을 동일한 값으로
덮어쓰지 않는다. 마지막 output frame 길이는 실제 관측값을 유지한다.

Contract·공개 capability·failure taxonomy·encoder profile은 변경하지 않는다.
이 결과는 해당 도구 버전과 비교 영상에 대한 검증이며 모든 MKV/VFR 호환성을 뜻하지 않는다.
