# 대신고

블랙박스 영상에서 교통위반 장면을 찾고, 번호판·시각·증거 영상을 모아 신고자료를 준비하는 서비스입니다.

- [서비스 체험](https://daesingo-ktc4.duckdns.org/)
- [개발 환경과 실행](docs/getting-started.md)
- [프로젝트 문서](docs/README.md)

> AI는 신고자료 준비를 돕습니다. 내용 확인과 안전신문고 최종 제출은 사용자가 직접 합니다.

<img src="docs/images/readme/cover.png" alt="대신고 — 기억 속 한 장면이 더 안전한 길의 시작" width="800">

## 목차

1. [서비스 소개](#서비스-소개)
2. [주요 기능](#주요-기능)
3. [공개 체험](#공개-체험)
4. [아키텍처](#아키텍처)
5. [기술 스택](#기술-스택)
6. [평가 결과](#평가-결과)
7. [저장소 구조](#저장소-구조)
8. [빠른 시작](#빠른-시작)
9. [문서](#문서)
10. [팀](#팀)

---

## 서비스 소개

위반을 목격하고도 장면을 찾고, 영상을 자르고, 번호판과 시각을 확인하는 과정이 번거로워 신고를 포기하는 운전자를 돕습니다.
기억나는 상황을 입력하면 대신고가 자료 초안을 준비하고, 사용자는 확인·수정한 뒤 직접 제출합니다.

**지원 유형:** 신호위반 · 중앙선 침범 · 백색 실선 침범 · 이륜차 안전모 미착용

<details>
<summary>대신고가 맡는 일</summary>

<table><tr><td>

<img src="docs/images/readme/workflow.png" alt="자료 준비를 자동화하고 사용자 확인과 제출로 연결하는 흐름" width="800">

</td></tr></table>

</details>

## 주요 기능

### 1. 영상과 상황 입력

블랙박스 영상을 올리고 기억나는 시간·차량·상황을 적습니다. 입력한 내용을 탐색 단서로 정리합니다.

<table><tr><td>

<img src="docs/images/readme/step-1-input.png" alt="영상 업로드와 상황 입력 화면" width="600">

</td></tr></table>

### 2. 분석 진행 확인

장면 탐색 → 후보 확인 → 번호판·시각 판독 → 증거 정리 순서로 진행 상황을 보여줍니다.

<table><tr><td>

<img src="docs/images/readme/step-2-analysis.png" alt="장면 탐색과 번호판 판독 진행 화면" width="800">

</td></tr></table>

### 3. 신고자료 확인과 내보내기

출처와 확인이 필요한 정보를 보여줍니다. 필요한 값을 수정하고 신고 내용 복사·영상 다운로드 후 안전신문고로 이동합니다.

<table><tr><td>

<img src="docs/images/readme/step-3-report.png" alt="신고자료 확인, 위치 수정, 내용 복사와 안전신문고 이동 화면" width="600">

</td></tr></table>

## 공개 체험

- Desktop Web에서 로그인 없이 이용합니다.
- 제공받은 공식 3분·10분 ZIP을 풀고, 같은 묶음의 MP4를 합계 **10분까지** 올립니다. 임의 사용자 영상은 받지 않습니다.
- 결과는 체험을 시작한 브라우저에서 확인합니다. 시작 24시간 후부터 자동 정리 대상이므로 필요한 자료는 미리 다운로드합니다.

---

## 아키텍처

<table><tr><td>

<img src="docs/images/readme/architecture.png" alt="React Web, FastAPI, MySQL, Worker와 도메인 모듈 구성" width="900">

</td></tr></table>

- API는 요청·조회를, Worker는 영상 분석·파일 생성을 담당하며 MySQL 기반 DB Queue로 연결합니다.
- `case`가 진행을 관리하고 `search`·`readout`의 관찰 결과를 `evidence`가 신고자료로 구성합니다.
- Eval은 제품 런타임과 분리된 개발용 평가 도구입니다. 카카오 지도는 키 설정 시 사용하는 보조 기능입니다.

<details>
<summary>후보 탐색과 정밀 검증</summary>

<table><tr><td>

<img src="docs/images/readme/coarse-fine.png" alt="넓은 범위의 Coarse 탐색과 선택한 후보의 Fine 검증" width="800">

</td></tr></table>

전체 범위에서 후보를 찾고 선택한 장면을 자세히 확인합니다. 다른 후보를 선택하면 해당 장면을 검증하며 기존 결과는 재사용합니다.

[모듈 경계와 계약](docs/architecture/module-architecture.md) · [Runtime 설계](docs/runtime/runtime-tech-spec.md)

</details>

## 기술 스택

| 구분 | 주요 기술 |
| --- | --- |
| FE | ![React 19](https://img.shields.io/badge/React%2019-61DAFB?style=for-the-badge&logo=react&logoColor=black) ![TypeScript](https://img.shields.io/badge/TypeScript-3178C6?style=for-the-badge&logo=typescript&logoColor=white) ![Vite 6](https://img.shields.io/badge/Vite%206-646CFF?style=for-the-badge&logo=vite&logoColor=white) ![CSS](https://img.shields.io/badge/CSS-663399?style=for-the-badge&logo=css&logoColor=white) |
| BE | ![Python 3.12+](https://img.shields.io/badge/Python%203.12%2B-3776AB?style=for-the-badge&logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white) ![Pydantic](https://img.shields.io/badge/Pydantic-E92063?style=for-the-badge&logo=pydantic&logoColor=white) ![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white) ![MySQL 8.4](https://img.shields.io/badge/MySQL%208.4-4479A1?style=for-the-badge&logo=mysql&logoColor=white) ![Alembic](https://img.shields.io/badge/Alembic-444444?style=for-the-badge) |
| AI·영상 | ![Gemini](https://img.shields.io/badge/Gemini-8E75B2?style=for-the-badge&logo=googlegemini&logoColor=white) ![PaddleOCR](https://img.shields.io/badge/PaddleOCR-0062B0?style=for-the-badge) ![OpenCV](https://img.shields.io/badge/OpenCV-5C3EE8?style=for-the-badge&logo=opencv&logoColor=white) ![FFmpeg](https://img.shields.io/badge/FFmpeg-007808?style=for-the-badge&logo=ffmpeg&logoColor=white) |
| 인프라 | ![AWS](https://img.shields.io/badge/AWS-FF9900?style=for-the-badge) ![Docker Compose](https://img.shields.io/badge/Docker%20Compose-2496ED?style=for-the-badge&logo=docker&logoColor=white) ![Caddy](https://img.shields.io/badge/Caddy-1F88C0?style=for-the-badge) ![GitHub Actions](https://img.shields.io/badge/GitHub%20Actions-2088FF?style=for-the-badge&logo=githubactions&logoColor=white) |
| 테스트·품질 | ![pytest](https://img.shields.io/badge/pytest-0A9EDC?style=for-the-badge&logo=pytest&logoColor=white) ![Vitest](https://img.shields.io/badge/Vitest-6E9F18?style=for-the-badge&logo=vitest&logoColor=white) ![Playwright](https://img.shields.io/badge/Playwright-2EAD33?style=for-the-badge) ![Ruff](https://img.shields.io/badge/Ruff-D7FF64?style=for-the-badge&logo=ruff&logoColor=black) ![mypy](https://img.shields.io/badge/mypy-3776AB?style=for-the-badge) |

## 평가 결과

2026-11-01 평가 기록입니다. 사건 탐색과 영상 유형 분류, 번호판 판독을 각각 측정했습니다.

| 평가 | 데이터 | 결과 |
| --- | --- | --- |
| 사건 탐색·정밀 확인 | 유튜브 179클립, 위반 16건 | 4/16 → **10/16 (62.5%)** |
| 영상 유형 분류 | AI-Hub 양성 영상 400개 | **371/400 (92.8%)** |
| 번호판의 잘못된 확정 | AI-Hub 번호판 crop 314장, O1 → O2 | **129건 → 32건** |

사건 탐색은 설정 선택에 사용한 사건 10건을 포함하는 개발 평가입니다(95% 신뢰구간 약 39–82%). 정상 클립당 최종 오탐은 0.35건입니다. 유형 분류는 양성 영상, 번호판은 crop 이미지·10/22 규칙 기준으로 전체 제품 성능과 구분합니다.

<details>
<summary>평가 그래프와 비용·오탐 비교</summary>

<table><tr><td>

<img src="docs/images/readme/evaluation.png" alt="설정별 사건 탐색 결과와 영상 유형 적중률" width="800">

</td></tr></table>

<table><tr><td>

<img src="docs/images/readme/evaluation-tradeoffs.png" alt="탐지 증가에 따른 비용과 오탐 변화" width="800">

</td></tr></table>

</details>

[상세 결과·평가 조건](docs/modules/eval/evaluation-results-2026-11-01.md) · [지표 정의](docs/modules/eval/metrics/metric-definitions.md)

## 저장소 구조

```text
apps/web/           실제 웹 앱
apps/prototype/     초기 흐름 프로토타입
src/daesingo/       API · Worker · 도메인 모듈
eval/              예측 · 채점 · 평가 결과
tests/             모듈별 테스트와 CI 실행 도구
docs/              제품 · 아키텍처 · 운영 문서
deploy/            배포·복구 도구
```

<a id="실행"></a>

## 빠른 시작

- [Web 실행](apps/web/README.md) — Node.js 20 이상. `/?demo`는 API 없는 목데이터 시연입니다.
- [API·Worker 실행](docs/getting-started.md) — Python 3.12 이상. 실제 분석에 필요한 DB·모델·환경 설정을 포함합니다.
- [평가 실행](eval/README.md) — 저장한 예측을 채점하고 결과를 비교합니다.

## 문서

| 문서 | 내용 |
| --- | --- |
| [제품 명세](docs/product/product-spec.md) · [사용자 흐름](docs/product/core-user-flow.md) | 지원 범위, 화면과 예외 처리 |
| [아키텍처](docs/architecture/module-architecture.md) · [논리 ERD](docs/architecture/erd-draft.md) | 모듈 경계와 데이터 구조 |
| [공개 운영 안내](docs/runtime/a1-public-readiness.md) · [배포·복구](docs/runtime/rt14-public-deployment.md) | AWS 운영, ECR·SSM 기반 배포 |
| [CI 실행 구조](docs/runtime/ci-test-partitions.md) | Python 회귀·MySQL 통합·품질 검사 |
| [전체 문서](docs/README.md) | 모듈별 설계와 의사결정 기록 |

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
