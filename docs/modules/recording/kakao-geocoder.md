<a id="kakao-reverse-geocoder-adapter"></a>

# Kakao 역지오코딩 adapter

`recording.kakao_geocoder`는 provider 내부 adapter다. RecordingService capability,
Canonical Contract, 기존 GPS Observation은 변경하지 않는다. 최종 Owner·composition
root 배선과 Case/Evidence 표시 주소 선택은 별도 합의 대상이다.

```python
from daesingo.recording.kakao_geocoder import KakaoReverseGeocoder

# composition root가 획득한 값으로 주입한다. 여기서 환경 파일/Secret을 읽지 않는다.
geocoder = KakaoReverseGeocoder(api_key=injected_key, timeout_sec=injected_timeout)
result = geocoder.reverse_geocode(validated_gps_observation)
```

검증된 OK GPS만 WGS84로 요청한다. 입력 GPS는 재검증하며 lon → x, lat → y로
매핑한다. timeout은 필수 양수·유한 입력이며 socket 작업 timeout이다. 전체 실행
deadline이나 재시도 수치를 확정하지 않는다. retry/cache/TTL/provider fallback은 없다.

기본 의존성에는 공용 HTTP client가 없다. lock의 httpx/requests는 optional dependency
경로에 있으므로 이를 필수 설치로 가정하지 않는다. 표준 라이브러리 HTTPSConnection을
사용해 추가 dependency 없이 TLS 검증을 수행하며 redirect는 따라가지 않는다.
성공·실패·timeout에서 연결을 닫는다.

`KakaoGeocoderResult`는 내부 결과이며 status는 OK/SKIPPED/FAILED다. `address`(지번)와
`road_address`(도로명)를 별도 보존한다. 각 주소의 `address_name`과 문자열 상세 필드는
immutable 값으로 보존하며 어느 주소도 최종 표시값으로 선택하지 않는다. 도로명 주소가
없어도 지번 주소가 유효하면 OK다. 전체 응답 원문은 결과에 포함하지 않는다.

| 내부 failure | 의미 |
| --- | --- |
| INVALID_INPUT | Observation·좌표 검증 실패, 호출 없음 |
| GPS_NOT_OK | 유효한 non-OK Observation, SKIPPED·호출 없음 |
| TIMEOUT | 연결·읽기 timeout |
| AUTHENTICATION | HTTP 401/403 인증·권한 거부 |
| RATE_LIMIT | HTTP 429 quota/rate limit |
| SERVER_ERROR | HTTP 5xx |
| HTTP_ERROR | 그 외 비정상 HTTP status, redirect 포함 |
| TRANSPORT_ERROR | 연결/TLS/HTTP transport 실패 |
| INVALID_JSON | JSON·문자 인코딩 파싱 실패 |
| INVALID_SCHEMA | 응답 shape/type/count 불일치 또는 유효한 주소 없음 |
| EMPTY_RESULT | documents=[] 및 total_count=0 |

이 이름들은 **공개 failure taxonomy가 아니다**. HTTP 오류 body는 해석·보관하지 않으며
오류 응답 문구로 주소를 추정하지 않는다. 어떤 실패도 원래 GPS를 변경하지 않는다.

adapter는 로그를 출력하지 않는다. 키·좌표·응답·원본 예외를 결과에 포함하지 않으며
adapter/result/address의 repr도 민감한 값을 출력하지 않는다. Consumer와 composition
root 역시 입력 Observation, 주소 details, HTTP 요청/메모리 dump를 로그에 남기지 않아야 한다.

검증은 fake HTTPS connection을 통한 무네트워크 테스트다. 실제 키 등록·API 호출은
수행하지 않았다. 따라서 provider 결정 문서의 실제 좌표 1건 검증·배포 Secret 주입 Gate는
완료로 간주하지 않는다. 실제 GPS의 좌표계/출처 신뢰성 검증도 adapter의 역할이 아니다.

참조: [provider 결정](decisions/gps-reverse-geocoder-provider.md),
[Runtime 주입 경계](../../runtime/runtime-tech-spec.md#151-module--provider-configuration-주입-경계),
[Kakao 공식 규격](https://developers.kakao.com/docs/ko/local/dev-guide#coord-to-address)
(2026-10-05 확인).

<a id="operator-live-geocoder-20261101"></a>

## 2026-11-01 — 운영자 실제 API 호출 확인

위 무네트워크 검증 설명은 adapter 개발 당시의 기록으로 보존한다. 아래는 이후
운영자가 직접 실행하고 대화에 공유한 출력에 근거한 후속 기록이다. 에이전트가
실제 API를 독립 호출하거나 원격 상태를 재검증한 결과가 아니다.

### 실행 범위

- 로컬 Windows PowerShell에서 기존 `scenario_happy_001`의 Mock GPS 관찰값을 사용했다.
- 기존 `KakaoReverseGeocoder`에 키를 주입해 실제 Kakao API를 1회 호출했다.
- REST API 키는 숨김 입력했으며 시험 runner는 키를 파일·로그에 기록하지 않는다.
- 이 시험의 socket timeout 인자는 10초다. 운영 timeout 정책의 확정값은 아니다.
- 실제 사용자 영상의 촬영 좌표를 추출하거나 사용한 시험이 아니다.

### 운영자가 공유한 실행 결과

```text
INPUT_KIND=MOCK_GPS
STATUS=OK
FAILURE=NONE
ADDRESS_PRESENT=True
ROAD_ADDRESS_PRESENT=False
GPS_UNCHANGED=True
```

Mock GPS 입력에 대한 실제 API의 지번 주소 반환과 입력 관찰값 유지를 확인했다.
도로명 주소 부재만으로 실패로 판정하지 않는다. 키·좌표·주소 원문은 기록하지 않는다.
요청·응답 원문이나 비공개 실행 자료를 저장소에 추가하지 않는다.

이 기록 준비 과정에서 에이전트가 수행한 검사는 시험 runner의 대역 실행이며,
실제 호출 증거와 구분한다. 앞선 `python -c` 방식은 키 입력 전 SyntaxError로
중단됐고, 위 성공 출력은 스크립트 파일 방식으로 운영자가 다시 실행한 결과다.

### 이번 시험에서 미검증 — NOT_RUN

- 실제 블랙박스 GPS 추출, 좌표계·출처 신뢰성 및 사건 시점·좌표 매핑
- EC2 Secret 주입과 운영 composition 연결
- Case/Evidence/Web의 주소 저장·표시 및 소비 정책

Mock 관찰값으로 adapter의 실제 주소 변환 경로를 확인한 것이며, 실제 영상 GPS
연동 완료나 provider 결정 문서의 구현 Gate 전체 충족으로 해석하지 않는다.
