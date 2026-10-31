"""Trusted manual Actions boundary. Never print AWS/CLI/HTTP response contents.

OIDC stays in this process; temporary credentials are not written to GITHUB_ENV.
AWS CLI is used with bounded captured output. No AWS call at import time.
"""
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
import urllib.request

REPOSITORY = "kakaotechcampus-4/ktc4-chonnam-2"
REPOSITORY_ID = "1340154683"
REGION = "ap-northeast-2"


class DeployError(Exception):
    """Only fixed diagnostic codes may cross the public log boundary."""


def require(ok, code="invalid_input"):
    if not ok:
        raise DeployError(code)


def command(argv, *, input=None, env=None, timeout=60, run=subprocess.run):
    try:
        result = run(argv, input=input, env=env, capture_output=True,
                     text=True, timeout=timeout, check=False)
        require(result.returncode == 0, "command_failed")
        return result.stdout
    except (OSError, subprocess.SubprocessError):
        raise DeployError("command_unavailable_or_timeout") from None


def aws(args, *, env=None, query=None, timeout=60, input=None):
    argv = ["aws", *args, "--region", REGION, "--no-cli-pager", "--output", "json",
            "--cli-connect-timeout", "10", "--cli-read-timeout", "30"]
    if query:
        argv += ["--query", query]
    return json.loads(command(argv, env=env, timeout=timeout, input=input))


def validate_image(image, account):
    require(bool(re.fullmatch(r"[0-9]{12}", account)))
    require(bool(re.fullmatch(re.escape(account) + r"\.dkr\.ecr\." + REGION
        + r"\.amazonaws\.com/[a-z0-9]+(?:[._/-][a-z0-9]+)*@sha256:[0-9a-f]{64}", image)))


def verify_identity(identity, account):
    require(identity.get("Account") == account and bool(re.fullmatch(
        r"arn:aws:sts::" + re.escape(account)
        + r":assumed-role/ktc-github-deploy/[A-Za-z0-9+=,.@_-]+",
        identity.get("Arn", ""))), "identity_mismatch")


def wait_command(poll, *, timeout=1500, clock=time.monotonic, sleep=time.sleep):
    end = clock() + timeout
    while clock() < end:
        response = poll()
        if response is not None:
            status = response.get("Status")
            if status == "Success":
                require(type(response.get("ResponseCode")) is int and response["ResponseCode"] == 0,
                        "remote_nonzero")
                return
            require(status in {"Pending", "InProgress", "Delayed"}, "remote_failed_or_cancelled")
        sleep(3)
    raise DeployError("remote_result_unknown_timeout")


def ssm_payload(instance, image, revision, config_id, operation):
    validate_image(image, image.split(".")[0])
    require(bool(re.fullmatch(r"i-[0-9a-f]{17}", instance)))
    require(bool(re.fullmatch(r"[0-9a-f]{40}", revision)))
    require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", config_id)))
    require(operation in {"deploy", "rollback"})
    # Every interpolated byte is from a narrow alphabet. No shell/secret input.
    remote = ("exec /usr/bin/python3 /opt/daesingo/controller/ec2.py " + operation
        + " --image " + image + " --revision " + revision + " --config-id " + config_id)
    return {"DocumentName": "AWS-RunShellScript", "InstanceIds": [instance],
        "TimeoutSeconds": 60, "Parameters": {"commands": [remote], "executionTimeout": ["1200"]},
        "CloudWatchOutputConfig": {"CloudWatchOutputEnabled": False}}


def trusted_context(environ):
    require(environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch", "untrusted_event")
    require(environ.get("GITHUB_REPOSITORY") == REPOSITORY
        and environ.get("GITHUB_REPOSITORY_ID") == REPOSITORY_ID, "untrusted_repository")
    require(environ.get("GITHUB_REF") == "refs/heads/develop", "untrusted_ref")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", environ.get("GITHUB_SHA", ""))))


def github_json(path, env):
    request = urllib.request.Request("https://api.github.com/repos/" + REPOSITORY + path,
        headers={"Authorization": "Bearer " + env["GH_TOKEN"], "Accept": "application/vnd.github+json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def quality_gate(env, revision=None):
    sha = revision or env["GITHUB_SHA"]
    require(bool(re.fullmatch(r"[0-9a-f]{40}", sha)))
    if revision:
        comparison = github_json("/compare/" + sha + "...develop", env)
        require(comparison["status"] in {"ahead", "identical"}, "target_not_on_develop")
    else:
        require(github_json("/git/ref/heads/develop", env)["object"]["sha"] == sha, "develop_moved")
    for workflow in ("python-tests.yml", "boundary-check.yml"):
        runs = github_json("/actions/workflows/" + workflow + "/runs?head_sha=" + sha + "&per_page=100", env)
        candidates = [r for r in runs["workflow_runs"] if r["head_sha"] == sha
                      and r["event"] == "push" and r["head_repository"]["id"] == int(REPOSITORY_ID)]
        require(bool(candidates), "quality_gate_pending")
        latest = max(candidates, key=lambda r: r["id"])
        require(latest["status"] == "completed" and latest["conclusion"] == "success", "quality_gate_failed")


def oidc(env):
    account = env.get("AWS_ACCOUNT_ID", "")
    require(bool(re.fullmatch(r"[0-9]{12}", account)), "account_missing")
    # Ignore any pre-existing runner AWS profile, static key or endpoint setting.
    env = {**{key: value for key, value in env.items() if not key.startswith("AWS_")},
        "AWS_ACCOUNT_ID": account, "AWS_CONFIG_FILE": "/dev/null",
        "AWS_SHARED_CREDENTIALS_FILE": "/dev/null", "AWS_EC2_METADATA_DISABLED": "true"}
    # Mask before any child/action can print it; still capture output at source.
    print("::add-mask::" + account, flush=True)
    request_url = env["ACTIONS_ID_TOKEN_REQUEST_URL"] + "&audience=sts.amazonaws.com"
    require(request_url.startswith("https://"))
    request = urllib.request.Request(request_url,
        headers={"Authorization": "Bearer " + env["ACTIONS_ID_TOKEN_REQUEST_TOKEN"]})
    with urllib.request.urlopen(request, timeout=20) as response:
        token = json.load(response)["value"]
    with tempfile.TemporaryDirectory(prefix="rt14-oidc-") as directory:
        path = Path(directory) / "token"
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(fd, "w") as stream:
            stream.write(token)
        result = aws(["sts", "assume-role-with-web-identity", "--role-arn",
            f"arn:aws:iam::{account}:role/ktc-github-deploy", "--role-session-name", "rt14-" + env["GITHUB_RUN_ID"],
            "--web-identity-token", "file://" + str(path), "--duration-seconds", "3600"], env=env)
    credentials = result["Credentials"]
    authenticated = {**env, "AWS_ACCESS_KEY_ID": credentials["AccessKeyId"],
        "AWS_SECRET_ACCESS_KEY": credentials["SecretAccessKey"], "AWS_SESSION_TOKEN": credentials["SessionToken"],
        "AWS_EC2_METADATA_DISABLED": "true", "AWS_PAGER": ""}
    verify_identity(aws(["sts", "get-caller-identity"], env=authenticated), account)
    return authenticated


def publish(env):
    repo = env.get("ECR_REPOSITORY", "")
    require(bool(re.fullmatch(r"[a-z0-9]+(?:[._/-][a-z0-9]+)*", repo)))
    registry = env["AWS_ACCOUNT_ID"] + ".dkr.ecr." + REGION + ".amazonaws.com"
    # The approved repository must already exist and have immutable tags.
    details = aws(["ecr", "describe-repositories", "--repository-names", repo], env=env)["repositories"]
    require(len(details) == 1 and details[0]["imageTagMutability"] == "IMMUTABLE", "immutable_repository_required")
    auth = aws(["ecr", "get-authorization-token"], env=env)["authorizationData"]
    import base64
    require(len(auth) == 1 and auth[0]["proxyEndpoint"] == "https://" + registry, "registry_mismatch")
    username, password = base64.b64decode(auth[0]["authorizationToken"]).decode().split(":", 1)
    require(username == "AWS")
    with tempfile.TemporaryDirectory(prefix="rt14-docker-") as directory:
        docker_env = {**env, "DOCKER_CONFIG": directory}
        command(["docker", "login", "--username", "AWS", "--password-stdin", registry],
                input=password, env=docker_env)
        tag = registry + "/" + repo + ":" + env["GITHUB_SHA"]
        command(["docker", "tag", "daesingo-rt14:verified", tag], env=docker_env)
        command(["docker", "push", tag], env=docker_env, timeout=900)
    images = aws(["ecr", "describe-images", "--repository-name", repo,
                  "--image-ids", "imageTag=" + env["GITHUB_SHA"]], env=env)["imageDetails"]
    require(len(images) == 1)
    image = registry + "/" + repo + "@" + images[0]["imageDigest"]
    validate_image(image, env["AWS_ACCOUNT_ID"])
    # The digest alone contains no account/registry identifier.
    print("rt14: image_verified sha256=" + image.rsplit(":", 1)[1])


def remote(env, operation):
    image = env.get("DEPLOY_IMAGE", "")
    validate_image(image, env["AWS_ACCOUNT_ID"])
    quality_gate(env, revision=env.get("DEPLOY_REVISION", ""))
    repository = image.split("/", 1)[1].split("@", 1)[0]
    entries = aws(["ecr", "describe-images", "--repository-name", repository,
        "--image-ids", "imageTag=" + env["DEPLOY_REVISION"]], env=env)["imageDetails"]
    require(len(entries) == 1 and entries[0]["imageDigest"] == image.split("@", 1)[1], "digest_revision_mismatch")
    payload = ssm_payload(env.get("DEPLOY_INSTANCE_ID", ""), image,
        env.get("DEPLOY_REVISION", ""), env.get("DEPLOY_CONFIG_ID", ""), operation)
    result = aws(["ssm", "send-command", "--cli-input-json", json.dumps(payload)],
                 env=env, query="Command.CommandId")
    require(isinstance(result, str) and bool(re.fullmatch(r"[0-9a-f-]{36}", result)), "command_id_missing")
    print("rt14: command_accepted (remote success pending)", flush=True)
    def poll():
        # Only status/code are collected; stdout/stderr/URLs never reach runner.
        try:
            return aws(["ssm", "get-command-invocation", "--command-id", result,
                "--instance-id", env["DEPLOY_INSTANCE_ID"]], env=env,
                query="{Status:Status,ResponseCode:ResponseCode}")
        except DeployError:
            # eventual-consistency/not-found and transport/permission failures
            # are all bounded UNKNOWN, never guessed successful.
            return None
    wait_command(poll)
    print("rt14: remote_success")


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        env = dict(os.environ)
        trusted_context(env)
        require(env.get("AWS_REGION") == REGION, "region_missing_or_not_allowed")
        require(args in (["authenticate"], ["publish"], ["deploy"], ["rollback"]))
        if args != ["authenticate"]:
            require(env.get("RT14_EXECUTION_ENABLED") == "true", "execution_not_enabled")
        if args in (["publish"], ["deploy"]):
            quality_gate(env)
        authenticated = oidc(env)
        if args == ["authenticate"]:
            print("rt14: identity_match")
        elif args == ["publish"]:
            publish(authenticated)
        else:
            remote(authenticated, args[0])
        return 0
    except BaseException:
        # Do not interpolate even exception types supplied by an SDK/plugin.
        print("rt14: operation_failed_or_unknown", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
