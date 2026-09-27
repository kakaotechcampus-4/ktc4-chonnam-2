# Search 전용 영상 판단 근거 출력

상태: 로컬 진단용 `search-decision-trace/v1`. 공개 Search 결과나 검증된 증거가 아니다. [결정과 실험 순서](../decisions/decision-trace-2026-09-26.md)를 따른다.

## 실행

저장소 루트에서 Python 3.12 이상, `openai`, `ffmpeg`/`ffprobe`를 준비한다. `PYTHONPATH=src`로 다음 모듈을 실행한다. PowerShell에서는 먼저 `$env:PYTHONPATH='src'`를 설정한다.

```text
python -m daesingo.search.diagnostic_cli --manifest .superpowers/seven-video-manifest.json --profile diagnostic-v1 --env-file .env --timeout-sec 180
```

`--profile p3`는 기존 출력 형식의 비교군이다. 운영 설정에 새 prompt 선택 옵션을 추가하지 않는다. `--provider-fixture <JSON>`는 네트워크 없이 실제 미디어 준비와 CLI 출력을 확인하며, 결과에 `mode=FIXTURE`를 표시한다. 실제 호출은 `mode=LIVE`다.

Manifest는 로컬 파일이며 정답 시각을 담지 않는다. source 상대 경로의 기준은 manifest 폴더다. 각 영상은 60초 이내여야 한다. 중복 case_id/유형, 실제 길이 차이, 입력 용량, 출력 폴더의 Git ignore를 호출 전에 확인한다.

```json
{"cases":[{"case_id":"clip_01","source":"../local-video.mp4","duration_sec":20.025,"event_types":["SOLID_LINE_LANE_CHANGE"]}]}
```

형식의 필수 값과 전체 스키마는 `src/daesingo/search/decision_trace.py`, 실행 기록은 `diagnostic_models.py`가 소유한다. 모델 출력에 실행 명령을 포함해도 데이터로만 저장한다.

## Coarse

기존 p3 `candidates[]`의 `event_type`, `span`, `at_sec`, `observed`, `score`에 `candidate_reason`을 추가한다. `window_reviews[]`는 제공 영상의 0초부터 연속된 5초 구간 × 요청 사건 유형마다 작성한다. 마지막 구간은 남은 길이만 사용한다. 후보가 없어도 반환한다.

| 필드 | 의미 |
| --- | --- |
| start_sec, end_sec | 제공 영상 시작 기준의 검토 구간 |
| event_type | 요청한 시각 사건 유형 |
| decision | CANDIDATE / NO_CANDIDATE / UNCERTAIN |
| observations | 직접 보았다고 보고한 움직임·선·신호·탑승자 가시성 |
| reason | 후보 선택 또는 무후보 이유 |
| limitations | 가림·해상도·시각 추정의 한계 |

구간 누락·중복은 `TRACE_WINDOW_COVERAGE`로 기록한다. 그 응답도 로컬에서 읽을 수 있다. 완전한 목록이 곧 정확한 관찰을 뜻하지 않는다.

## Fine

기존 p3 `verification`, `visual_event_type`, `target`, `primitives`, `temporal_facts`, `uncertainties`를 유지하며 다음을 추가한다.

| 필드 | 의미 |
| --- | --- |
| decision_reason | 결론을 지지·반박한 관찰과 판정을 막은 불확실성 요약 |
| decision_basis[].criterion | 사건별 확인 항목 이름 |
| observation | 직접 보인 사실 또는 확인하지 못한 사실 |
| at_offset_ms | 제공된 **잘라낸 clip의 0초** 기준 관찰 시각; 특정 불가하면 null |
| limitation | 해당 관찰 한계; 없으면 null |

확인 항목은 `CHECKLISTS`를 그대로 프롬프트에 전달한다. 신호: 대상·이동 방향·관련 신호·침범 전/시점 신호·경계·통과·시간 순서. 중앙선: 대상·도로 방향·중앙선 식별·차량 전/후 위치·접촉/침범·지속·도로 형태. 실선: 대상·원래 차로·횡이동·경계 식별·횡단 시점 선 종류·횡단·도착 차로·시간 순서. 안전모: 이륜차·탑승자 연관·역할·머리 가시성·착용/미착용·부재 판정 가시성·관찰 일관성.

원본 시각은 `prepared_origin_start_sec × 1000 + at_offset_ms`로 읽는다. 준비 clip의 길이·끝 경계도 기록한다. 확인 항목 누락·중복과 시간 초과는 issue code로 남기되 p4 의미 검증처럼 설명을 버리지 않는다. 음수 시각·p3 판정/사건 유형 불변조건 위반 같은 기본 형식 오류는 `PROVIDER_PAYLOAD` 실패로 기록한다. 실패 응답 원문은 저장하지 않는다.

## 기록 읽기

실행기가 생성하는 전체 JSON/Markdown은 Git 제외 `.superpowers/decision-trace/trace_<UUID>.*`에 저장한다. 이번 7영상 실험의 저장소 보관 범위는 [보관 결정](../decisions/decision-trace-2026-09-26.md#보관과-전환)을 따른다. 실행 조건에는 model, 모드, profile, HEAD SHA, 미커밋 Search 코드 fingerprint, config fingerprint, fps/해상도/padding/retry/reasoning/예산/단가가 있다. 각 호출에는 prompt version/fingerprint, 준비 영상 해시·바이트·원본 범위, latency, usage와 응답 또는 고정 실패 코드가 있다. `input_sha256`은 원본 영상, `prepared_media_sha256`은 실제 provider에 전달한 미디어다.

코드 fingerprint는 Search `.py`와 프롬프트 원문 파일명·바이트를 정렬하여 SHA-256으로 계산한다. 템플릿 fingerprint는 렌더링 전 프롬프트 기준이다. 서로 다른 후보 clip 자체를 동일 입력이라고 주장하지 않는다.

stdout은 요약만 출력한다. 종료 코드 0은 호출·진단 구조 점검 통과, 1은 실행 중 실패 또는 진단 issue, 2는 호출 전 입력 조건 실패다. 코드 0도 검출 정답이나 설명의 신뢰도를 보장하지 않는다. 오류 호출 사용량 미보고는 unknown, 단가 미설정 비용은 null이다. 실행 예산은 영상마다 적용하고 진단 CLI는 재시도를 0회로 고정한다.
