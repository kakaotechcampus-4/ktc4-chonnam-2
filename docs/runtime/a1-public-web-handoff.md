# A-1 샘플 진입 Web 연결과 #629 CI 후속

상태: 로컬 미커밋 연결·검증 / 운영 미적용 / 공개 NO-GO. 기준 PR#629 head117bf0ef와 이 뒤의 로컬 변경을 구분한다.

MySQL 23건의 이후 실제 base 대조·최소 수정·재검증은 [MySQL CI 후속](a1-mysql-ci-followup.md)을 참조한다. 아래 미해결 기록은 그 이전 조사 시점의 상태다.

## 이번 변경

- 기본 Web 진입은 서버 GET /public/samples의 목록만 선택한다. 같은 origin의 cookie로 POST /public/session → POST /cases → POST /cases/{id}/official-samples(sample_id만)을 호출한다. localStorage Case ID는 권한으로 사용하지 않는다.
- 샘플 준비는 분석을 발주하지 않는다. 사용자가 설명을 확인하고 분석 시작을 눌러야 기존 START_ANALYSIS를 한 번 보낸다.429/503에서 자동 유료 재시도하지 않고, 결과 불명은 GET/view로 확인한다.
- 준비/시작 중 중복 클릭을 막고 다른 세션의404를 새 세션/임의 업로드로 우회하지 않는다. 삭제202는 DELETING으로 표시하고 명시적으로 재확인한다.200/DELETED 전에는 삭제 완료로 표시하지 않는다.
- 분석 이후 CaseView 기반 결과·후보·다운로드는 기존 ApiFlow를 재사용한다. 초기 GET이 끝나기 전 기존 업로드 화면이 노출되지 않도록 optional intake slot만 추가했다. 기존 ?api의 내부 업로드 UI는 유지하지만 A-1 서버의 업로드/권한 차단을 우회하지 못한다. 개발 proxy는 /public도 같은 API로 전달한다.
- 기본 응답 구조와 식별자를 검사하며 전체 CaseView 계약 validator를 새로 정의한 것은 아니다. 깨진 응답은 web.invalid_response로 처리하고 값을 임의 보정하지 않는다.

## 진행 중 PR과 연결 경계

조회 당시 Web#606 bf609d76/open, Web#621 ec979594/open, Case#616 59184b20/Draft가 진행 중이었다.
UploadScreen·기존 api/client·결과 화면·Case domain·공유 CSS를 이식/수정하지 않았다. ApiFlow는 optional intake3줄 접점만 추가했다.
유민의#606 동의/보관 안내를 샘플 준비·분석 앞에 연결하고, #621 결과/초안 변경과 실제 통합해야 한다.
소연의 same-Connection 권한 경계·삭제 및 #616 Case 변경을 통합 리뷰해야 한다. 현재 Web mocked 검사로 이를 완료했다고 표시하지 않는다.
기존 demo/dev 주소는 유지했다. 공개할 실제 경로·동의/보관 문구·실제 외부 브라우저 검수는 미완료다.

## 입력과 승인 구분

사용자가 지정한1min 폴더의10개 파일은 실제 hash/probe/프레임 읽기로600000ms/244829133B를 확인했다. short는 제외했다.
출처 설명과 실제 확인은 다음과 같이 구분한다. 여기서 상위 폴더는 사용자 지정 `1min` 바로 위의 `synthetic_dashcam_e2e_v3`다.

| 원문 파일·위치 | 실제 문구/필드 | 이번 10개에 적용되는 범위 |
| --- | --- | --- |
| 상위 `README.md:6` | `장시간 탐색`, `1min/`의 1분 MP4 10개, 10분 | 사용자 지정 묶음과 같은 폴더·파일 수 |
| 상위 `manifest.json:4` | `"release_status": "local-only"` | outputs 10개가 모두 `1min/`이며 실제 파일의 이름·SHA256·bytes와 일치. short의 manifest를 대신 읽은 것이 아님 |
| 상위 `README.md:48` | “두 샘플에는 AI Hub 사건 장면과 기존 주행 배경이 포함되어 있어 로컬 검증용으로 보관한다.” | README의 두 샘플은 short와 1min을 가리키므로, 작성자의 설명은 이번 1min 10개에도 적용됨 |
| 상위 `README.md:40`, `manifest.json:100` 이후 | `aihub_mixed_100_v1/` 배경 파일과 hash, v2 사건 파일·hash 참조 | 생성 소재에 대한 로컬 작성 기록. AI Hub 원천 자료·라이선스·권한의 독립 검증 근거는 아님 |

기존 “README와 manifest가 AI Hub 사용을 명시한다”는 표현은 위와 같이 정정한다.
`local-only`는 manifest의 명시적 선언이고, AI Hub 사건 장면 포함은 README 작성자의 설명이다.
manifest의 배경 경로명만으로 배경 전체의 출처나 권한까지 확정하지 않는다.
원천 자료까지의 출처 추적·사용권 확인은 NOT_RUN이다. 이 기록이 곧 공개 불가라는 법적 판정도 아니다.
폴더 지정은 공개/외부 AI 처리/결과 재배포·비식별 승인 완료가 아니다. 실제 권한·예산은 미확정이다.
보호된 로컬 조사 자료에 전체 파일명/순서/hash/bytes/길이와 manifest초안·설치 절차를 보존했다. 제품 repository에 영상을 복사하지 않았다.
manifest초안은 authorization_ref가 빈칸이어서 제품에서 INVALID_MANIFEST로 거부한다. 실제 승인 후 JSON전체SHA를 새로 고정해야 한다.
TEST_ONLY 참조·시험 금액을 운영 승인값으로 사용하지 않는다. 실제 서비스의 필수 값 누락 시 거부 상태는 유지한다.

## #629 CI 결과(기존117bf0ef)

| 항목 | 확보한 결과 | 판정 |
| --- | --- | --- |
| boundary/quality | 성공 | 해당 CI 범위 PASS |
| regression |15232 PASS /2 FAIL /34 SKIP | 실패2개는 업로드 timeout 시험 env의 internal 누락. 로컬 RED403→env한줄 보완 후 timeout2+공개 차단/필수값 거부4 =6 PASS |
| MySQL canonical |1310 PASS /23 FAIL, 전체1333개 실행 | 실패. 취소 측정9/DB observer14. 신규 A-1 MySQL19개는 모두PASS. 실행을 취소하지 않고 완료 원문 확보 |
| strict/실제 보고서 변조 | canonical 실패로 미진입 | NOT_RUN |
| required test | 실패 | 병합 gate 미완료 |

23건은 별도 미해결이다. 정적 대조에서는 새 public tagging 읽기 transaction이 기존 observer 범위와 취소 시험의 첫 commit anchor에 포함되는 문제가 의심된다.
실제 DB의 변경 전후 대조는 NOT_RUN이며 product metric 오류인지 fixture 관측 범위 문제인지 최종 확정하지 않는다. assertion/허용시간을 넓히거나 무시하지 않았다.
이번 CI 결과는117bf0ef의 결과이며 현재 미커밋 env 수정·Web 코드의 원격CI가 아니다. 로컬 canonical 전체를 반복하지 않았다.

## 로컬 검증과 남은 것

- 기존 업로드 timeout2개를 동일403으로 RED 재현. internal 모드만 시험 env에 추가한 뒤6 PASS. 기존 assertion·timeout의 AST 동일을 확인했다. 서버 업로드 차단 코드는 수정하지 않았다.
- 새 Web 정상·429·404·중복 준비·202삭제/재확인과 실제ApiFlow 초기 로딩 검증 포함 Web전체362 PASS,25files. TypeScript/Vite build PASS. 기존 jsdom navigation 미지원 경고가 있으며 실제 브라우저 검증이 아니다.
- 독립 정적 리뷰에서 null catalog·깨진 응답·실제ApiFlow 파일입력 노출을 RED로 확인해 보완했다. 최종 검토 범위 추가 P1/P2 미발견. reviewer가 실행 검증을 대신한 것은 아니다.
- Coarse600초 유지.26분 E2E·#583 구현·운영 DB/서비스 변경·실제 유료 호출·publish·commit/push·외부 게시 없음.
- 실제 HTTPS origin/cookie, 양 API/Worker의 보호된 manifest/policy RO mount, 최종image/config/복구tuple, 공식 권한/예산, #606/#621/#616 통합, 외부 샘플→실제분석→신고영상 다운로드·재생 및 삭제/중단 검증은 NOT_RUN/확인 필요.
- 원본·보호 증거·기존 volume 보존. 로컬 경로 지정/코드 build/기존 장시간 E2E는 운영 등록·공개 완료를 뜻하지 않는다.
