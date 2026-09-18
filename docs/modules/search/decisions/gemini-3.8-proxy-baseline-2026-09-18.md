# Gemini 3.8 · 프록시 경유 운영 baseline (Owner 결정)

작성: 2026-09-18 · 결정: 서어진(search Owner)

적용 대상: Coarse / Fine 기반 블랙박스 영상 검색 파이프라인 (`src/daesingo/search`, `eval`)

이 문서는 운영 baseline 결정을 기록한다. `gemini-change-application-plan-2026-09-12.md`는
계측·A/B 실험 계획서로 유효하지만, "3.8 전환은 A/B 뒤"(같은 문서 §1·§8·Phase 3) 항목은
아래 Owner 결정으로 **운영 기본값에 한해 선행 적용**되어 대체된다. 실험 계획 자체는 그대로다.

## 결정

1. **모델 기본값을 `gemini-3.8-flash`로 올린다.** Interactions API 호출 구조는 3.7과 같다
   (같은 문서 §2.1). 토큰/비용/품질 재측정은 여전히 필요하지만 baseline 자체는 3.8로 둔다.
2. **FPS는 현재값이 기준이다** — coarse 1.0 / fine 2.0. 코드 변경 없음, 기준으로 고정.
3. **모든 Gemini 호출은 프록시를 경유한다.** base URL을 프록시로 돌리면
   `files.upload`(영상)와 `interactions.create`가 모두 프록시를 탄다. 인증은
   `Authorization: Bearer <GEMINI_API_KEY>`.
   - 기본 base URL: `https://mlapi.run/a90d8545-f100-4276-bf86-eb774596b91d/v1`
   - override: `.env` 의 `DAESINGO_GEMINI_BASE_URL`
4. **평가는 담당자 로컬에서 실행한다.** 데이터·`GEMINI_API_KEY`·프록시 접근은 각자의
   로컬 `.env` 에 있다. 저장소는 개인 회귀 영상·키를 담지 않는다.
5. **모든 설정은 `.env` 에서만 읽는다.** shell 환경변수 방식은 제거했다. `GEMINI_API_KEY`·
   `DAESINGO_*` 전부 저장소 루트 `.env`에서 로드하며(`daesingo.common.load_env_file`),
   `GEMINI_API_KEY`는 `.env`에 없으면 실패한다. `.env.example` 참고.

## 코드 반영

| 위치 | 변경 |
| --- | --- |
| `src/daesingo/search/config.py` | `model` 기본값 `gemini-3.8-flash`, `base_url` 필드 추가(기본=프록시), `from_env`→`from_dotenv`(`.env`에서만 로드), `version` → `gemini-search-v2` |
| `src/daesingo/search/provider.py` | `genai.Client(http_options={base_url, headers:{Authorization: Bearer <key>}})` |
| `src/daesingo/common/env.py` | `load_env_file()` — `.env`를 dict로 파싱(os.environ 미사용) |
| `src/daesingo/search/cli.py` · `eval/gemini_preflight.py` | 키·데이터루트를 `.env`에서 로드, `os.getenv` 제거 |
| `.env.example` · `eval/README.md` | `.env` 전용 설정 안내 |

`base_url`은 config fingerprint에 포함되므로 endpoint가 provenance에 남는다.

## 운영자가 로컬에서 확인할 것 (여기서 검증 불가)

프록시에 실제 호출을 넣어봐야만 확인되는 것 — 이 저장소에는 키·프록시 접근이 없어 미검증:

- 기본 base URL이 이미 `/v1`을 포함한다. SDK가 버전 경로(`/v1beta` 등)를 덧붙여
  경로가 이중이 되면, 버전 없는 base를 `DAESINGO_GEMINI_BASE_URL`로 지정하거나
  `api_version`을 맞춘다.
- 프록시가 Files API 업로드와 Interactions API를 모두 중계하는가.
- Bearer 토큰으로 인증이 통과하는가(SDK가 함께 보내는 `x-goog-api-key`는 프록시가 무시).

## 범위 밖 (이번에 손대지 않음)

- `feature/search-gemini-eval` 브랜치에 대한 코덱스 5축 리뷰 FAIL 항목
  (계약값 `ANALYSIS_SCOPE` 불일치, `budget` 미집행, 실패 taxonomy 미구현,
  A-tier Fine/Classification runner 부재, eval CLI path traversal) — 별도 후속.
- Architecture/contract 문서의 "proxy"(저해상도 영상 사본, A6 미결)와는 무관하다.
  이 결정의 프록시는 API 네트워크 프록시다.
