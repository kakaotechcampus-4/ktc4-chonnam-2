# 카테캠 지원 AWS 환경

**Status:** Input — 카테캠 운영진 공지 요약  
**Source:** 카테캠 운영진 AWS 실습환경 공지 (비공개)  
**Notice date:** 확인 필요  
**Captured:** 2026-10-02  
**Maintainer:** common/runtime — 김준영  
**Router:** [Official Inputs](./README.md)

> 공지 원문은 비공개이므로 싣지 않는다. §1–§4는 카테캠 고유 조건을 **사실만 요약**했고, §5–§6은 공지가 안내한 접속 절차를 **표준 AWS 절차로 재서술**했다. 스크린샷의 계정·리소스 식별자는 가렸다.
>
> 이 문서는 외부 입력이며 결정이 아니다. Runtime 배포·용량 결정은 [`ops-spec.md`](../ops-spec.md)에 기록하고 이 문서를 근거로 가리킨다.

## 1. 제공 환경

| 항목 | 내용 |
| --- | --- |
| 단위 | 팀당 독립 AWS 계정 1개 + EC2 서버 1대 (팀원 공유) |
| 서버 | t3.medium — 2 vCPU / 4 GB RAM |
| OS | Ubuntu 24.04 LTS |
| 디스크 | 50 GB SSD (암호화) |
| 리전 | 서울 `ap-northeast-2` 만 사용 |
| 제공 기간 | 2026-08-31 ~ 2026-11-20 |
| 로그인 | 팀원 각자 개인 SSO 계정 (카테캠 이메일) + MFA 필수. 자격증명 공유 금지 |
| 서버 접속 | SSM Session Manager. SSH 키·22번 포트 불필요 |

## 2. 제한 사항

차단된 작업은 권한 오류가 난다.

| 구분 | 불가 | 요청 시 검토 |
| --- | --- | --- |
| 서버 | 추가 생성, 사양 변경, 종료(삭제) | 사양 상향 |
| 스토리지 | 디스크 확장, 추가 볼륨 | 디스크 확장 |
| 네트워크·관리형 | Elastic IP, RDS, ALB, 고비용 서비스(NAT Gateway·EKS·Redshift·SageMaker·ElastiCache 등) | RDS, ALB, Elastic IP, 기타 차단 서비스 |
| 계정·보안 | 서울 외 리전, IAM 사용자·액세스 키 생성, CloudTrail 변경, Spot·Auto Scaling | — |

자유롭게 할 수 있는 것:

- 서버 중지·시작·재부팅
- 보안그룹 규칙 편집 (서비스 포트 개방 등)
- 서버 내부 패키지·런타임·Docker 설치와 구성
- S3, DynamoDB, Lambda, CloudWatch, ECR, API Gateway, SQS/SNS 사용

## 3. 사용 범위와 감시

- 허용: 2단계 팀프로젝트의 개발·빌드·테스트·배포, 데모·발표용 서비스 운영, 교육 관련 실습.
- 금지: 채굴, 외부 공격·스캔, 불법 콘텐츠·파일 공유 서버, 상업적·유료 서비스, 자격증명의 팀 외부 공유, 교육 무관 개인 사용, 스팸·프록시/VPN 운영. 위반 시 계정 즉시 정지.
- 감시: 모든 활동이 CloudTrail에 기록되고 GuardDuty 위협 탐지와 예산 모니터링이 상시 동작한다. 이상 사용은 자동 제한될 수 있다.
- 22번 포트를 `0.0.0.0/0`으로 열면 보안 모니터링에 탐지된다.

## 4. 증설·예외 요청

§2의 「요청 시 검토」 항목은 카테캠 인프라 담당에게 요청한다. 예산과 교육 목적을 함께 검토한 뒤 처리하며, 우회 시도는 금지다.

요청에 포함할 내용:

- 팀 (학교 / 팀 번호)
- 필요한 항목
- 필요한 이유 (어떤 기능을 위해)
- 예상 사용 기간

## 5. 콘솔 접속 절차

표준 IAM Identity Center + Session Manager 흐름이다. 포털 URL은 공지 원문을 따른다.

1. **SSO 로그인** — AWS 액세스 포털에 카테캠 이메일로 로그인한다. 첫 로그인 때 이메일 인증 코드로 비밀번호를 정하고 MFA를 등록한다. 로그인하면 팀 계정 타일과 권한 세트가 보인다.

    ![AWS 액세스 포털 계정 타일](images/aws-environment-01.png)

2. **리전을 서울로 전환** — 콘솔은 기본 리전(미국)으로 열린다. 우측 상단 리전 선택기에서 `ap-northeast-2`를 고른다. 다른 리전에서는 리소스가 비어 보이거나 권한 오류가 나는 것이 정상이다.

    ![콘솔 우측 상단 리전 선택기](images/aws-environment-02.png)

3. **EC2 인스턴스 열기** — 콘솔 홈 → EC2 → 인스턴스.

    ![콘솔 홈 EC2](images/aws-environment-03.png)

    ![EC2 리소스 인스턴스](images/aws-environment-04.png)

4. **Session Manager로 연결** — 인스턴스 선택 → 연결 → Session Manager 탭 → 연결. 브라우저 터미널이 `ubuntu` 사용자로 열린다.

    ![인스턴스 목록 연결 버튼](images/aws-environment-05.png)

    ![Session Manager 연결](images/aws-environment-06.png)

참고: [AWS Systems Manager Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager.html)

## 6. 로컬 SSH 접속 (선택)

22번 포트를 열지 않고 Session Manager 터널 위로 SSH를 쓴다. `scp`·`rsync`·VS Code Remote-SSH도 동작한다.

1. **도구 설치** — AWS CLI v2와 Session Manager plugin.
2. **SSO 프로필 설정** — `aws configure sso`에 포털 URL을 넣어 프로필을 만든다.
3. **SSH 키 준비** — 둘 중 하나.
    - **팀 공용 키:** 팀 서버의 키 페어 개인키가 Parameter Store `/ec2/keypair/<KeyPairId>`에 보관돼 있다. `aws ec2 describe-key-pairs`로 ID를 확인하고 `aws ssm get-parameter --with-decryption`으로 받는다.
    - **개인 키 (권장):** 로컬에서 `ssh-keygen -t ed25519`로 만들고, 공개키를 브라우저 세션에서 `~/.ssh/authorized_keys`에 추가한다.
4. **`~/.ssh/config` 등록** — 인스턴스 ID를 HostName으로 두고 SSM 문서 `AWS-StartSSHSession`을 ProxyCommand로 쓴다.

    ```text
    Host ktc-server
      HostName <인스턴스 ID>
      User ubuntu
      IdentityFile <개인키 경로>
      ProxyCommand sh -c "aws ssm start-session --target %h --document-name AWS-StartSSHSession --parameters 'portNumber=%p' --profile <SSO 프로필>"
    ```

개인키(`.pem`, `id_ed25519`)는 커밋하거나 공유하지 않는다.

참고: [Install the Session Manager plugin](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-install-plugin.html) · [Allow SSH connections through Session Manager](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-getting-started-enable-ssh-connections.html) · [Configure IAM Identity Center authentication with the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-sso.html)

## 7. 공지가 함께 안내한 운영 팁

- **디스크 부족:** 가장 흔한 원인은 Docker 빌드 캐시 누적이다. `docker system df`로 확인하고 `docker system prune`·`docker volume prune`으로 정리한다. 그래도 부족하면 §4로 확장을 요청한다.
- **외부 공개:** 보안그룹에서 서비스 포트(예: 80/443/8080)를 열고 서버 공인 IP로 접속한다. HTTPS는 Caddy 등으로 Let's Encrypt 인증서를 발급한다. 고정 IP(Elastic IP)는 기본 차단이므로 §4 요청 대상이다.
