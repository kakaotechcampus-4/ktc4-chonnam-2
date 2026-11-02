# 외부 AI로 보내는 영상 범위 (Owner 결정)

작성·결정: 2026-10-31 · 서어진(search Owner) · 결정 추적 [#71](https://github.com/kakaotechcampus-4/ktc4-chonnam-2/issues/71) §3 · `pre-deploy-security-review.md` 항목 7

적용 대상: 외부 AI provider를 부르는 모든 경로(`src/daesingo/search`). profile 값(width · height · fps · codec)은 다시 정하지 않는다(#41 경계 유지, #71 「범위 밖」).

## 결정

**외부 AI에는 Search가 저해상도 · 무음으로 다시 만든 영상과 사용자가 입력한 문장만 보낸다. 원본이나 판독용 고화질 영상은 보내지 않는다.**

| 입력 범위 | 외부 전송 | 쓰는 기능 | 상한 |
| --- | --- | --- | --- |
| 사용자 설명 문장 | 허용 | `HINT_EXTRACT`(단서 구조화) | 텍스트만. 영상 없음 |
| 저해상도 · 무음, **전체 timeline** | 허용 | `COARSE_SEARCH`(후보 찾기)만 | 360p 이하 · 소리 없음 · 원본 2 fps 표본 · 요청 1건 40 MiB |
| 저해상도 · 무음, **사건 구간만** | 허용 | `FINE_VERIFY`(위반 확인) | 후보 span ±4초 · 360p 이하 · 소리 없음 · 원본 4 fps 표본 · 40 MiB |
| 원본 또는 판독용 고화질 | **보내지 않음** | — | 번호판 · 시각 판독은 로컬 OCR(`readout`)에서 한다 |

### 최소 범위 원칙 — 적용한다

- 더 작은 범위로 되는 기능에는 넓은 범위를 보내지 않는다. 그래서 위반 확인은 전체 영상이 아니라 후보 구간만 보낸다.
- 전체 timeline은 「사건이 어디 있는지 모르는」 후보 찾기에만 보낸다. 범위는 case가 만든 `AnalysisScope`로 Recording이 준비한 분석 영상이다(지금 case는 Case 영상 전체를 범위로 잡는다).
- 소리는 어떤 기능에도 쓰지 않으므로 보내지 않는다.

### 원본 품질 입력이 필요해지면

지금 외부 AI 기능 중 원본 품질이 필요한 것은 없다. 앞으로 생기면(예: 외부 AI로 번호판 판독) 이 결정을 바꾸는 별도 Owner 결정과 PM 승인을 거친다. 그 전에는 provider adapter가 원본을 보내지 않는다.

## 코드가 이 상한을 지키는 방식

- 전송 영상은 Search가 매번 새로 인코딩한다(`search/media.py` `_run_ffmpeg_encode`): downscale만(`scale=-2:min(360,ih)`), `-an`(소리 제거), fps 표본 추출. Recording이 준 분석 영상의 해상도와 관계없이 이 단계를 거친다.
- 인코딩한 결과가 40 MiB를 넘으면 네트워크 호출 전에 거부한다(`_verify_output`, `max_inline_media_bytes`).
- Fine은 `fine_padding_sec`(4초)로 후보 span 앞뒤만 잘라 보낸다.
- 테스트: `tests/search/test_media_preparation.py` — `test_coarse_height_at_most_360` · `test_coarse_no_audio` · `test_fine_no_audio` · 크기 초과 거부. Fine 해상도 테스트는 720 이하만 확인한다(`test_fine_height_at_most_720`). 코드는 360이지만 테스트가 더 느슨하다.
- provider에 파일 객체를 올리지 않는다(inline 전송). 그래서 우리가 지워야 할 원격 사본(RemoteCopy)은 생기지 않는다(#71 §2, 2026-10-30 답).

## 남는 것

- **provider · 프록시가 요청 본문과 로그를 얼마나 보관하는지는 확인하지 못했다.** Elice 프록시와 Gemini의 보관 정책은 우리가 제어할 수 없다. 공개 운영 전 외부 AI 처리 고지와 함께 다룬다(#450 공개 운영 hardening).
- inline 요청 본문이 우리 쪽 로그에 남지 않는지는 별도 항목이다(`pre-deploy-security-review.md` 항목 18).
- Fine 해상도 테스트를 360으로 좁히는 것은 동결 뒤 후속이다.
