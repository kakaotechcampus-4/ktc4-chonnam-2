"""AWS boundary doubles: no credentials, network or remote execution."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module():
    path = ROOT / "deploy/aws.py"
    assert path.is_file(), "RT-14 AWS tool missing"
    spec = importlib.util.spec_from_file_location("rt14_aws", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.parametrize("status,code", [("Success", 1), ("Failed", 0),
    ("Cancelled", 0), ("TimedOut", -1), ("Cancelling", -1), ("Unknown", 0)])
def test_ssm_only_exact_success_and_zero_are_accepted(status, code):
    m = module()
    with pytest.raises(m.DeployError):
        m.wait_command(lambda: {"Status": status, "ResponseCode": code},
                       timeout=1, sleep=lambda _: None)


def test_ssm_pending_missing_then_exact_success():
    m = module()
    values = iter([None, {"Status": "Pending", "ResponseCode": -1},
        {"Status": "InProgress", "ResponseCode": -1}, {"Status": "Success", "ResponseCode": 0}])
    m.wait_command(lambda: next(values), timeout=5, sleep=lambda _: None)


def test_ssm_missing_is_bounded_failure():
    m = module()
    ticks = iter([0, 0, 2])
    with pytest.raises(m.DeployError):
        m.wait_command(lambda: None, timeout=1, clock=lambda: next(ticks), sleep=lambda _: None)


def test_identity_matches_account_and_exact_role_not_prefix():
    m = module()
    account = "1" * 12  # synthetic, never a target
    m.verify_identity({"Account": account, "Arn": f"arn:aws:sts::{account}:assumed-role/ktc-github-deploy/session"}, account)
    for role in ["ktc-github-deploy-other", "OtherRole"]:
        with pytest.raises(m.DeployError):
            m.verify_identity({"Account": account, "Arn": f"arn:aws:sts::{account}:assumed-role/{role}/session"}, account)


@pytest.mark.parametrize("value", ["latest", "repo:tag", "repo@sha256:123", "x;touch /tmp/x", ""])
def test_non_digest_image_rejected(value):
    m = module()
    with pytest.raises(m.DeployError):
        m.validate_image(value, "1" * 12)


def test_command_failure_never_exposes_argv_or_output(capsys):
    m = module()
    def run(*args, **kwargs):
        return SimpleNamespace(returncode=1, stdout="PRIVATE-CANARY", stderr="PRIVATE-CANARY")
    with pytest.raises(m.DeployError) as error:
        m.command(["aws", "PRIVATE-CANARY"], run=run)
    assert "PRIVATE-CANARY" not in str(error.value) + capsys.readouterr().out


def test_remote_command_is_fixed_controller_and_validated_fields():
    m = module()
    image = "1" * 12 + ".dkr.ecr.ap-northeast-2.amazonaws.com/runtime@sha256:" + "a" * 64
    payload = m.ssm_payload("i-" + "a" * 17, image, "b" * 40, "config-1", "deploy")
    assert payload["DocumentName"] == "AWS-RunShellScript"
    assert payload["InstanceIds"] == ["i-" + "a" * 17]
    assert payload["CloudWatchOutputConfig"] == {"CloudWatchOutputEnabled": False}
    assert "--config-id config-1" in payload["Parameters"]["commands"][0]
    with pytest.raises(m.DeployError):
        m.ssm_payload("i-" + "a" * 17, image, "b" * 40, "x; echo secret", "deploy")


@pytest.mark.parametrize("mutation", [{"GITHUB_EVENT_NAME": "pull_request"}, {"GITHUB_REF": "refs/heads/evil"},
    {"GITHUB_REPOSITORY_ID": "9"}, {"GITHUB_REPOSITORY": "fork/project"}])
def test_untrusted_context_refused(mutation):
    m = module()
    env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/develop",
        "GITHUB_REPOSITORY": "kakaotechcampus-4/ktc4-chonnam-2", "GITHUB_REPOSITORY_ID": "1340154683",
        "GITHUB_SHA": "a" * 40, **mutation}
    with pytest.raises(m.DeployError):
        m.trusted_context(env)


def test_target_revision_requires_own_ci_and_ancestry(monkeypatch):
    m = module()
    requests = []
    def api(path, env):
        requests.append(path)
        if path.startswith("/compare/"):
            return {"status": "diverged"}
        pytest.fail("diverged target must stop before CI or AWS")
    monkeypatch.setattr(m, "github_json", api)
    with pytest.raises(m.DeployError):
        m.quality_gate({"GITHUB_SHA": "a" * 40}, revision="b" * 40)


@pytest.mark.parametrize("status,code,expected", [("Success", 0, 0), ("Success", 7, 1), ("Failed", 0, 1),
                                                ("Cancelled", -1, 1), ("TimedOut", -1, 1)])
def test_dispatch_reports_remote_result_without_capturing_remote_output(monkeypatch, capsys, status, code, expected):
    m = module()
    env = {"GITHUB_EVENT_NAME": "workflow_dispatch", "GITHUB_REF": "refs/heads/develop",
        "GITHUB_REPOSITORY": "kakaotechcampus-4/ktc4-chonnam-2", "GITHUB_REPOSITORY_ID": "1340154683",
        "GITHUB_SHA": "a" * 40, "RT14_EXECUTION_ENABLED": "true", "AWS_ACCOUNT_ID": "1" * 12,
        "AWS_REGION": "ap-northeast-2",
        "DEPLOY_REVISION": "b" * 40, "DEPLOY_CONFIG_ID": "config-1", "DEPLOY_INSTANCE_ID": "i-" + "c" * 17,
        "DEPLOY_IMAGE": "1" * 12 + ".dkr.ecr.ap-northeast-2.amazonaws.com/runtime@sha256:" + "d" * 64}
    monkeypatch.setattr(m.os, "environ", env)
    monkeypatch.setattr(m, "oidc", lambda env: env)
    quality = []
    monkeypatch.setattr(m, "quality_gate", lambda env, revision=None: quality.append(revision))
    def aws(args, **kwargs):
        if args[:2] == ["ecr", "describe-images"]:
            assert "imageTag=" + "b" * 40 in args
            return {"imageDetails": [{"imageDigest": "sha256:" + "d" * 64}]}
        if args[:2] == ["ssm", "send-command"]:
            assert kwargs["query"] == "Command.CommandId"
            return "00000000-0000-0000-0000-000000000000"
        if args[:2] == ["ssm", "get-command-invocation"]:
            assert kwargs["query"] == "{Status:Status,ResponseCode:ResponseCode}"
            return {"Status": status, "ResponseCode": code}
        pytest.fail("unexpected external boundary")
    monkeypatch.setattr(m, "aws", aws)
    assert m.main(["deploy"]) == expected
    output = str(capsys.readouterr())
    assert env["DEPLOY_IMAGE"] not in output and env["DEPLOY_INSTANCE_ID"] not in output
    assert ("remote_success" in output) == (expected == 0)
    assert quality == [None, "b" * 40]


def test_oidc_token_file_removed_and_credentials_never_exported(tmp_path, monkeypatch, capsys):
    import io
    m = module()
    account = "1" * 12
    request = []
    def urlopen(value, timeout):
        request.append(value)
        return io.BytesIO(json.dumps({"value": "JWT-CANARY"}).encode())
    monkeypatch.setattr(m.urllib.request, "urlopen", urlopen)
    token_paths = []
    def aws(args, **kwargs):
        if args[:2] == ["sts", "assume-role-with-web-identity"]:
            token_path = Path(args[args.index("--web-identity-token") + 1][7:])
            assert token_path.read_text() == "JWT-CANARY"
            token_paths.append(token_path)
            assert "JWT-CANARY" not in str(args)
            return {"Credentials": {"AccessKeyId": "KEY-CANARY", "SecretAccessKey": "SECRET-CANARY", "SessionToken": "SESSION-CANARY"}}
        assert args == ["sts", "get-caller-identity"]
        assert kwargs["env"]["AWS_SESSION_TOKEN"] == "SESSION-CANARY"
        return {"Account": account, "Arn": f"arn:aws:sts::{account}:assumed-role/ktc-github-deploy/test"}
    monkeypatch.setattr(m, "aws", aws)
    monkeypatch.setattr(m.tempfile, "tempdir", str(tmp_path))
    env = {"AWS_ACCOUNT_ID": account, "GITHUB_RUN_ID": "123", "ACTIONS_ID_TOKEN_REQUEST_URL": "https://example.invalid/token?api=1",
           "ACTIONS_ID_TOKEN_REQUEST_TOKEN": "REQUEST-CANARY"}
    authenticated = m.oidc(env)
    assert authenticated["AWS_ACCESS_KEY_ID"] == "KEY-CANARY"
    assert token_paths and all(not path.exists() for path in token_paths)
    assert "AWS_ACCESS_KEY_ID" not in env
    output = str(capsys.readouterr())
    assert all(secret not in output for secret in ("JWT-CANARY", "KEY-CANARY", "SECRET-CANARY", "SESSION-CANARY", "REQUEST-CANARY"))
