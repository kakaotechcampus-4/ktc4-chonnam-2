# Official Inputs

**Status:** Working — input router  
**Owner:** common/runtime — 김준영

카테캠 운영진이 알려준 AWS · ML API 등 주요 공지를 Runtime/Ops 판단의 외부 입력으로 보관한다.

> 이 폴더의 문서는 **외부 사실(input)** 이며 결정이 아니다. 배포·용량·provider 결정은 [`ops-spec.md`](../ops-spec.md) · [`runtime-tech-spec.md`](../runtime-tech-spec.md)에 기록하고 여기 문서를 근거로 가리킨다.

## 문서

| 문서 | 내용 |
| --- | --- |
| [`aws-environment.md`](./aws-environment.md) | 팀 AWS 환경 — EC2 사양·리전·제공 기간, 접속 방법(SSM), 사용 범위, 제한 사항, 증설 요청 경로 |
| [`mlapi.md`](./mlapi.md) | 2단계 ML API — Serverless 전용, 모델 선택 경계, 팀 ₩120,000 크레딧, API Key·비용·미확인 provider 제약 |

## 추가 규칙

- 파일명은 `<주제>.md` (kebab-case 영어), 이미지는 `images/<주제>-NN.png`.
- 레포는 공개이고 공지는 비공개다. **원문을 싣지 않는다.**
  - 카테캠 고유 조건(사양·기간·제한·요청 경로)은 사실만 요약한다.
  - 보편적인 절차(AWS·provider 사용법)는 공식 문서 기준으로 재서술하고 공식 문서를 링크한다.
  - 요약·재서술 방식은 문서 머리말에 적는다.
- 커밋 전에 가린다: 개인 대화 링크, 내부 포털 URL, 담당자 이름, 스크린샷의 계정 이름·계정 ID·이메일·인스턴스/VPC/서브넷/보안그룹 ID·퍼블릭 IP/DNS, 키·토큰.
