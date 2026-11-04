# 연결 길이 정밀도 최소 재현과 검증 — 2026-11-04

범위: #452 전체 입력 실험의 Recording 연결 전 길이 검사. 시작 revision은
`0598187d015ac32a74f9ac2ca601920e440b34dc`다. 전체 영상·Search·웹 E2E 성공 기록이 아니다.

## 원인과 증거 구분

| 구분 | 확인 내용 |
| --- | --- |
| 운영자 제공 EC2 증거 | 개별 materialization 15개 성공 후 연결 파일 생성 전 `UNSUPPORTED_MEDIA`. DB 저장·재조회와 Search 미도달, provider 호출 0회. 이 문서 작성자의 EC2 재실행 결과가 아님 |
| 직접 로컬 산술 대조 | 보호된 실행 숫자와 실제 전송 placement의 Fraction 합은 각각 `118813/75초`, `396043333/250000초`. 차이는 `1/750000초`, 최대 개별 seam 차이는 약 `333.3334ns` |
| 코드 추적 | `full_plan`은 `format.duration`을 Decimal로 합산한다. 단일 materialization은 실제 frame PTS·duration으로 선택 coverage를 계산하고 해당 span의 Timeline에 투영한다. 연결 검사는 frame 길이 합을 투영 범위의 양 끝 차이와 비교했다 |
| 직접 최소 재현 | 30fps·1프레임 AVI 7개와 각각 `.033333초` placement로 공개 등록→Timeline→해소→준비 경로에서 수정 전 동일한 전체 길이 검사 오류를 재현 |
| 실제 15개 숫자 함수 경계 대조 | 원본 encode 대신 coverage 대역을 넣은 별도 실행. 시작 HEAD 함수는 전체 길이 검사에서 RED, 수정 함수는 연결 도구 실행 직전까지 GREEN. 실제 영상 연결·프레임 수 검증을 대신하지 않음 |

개별 실제 길이와 placement 길이의 차이는 `0` 또는 `±1/3000000초`였다.
이 값들은 마이크로초 단위 최근접 반올림과 정확히 대응한다. 산술 합과 작은 제품 재현으로
해당 표현 차이의 누적이 기존 전체 검사 실패를 일으킴을 확인했다. 단순 이진 float 합산 오차로
설명하지 않는다. 전체 원본에 대한 새 코드의 처리 성공은 아직 확인하지 않았다.

## 수정과 호환성

`MaterializedVideo`에 선택 원본의 정확한 양 끝과 **선택 전 전체 decode coverage의 끝**을
내부 Fraction 증거로 보존한다. 다음 조건을 만족하는 내부 seam만 보존식에 반영한다.

- 왼쪽 span 끝이 등록된 전체 metadata 길이이며 실제 전체 decode 끝까지 선택했다.
- 선택 source frame coverage와 출력 frame coverage가 정확히 같다.
- 실제 끝을 마이크로초 단위로 반올림하면 등록된 길이와 정확히 같다.
- 두 출력의 Timeline 범위가 원본 선택 경계의 정확한 투영과 같다.
- 입력 span의 Timeline 경계가 같고 다음 원본은 source-local 0에서 시작한다.
- 개별 표현 차이는 기존 tick·frame·1마이크로초 제한 안에 있다.

입증된 내부 seam마다 `실제 source 끝 − 등록된 길이`의 **부호 있는 정확한 값**을 합산한다.
`프레임 길이 합 − Timeline 양 끝 차이 − 입증된 합`을 기존 tolerance로 비교한다.
구간 수로 tolerance를 늘리거나 입력·프레임·출력 timestamp·Timeline을 고치지 않는다.
증거가 없으면 기존 전체 비교를 그대로 적용한다.

공개 API·Contract 버전·JSON·DB schema·직렬화 metadata는 바꾸지 않는다. 내부 증거는 영속화하지 않는다.
`timeline_range`는 실제 선택 coverage의 Timeline 투영, `duration_sec`는 출력 MP4의 측정 길이라는
[기존 의미](../local-analysis-source.md#frame-경계와-metadata)를 유지한다.
다중 IncidentClip도 같은 연결 함수를 사용하므로 관련 회귀에 포함했다. 기존 단일 materialization의
PTS·duration 허용치, 연결 출력 frame 수·순서·packet·strict decode·원본 identity 검사는 유지한다.

## RED → GREEN과 부정 대조

| 직접 검증 | 결과 |
| --- | --- |
| 최초 합성 공개 재현 | 수정 전 `1 FAIL, 1 PASS`; 실패 위치는 기존 `multi_analysis.py:57` |
| 최종 신규 테스트 — Windows / FFmpeg 9.0.1 | `29 PASS`: 무미디어 경계 26개, 합성 산술 1개, 실제 합성 연결 1개, header 변조 거부 1개 |
| 최종 관련 회귀 — Linux / Python 3.12.16 / FFmpeg 8.1 | `195 PASS, 1 SKIP`. 신규 테스트·다중 분석·다중 IncidentClip·혼합 time base·VFR·frame duration 6개 파일. SKIP은 실제 영상 pair opt-in 미제공 |
| 부정 대조 | gap·overlap·근거 없는 누적 이동·경계/전체 끝 증거 부재·metadata 변조·부분 endpoint·frame 길이 변조·누락·중복·source coverage 불일치·더 미세한 clock에서 거부 |
| 실제 짧은 연결 | 전체 7프레임의 개수와 각 PTS·길이 `1/30초`를 확인하고 strict decode, provenance 순서, 원본 fingerprint 유지, 작업 디렉터리 정리 확인 |
| 독립 reviewer 1차 직접 실행 | 신규 26개 PASS. 2프레임 AVI의 header 길이만 1프레임으로 변조한 7개 입력이 허용되는 결함을 직접 재현 |
| 지적 수정 직접 검증 | 같은 변조 입력 거부 테스트가 수정 전 `DID NOT RAISE`로 RED. 전체 decode 끝 증거를 추가한 후 최종 신규·Linux 회귀에서 GREEN |
| 추가 focused 회귀 | 내부 prepared metadata·전체 입력 계획·첫 통합 Contract 관련 `52 PASS`. 실제 MySQL 저장·재조회 검증은 아님 |
| 최종 Runtime quality | Ruff 통과, Linux·Windows 대상 mypy 각각 89개 파일 오류 없음 |
| 최종 boundary·Contract·diff | 경계 위반 0건, Contract 구조 62·JSON 26·의미 104 검사 통과, 수정 문서 로컬 링크와 `git diff --check` 통과 |
| 동일 reviewer 재확인 | 신규 29개와 diff 검사를 독립 직접 실행. 전체 decode 끝 조건으로 P2 해소, 추가 확정 결함 없음. Linux 회귀·추가 52개·품질·boundary·Contract 결과는 작성자 로그를 읽은 증거 검토이며 reviewer의 직접 실행과 구분 |

첫 실행의 pytest 임시 디렉터리 권한 오류는 재현 RED에 포함하지 않았다. 전용 scratch basetemp로
재실행해 제품 오류를 관측했다. boundary 검사의 Windows 출력 인코딩 오류도 별도로 구분하고
UTF-8로 재실행했다. 기존 Linux 이미지에 pytest가 없어 로컬 순수 Python 테스트 의존성만
읽기 전용 제공했으며 다운로드·이미지 빌드·DB 실행은 하지 않았다.

## 검증 한계와 EC2 재검증 전 조건

- 전체 테스트·MySQL 저장/재조회·실제 15개 원본 재연결·Search/provider·Package READY·신고영상 다운로드·웹 업로드 E2E는 **미실행**이다.
- 새 패키지는 아직 만들지 않았다. 향후 별도 승인 범위에서 미커밋 수정이 포함된 실행물을 만들고 revision과 실제 변경분·파일 hash를 명확히 결속해야 한다. 기존 시작 HEAD만으로 수정 포함을 표현하면 안 된다.
- 원본 15개·전송 manifest·placement·정확한 요청 끝을 유지하고, 새 내부 전체 decode 끝 증거가 각 seam에서 성립하는지 실제 재검증해야 한다. 현재 숫자 경계 대조는 전체 끝을 대역으로 제공한 검증이다.
- 기존 EC2의 자원·서비스 복구·잠금·정리 조건과 사용 가능한 실측 예산을 다시 확인한 뒤 Recording 연결→DB 저장·fresh read→Search→Package·다운로드를 단계별로 구분해야 한다. 이번 결과로 장시간 성능이나 전체 완료를 추정하지 않는다.

## 자원 보존

기존 로컬 Linux 이미지를 재사용했다. 검증 전 Linux 여유 메모리는 약 6.1GB, Windows 여유 메모리는
약 5.8백만 KiB, C 드라이브 여유는 약 10.2GB였다. 실행 컨테이너의 실제 한도는
메모리·메모리와 swap 합계 각각 `805306368B`, CPU 1개, 네트워크 `none`이었다.
저장소는 읽기 전용으로 제공하고 임시 파일은 한도 256MiB의 `/tmp`에 생성했다.
DB·새 volume·network·이미지는 만들지 않았으며 검증 컨테이너는 자동 삭제했다.
원본·기존 보호 증거·보호 volume 3개·공유 이미지와 캐시는 수정하지 않는다.
이번 작업의 로그와 수치 요약은 ignored scratch에 보존하고 합성 미디어·복사한 테스트 의존성만 정리한다.

종료 확인: 이번 작업 소유 컨테이너 잔여 0, 작성자 임시 디렉터리 8개와 reviewer 전용
임시 디렉터리 2개 정리 완료. 정리 전에 절대경로가 해당 저장소 scratch 아래인지 확인했다.
원본 파일 15개 존재와 보호 volume 3개 유지 확인. 기존 보호 증거에는 쓰지 않았으며
산술 대조 전후 사용한 증거·전송 manifest의 hash도 같았다. 변경 파일 5개는 미스테이징·미커밋이다.
