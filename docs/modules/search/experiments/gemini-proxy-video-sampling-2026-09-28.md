# Gemini 프록시 경유 영상 샘플링: fps·해상도가 모델에 전달되는가

실행일: 2026-09-28. 호출별 조건·프레임 수·파일 크기·입력 토큰·에러 원문은 [구조화 결과](./gemini-proxy-video-sampling-2026-09-28-results.json)에 기록했다. 영상 파일과 API 키는 저장하지 않았다.

## 질문

Coarse 1 fps/최대 360p, Fine 2 fps/최대 720p(`config.py`의 `coarse_fps`·`fine_fps`, `media.py`의 ffmpeg 전처리)가 실제로 모델 입력에 반영되는가. 반영되지 않는다면 요청 파라미터로 지정할 수 있는가.

계기: 2026-09-26 p3 실행([결과 JSON](decision-trace-seven-video-2026-09-26-results.json)의 `trace_e0699a…` run)에서 Coarse 20초 호출은 모든 케이스가 입력 1,722토큰이었고, Fine 7초 호출은 831토큰이었다. Gemini 공개 단가(프레임당 low 66, default 258)로 계산하면 2 fps Fine은 low여도 영상만 924토큰이어서 관측값을 넘는다.

## 방법

- 현재 Search 설정(`GeminiSearchConfig.from_dotenv`)의 프록시 `base_url`로 `gemini-3.8-flash`, `reasoning_effort=low`를 호출했다. 요청 형식은 `provider.py`와 같게 `type: file` 파트에 base64 data URL로 인라인 전송했다. structured output은 쓰지 않았다.
- 원본은 `20260620_141628_EVT_1.avi`의 0–7초다. `media.py`와 같은 ffmpeg 필터(`fps=N,scale=-2:'min(H,ih)'`, libx264, 오디오 제거)로 조건별 클립을 만들고 ffprobe로 실제 프레임 수를 셌다.
- 프롬프트는 모든 호출에서 `Reply with the single word OK.` 하나로 고정했다. 같은 프롬프트를 영상 없이 보낸 입력 토큰(8)을 빼서 영상 토큰으로 본다.
- 실험 1은 fps·해상도만 바꾼다. 실험 2는 2 fps/720p(14프레임) 클립을 고정하고 후보 파라미터를 하나씩 추가한다. 토큰이 기준값에서 바뀌면 그 파라미터가 Gemini에 도달한 것으로 본다.

## 결과 1: 로컬 fps·해상도

| 조건 | 실제 프레임 | 파일 크기 | 입력 토큰 | 영상 토큰 |
| --- | --- | --- | --- | --- |
| 1 fps / 360p | 7 | 161,535 B | 470 | 462 |
| 1 fps / 720p | 7 | 547,201 B | 470 | 462 |
| 2 fps / 360p | 14 | 217,600 B | 470 | 462 |
| 2 fps / 720p (현재 Fine) | 14 | 795,841 B | 470 | 462 |
| 4 fps / 720p | 28 | 1,083,371 B | 470 | 462 |
| 8 fps / 720p | 56 | 1,366,367 B | 470 | 462 |

프레임 8배, 파일 8.5배에서도 영상 토큰은 462로 같다. 462 = 7초 × 66으로, 서버가 **1 fps·low 해상도로 재샘플링**한다는 해석과 일치한다. 같은 p3 실행의 Coarse(20초: 1,320 + 텍스트)·Fine(7초: 462 + 텍스트) 수치도 같은 해석과 맞는다.

## 결과 2: 파라미터 전달

| 넣은 위치 | 결과 |
| --- | --- |
| 최상위 `media_resolution`(`high`, `MEDIA_RESOLUTION_HIGH`), `fps`, `generation_config` | 400 `Unknown name ... Cannot find field` |
| `extra_body.google`의 `media_resolution`, `mediaResolution`, `generation_config`, `generationConfig`, `video_metadata` | 400 `Unknown name ... at 'extra_body.google'` |
| `extra_body.google.thinking_config` (전달 경로 확인용) | 400 `Expected one of either reasoning_effort or custom thinking_config; found both` — 필드가 Google까지 도달함 |
| 파일 파트 안 `detail`, `media_resolution`, `video_metadata.fps`, `format`; 파트 수준 `video_metadata.fps` | 200, 470 그대로 (무시) |
| 파일 파트 안 `video_metadata.end_offset=3s` | 200, 470 그대로 — `video_metadata` 전체가 무시됨 |
| 같은 호스트의 네이티브 `…/v1beta/models/{model}:generateContent` | 404 |
| 같은 호스트의 `…/v1/models/{model}:generateContent` | 405 |

에러 형식과 `thinking_config` 반응으로 볼 때 프록시는 요청을 Google의 OpenAI 호환 엔드포인트로 그대로 넘긴다. 그 호환 레이어가 영상 `fps`·`media_resolution`을 받지 않으며, 네이티브 API는 이 프록시에서 제공되지 않는다.

## 해석과 한계

- 현재 경로에서 영상 입력은 Coarse·Fine 모두 **1 fps·프레임당 66토큰(low)**으로 처리된다. `fine_fps=2.0`·`fine_media_resolution="high"`와 Fine 720p 전처리는 모델 입력을 바꾸지 않고 전송 크기만 키운다. Fine이 Coarse와 다른 점은 구간 길이와 프롬프트뿐이다.
- 따라서 기존 Fine 실험 결과(p3·p4·진단 trace)는 모두 1 fps·low 입력 조건의 결과다.
- 토큰 수가 확인해 주는 것은 프레임 수와 해상도 등급까지다. 서버가 1초 중 어느 프레임을 고르는지, 토큰화 이전 해상도가 판별에 영향을 주는지는 이 실험으로 알 수 없다.
- 원본 1개·구간 1개·호출 조건당 1회다. 토큰 수는 결정적으로 보이지만 다른 길이·코덱·모델 버전에서 재확인하지 않았다.
- 이 기록은 결과만 남긴다. [프록시 baseline 결정](../decisions/gemini-3.8-proxy-baseline-2026-09-18.md)의 "FPS는 coarse 1.0 / fine 2.0 기준" 항목과 `provider.py`·`media.py`의 처리를 어떻게 할지는 정하지 않았다.
- 남은 경로는 로컬에서 추출한 프레임을 이미지 여러 장(`image_url`)으로 보내는 방식이다. 이미지 장당 토큰·`detail` 적용 여부·18 MiB 요청 상한 내 장수를 먼저 같은 방식으로 측정한다.
