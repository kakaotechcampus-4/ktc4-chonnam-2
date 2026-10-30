"""Explicit host-only SecureString fetch; never invoked by Actions/SSM deploy.

Run separately after secret registration approval. Existing config IDs are
immutable and never replaced. Session Manager manual placement is the fallback.
"""
import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

from ec2 import ROOT, HostError, SafeParser, instance_environment, operation_lock, protected, require, run, validate_policy

NAMES = {"runtime-env": "runtime.env", "mysql-password": "mysql-password",
         "mysql-root-password": "mysql-root-password"}


def select_parameters(parameters, prefix):
    selected = {}
    for parameter in parameters:
        require(parameter.get("Type") == "SecureString")
        name = parameter.get("Name", "")
        require(name.startswith(prefix))
        leaf = name[len(prefix):]
        require(leaf in NAMES and NAMES[leaf] not in selected)
        value = parameter.get("Value")
        require(isinstance(value, str) and bool(value.strip()) and "\x00" not in value)
        selected[NAMES[leaf]] = value
    require(set(selected) == set(NAMES.values()))
    return selected


def main(argv=None):
    parser = SafeParser()
    parser.add_argument("--config-id", required=True)
    try:
        args = parser.parse_args(argv)
        require(os.name == "posix" and os.geteuid() == 0)
        require(bool(re.fullmatch(r"[a-z0-9][a-z0-9-]{0,63}", args.config_id)))
        protected(ROOT, 0, directory=True)
        protected(ROOT / "policy.json", 0)
        policy = json.loads((ROOT / "policy.json").read_text())
        validate_policy(policy)
        prefix = policy["parameter_path"]
        require(bool(re.fullmatch(r"/[A-Za-z0-9/_-]+/", prefix)))
        configs = ROOT / "configs"
        protected(configs, 0, directory=True)
        target = configs / args.config_id
        with operation_lock(ROOT):
            require(not target.exists() and not target.is_symlink())
            data = json.loads(run(["aws", "ssm", "get-parameters-by-path", "--path", prefix,
                "--with-decryption", "--no-recursive", "--region", "ap-northeast-2",
                "--output", "json", "--no-cli-pager"]))
            values = select_parameters(data["Parameters"], prefix)
            with tempfile.TemporaryDirectory(prefix="config-", dir=configs) as directory:
                pending = Path(directory) / "ready"
                pending.mkdir(mode=0o700)
                for name, value in values.items():
                    fd = os.open(pending / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o400)
                    with os.fdopen(fd, "w") as stream:
                        stream.write(value)
                        stream.flush()
                        os.fsync(stream.fileno())
                        os.fchown(stream.fileno(), 10001 if name == "runtime.env" else policy["mysql_uid"], -1)
                os.rename(pending, target)
        print("rt14-config: protected_files_created (deployment validation pending)")
        return 0
    except BaseException:
        print("rt14-config: failed", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
