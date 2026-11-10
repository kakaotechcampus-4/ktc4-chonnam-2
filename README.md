<div align="center">

# 대신고 · Daesingo

### 기억나는 장면을, 신고할 수 있는 자료로.

블랙박스 영상에서 교통위반 장면을 찾고<br>
번호판·시각·증거 영상을 모아 신고자료를 준비하는 AI 서비스

[**서비스 체험하기 ↗**](https://daesingo-ktc4.duckdns.org/) · [**평가 결과**](#평가-결과) · [**개발 환경**](docs/getting-started.md) · [**문서 모음**](docs/README.md)

![React](https://img.shields.io/badge/React_19-149ECA?style=flat-square&logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white)
![Python](https://img.shields.io/badge/Python_3.12+-3776AB?style=flat-square&logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL_8.4-4479A1?style=flat-square&logo=mysql&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=flat-square&logo=docker&logoColor=white)

카카오테크 캠퍼스 4기 · 전남대학교 2팀

</div>

---

## 목차

[서비스 소개](#서비스-소개) · [주요 기능](#주요-기능) · [공개 체험](#공개-체험) · [아키텍처](#아키텍처) · [기술 스택](#기술-스택) · [평가 결과](#평가-결과) · [빠른 시작](#빠른-시작) · [팀](#팀)

## 서비스 소개

> “앞차가 실선을 넘어왔는데, 영상에서 그 장면을 다시 찾으려니 막막해요.”

위반을 목격한 뒤 신고하려면 긴 블랙박스 영상을 되돌려 보고, 차량 번호와 발생 시각을 확인하고, 증거 구간과 신고 내용을 직접 준비해야 합니다. **대신고는 신고 의향이 있는 운전자가 이 준비 과정을 끝낼 수 있도록 돕습니다.**

기억나는 시간·차량·상황·장소를 입력하면 AI가 단서를 정리해 장면을 탐색합니다. 사용자는 후보와 근거를 확인하고 필요한 정보를 보완한 뒤, 준비된 자료를 안전신문고에 직접 제출합니다.

| 찾기 | 확인하기 | 준비하기 |
| :--- | :--- | :--- |
| 기억나는 단서로 영상 속 사건 후보 탐색 | 후보 영상·번호판·시각과 출처 확인 | 사건 전후 영상·이미지·신고 내용 준비 |

**지원 유형:** 신호위반 · 중앙선 침범 · 진로변경(백색 실선 침범) · 이륜차 안전모 미착용

## 주요 기능

### 01. 영상과 기억나는 단서 입력

블랙박스 파일을 올리고 기억나는 상황을 자연어로 적습니다. 시간·차량·상황 단서를 구조화하고 탐색 범위를 계산해, 사용자가 영상을 직접 훑는 작업을 줄입니다.

### 02. 사건 후보 탐색과 근거 확인

넓은 범위에서 사건 후보를 찾는 **1차 탐색(Coarse)**과 선택한 장면을 자세히 확인하는 **정밀 검증(Fine)**을 나눴습니다. 상위 후보를 카드와 영상으로 비교하고, 다른 후보를 선택하거나 단서를 고쳐 다시 탐색할 수 있습니다.

### 03. 번호판·시각 확인과 사용자 보정

번호판이 잘 보이는 프레임을 골라 OCR을 수행합니다. 시각과 위치는 출처를 함께 표시하고, 불확실한 값은 사용자가 확인·수정할 수 있게 합니다. **읽지 못한 값을 임의로 채우지 않습니다.**

### 04. 신고자료 생성과 안전신문고 연결

파일 경계에 걸친 사건도 전후 구간을 연결해 신고영상을 준비합니다. 신고 내용 복사, 영상·이미지 다운로드, 안전신문고 이동까지 이어집니다. **법적 위반 여부의 최종 판단과 실제 신고 제출은 사용자가 직접 합니다.**

화면 흐름과 예외 처리는 [사용자 흐름](docs/product/core-user-flow.md), 지원 범위는 [제품 명세](docs/product/product-spec.md)에서 확인할 수 있습니다.

## 공개 체험

**[대신고 열기](https://daesingo-ktc4.duckdns.org/)** · Desktop Web

1. 별도로 제공받은 공식 3분 또는 10분 ZIP의 압축을 풉니다.
2. 같은 묶음의 MP4를 하나 이상 올립니다. 합계 **10분까지** 분석할 수 있습니다.
3. 상황을 입력하고 분석한 뒤, 후보와 신고자료를 확인합니다.

공개 체험은 공식 샘플의 파일 크기와 SHA-256을 확인하며, 임의 사용자 영상은 받지 않습니다. 로그인 없이 이용하고 체험을 시작한 브라우저 세션에서 결과를 조회·다운로드합니다. 체험 시작 24시간 후부터 자동 정리 대상이므로 필요한 결과는 미리 저장해 주세요.

공식 10분 묶음의 업로드부터 신고영상 생성·다운로드까지 확인한 배포 기록은 [최종 AWS 공개 운영 인계](docs/runtime/a1-public-readiness.md#2026-11-10-최종-aws-공개-배포)에 있습니다.

## 아키텍처

**모듈형 모놀리스 + API·Worker 분리**로 구성했습니다. API는 사용자 요청과 결과 조회를 담당하고, 시간이 걸리는 영상 분석·OCR·파일 생성은 DB Queue를 통해 Worker가 실행합니다.

| 계층 | 구성 | 역할 |
| --- | --- | --- |
| 화면 | React Web | 서버가 제공한 `CaseView`로 진행 상태와 결과 표시 |
| 요청·진행 관리 | FastAPI · `case` | 명령 처리, 사용자 선택, 작업 요청, 부분 재실행 |
| 분석·미디어 처리 | Worker · `search` · `readout` · `recording` | 장면 탐색, OCR, 프레임 추출, 영상 생성 |
| 신고자료 구성 | `evidence` | 관찰 결과와 사용자 확인을 구분하고 신고요건·자료 구성 |
| 저장·실행 기반 | MySQL 8.4 · DB Queue · media volume | 도메인 데이터, 작업 실행 상태, 원본·파생 파일 관리 |
| 오프라인 평가 | `eval` | 예측 저장과 채점 분리, 동일 정답지로 설정 비교 |

### 설계에서 중요하게 본 세 가지

- **관찰과 확정 분리:** AI가 관찰한 결과와 사용자가 확인한 값을 구분해, 불확실한 정보가 확정값으로 바뀌지 않도록 했습니다.
- **수정한 부분부터 다시 실행:** 사용자 보정과 후보 변경을 `case`가 관리하고, 필요한 작업을 다시 요청합니다.
- **제품과 평가 분리:** 제품 모듈은 평가 코드를 참조하지 않습니다. 저장한 예측 결과를 별도 채점기로 평가합니다.

[모듈 경계와 계약](docs/architecture/module-architecture.md) · [Runtime 설계](docs/runtime/runtime-tech-spec.md) · [논리 ERD](docs/architecture/erd-draft.md)

## 기술 스택

| 영역 | 사용 기술 |
| --- | --- |
| Frontend | React 19 · TypeScript · Vite 6 · CSS · Vitest · Playwright |
| Backend | Python 3.12+ · FastAPI · Pydantic · SQLAlchemy · Alembic |
| AI·영상 | Gemini · PaddleOCR · OpenCV · FFmpeg / FFprobe |
| 데이터·비동기 작업 | MySQL 8.4 · DB Queue |
| 배포·운영 | AWS · Docker Compose · Caddy · GitHub Actions · ECR · SSM |
| 검증 | pytest · Ruff · mypy · 모듈 경계 검사 |

## 평가 결과

장면 탐색과 번호판 판독을 나눠 평가했습니다. 아래는 **2026-11-01 결과 보고서의 실측값**입니다.

| 평가 대상 | 데이터·조건 | 결과 |
| --- | --- | --- |
| 영상의 위반 유형 찾기 | AI-Hub 양성 영상 400개, 최상위 후보 유형 일치 | **371/400 · 92.8%** |
| 실제 영상에서 사건 찾고 확인하기 | 유튜브 179클립·위반 16건, 상위 3개·시점 ±2초·유형 일치·Fine 확인 | **10/16 · 62.5%**, 정상 클립당 최종 오탐 **0.35건** |
| 번호판의 잘못된 확정 줄이기 | AI-Hub 번호판 crop 314장, O1 → O2 판독 규칙 비교 | **129건 → 32건**, 전체 정답률 **21.0% → 36.0%** |

유형 적중률은 양성 영상의 분류 결과이고, 번호판 수치는 잘라낸 이미지의 인식 결과입니다. 사건 탐색은 표본 16건으로 95% 신뢰구간이 약 39–82%이며, 설정 선택에 사용한 사건 10건이 포함된 개발 평가입니다. 번호판 O2는 10/22 규칙 기준입니다. 각 수치를 전체 제품의 일반화 성능으로 합산하지 않습니다.

[평가 결과와 조건](docs/modules/eval/evaluation-results-2026-11-01.md) · [평가 실행 방법](eval/README.md) · [지표 정의](docs/modules/eval/metrics/metric-definitions.md)

<a id="실행"></a>

## 빠른 시작

Node.js 20 이상, Python 3.12 이상을 사용합니다. npm workspace 의존성은 저장소 루트에서 설치합니다.

```bash
npm ci
npm run dev:web
```

Vite가 출력한 주소의 `/?demo`에서 API 없이 목데이터 화면 흐름을 확인할 수 있습니다. `/`의 실제 분석 흐름에는 API·Worker와 실행 환경 설정이 필요합니다.

```bash
uv sync --locked --extra test --extra quality
uv run pytest tests/eval -q
npm run test:web
npm run build --workspace=daesingo-web
```

API·Worker·MySQL 구성, OCR 모델, 환경변수, migration과 통합 테스트 실행은 [개발 환경과 실행](docs/getting-started.md)을 따릅니다.

## 저장소 구조

```text
apps/web/           실제 웹 앱
apps/prototype/     목데이터 기반 초기 흐름 프로토타입
src/daesingo/       API · Worker · 도메인 모듈
eval/              데이터 목록 · 예측 · 채점 · 평가 결과
tests/             모듈별 테스트와 CI 실행 도구
docs/              제품 · 아키텍처 · 모듈 · 운영 문서
deploy/            배포와 복구 도구
scripts/           경계 · 품질 · 보안 검사
```

## 배포와 검증

GitHub Actions에서 Python 회귀·MySQL 통합·Runtime 품질 검사와 웹 테스트를 실행합니다. 배포는 OIDC 인증으로 AWS에 연결하고 ECR 이미지와 SSM을 사용합니다.

| 확인할 내용 | 문서 |
| --- | --- |
| API·Worker 실행과 설정 | [API](src/daesingo/api/README.md) · [Worker](src/daesingo/worker/README.md) · [실행환경](docs/runtime/local-runtime-environment.md) |
| 웹 화면·API 연결·테스트 | [Web README](apps/web/README.md) |
| CI 분할과 MySQL 검증 | [CI 실행 구조](docs/runtime/ci-test-partitions.md) |
| 배포·복구·보관 정책 | [공개 배포](docs/runtime/rt14-public-deployment.md) · [운영 명세](docs/runtime/ops-spec.md) |
| 설계·의사결정·모듈별 자료 | [문서 목차](docs/README.md) |

## 팀

| 이름 | 담당 |
| --- | --- |
| 김준영 | PM · 증거 확정·신고자료 구성(`evidence`) · 공통 기반·운영 |
| 유소연 | 진행 관리·오케스트레이션(`case`) · E2E 통합 |
| 서어진 | 사건 후보 탐색·정밀 검증(`search`) |
| 신유민 | 번호판·화면 값 판독(`readout`) · Web 상태·API 연결 |
| 정철원 | 블랙박스 파일·미디어 처리(`recording`) · 작업 실행 기반 |
| 김대원 | 평가 설계·채점(`eval`) · Web 화면·접근성 구현 |

모듈별 역할과 협업 경계는 [담당 영역](docs/management/ownership.md)에 정리했습니다.

## 라이선스

[MIT](LICENSE)
