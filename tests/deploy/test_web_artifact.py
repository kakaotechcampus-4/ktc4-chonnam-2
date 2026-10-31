"""Synthetic public bundles; no credentials or external resources."""
import hashlib
import importlib
import json
from pathlib import Path

import pytest

REV = "b" * 40


def bundle(path, revision=REV):
    path.mkdir(parents=True)
    (path / "index.html").write_text("<!doctype html><title>synthetic</title>")
    (path / "version.json").write_text(json.dumps({"revision": revision}))
    files = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in path.iterdir()}
    (path / "manifest.json").write_text(json.dumps({"revision": revision, "files": files}))


def module():
    assert Path("deploy/web_artifact.py").exists(), "release bundle validation missing"
    return importlib.import_module("deploy.web_artifact")


@pytest.mark.parametrize("mutation", ["revision", "content", "extra", "missing", "traversal"])
def test_web_bundle_rejects_mismatch(tmp_path, mutation):
    m = module()
    web = tmp_path / "web"
    bundle(web)
    if mutation == "revision":
        (web / "version.json").write_text(json.dumps({"revision": "c" * 40}))
    elif mutation == "content":
        (web / "index.html").write_text("tampered")
    elif mutation == "extra":
        (web / "unexpected").write_text("synthetic")
    elif mutation == "missing":
        (web / "index.html").unlink()
    else:
        manifest = json.loads((web / "manifest.json").read_text())
        manifest["files"]["../escape"] = "a" * 64
        (web / "manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(m.ArtifactError):
        m.verify_web(web, REV)


def test_web_bundle_verified_and_revision_bound(tmp_path):
    m = module()
    bundle(tmp_path / "web")
    digest = m.verify_web(tmp_path / "web", REV)
    assert len(digest) == 64
    with pytest.raises(m.ArtifactError):
        m.verify_web(tmp_path / "web", "c" * 40)


def test_stage_extracts_exact_image_and_refuses_rewritten_bundle(tmp_path, monkeypatch):
    from deploy import ec2
    image = "synthetic@sha256:" + "a" * 64
    release = {"revision": REV, "image": image}
    calls = []
    def run(args, **kwargs):
        calls.append(args)
        if args[:2] == ["docker", "create"]:
            assert args[-1] == image
            return "d" * 64
        if args[:2] == ["docker", "cp"]:
            assert args[2] == "d" * 64 + ":/app/web/dist"
            bundle(Path(args[3]))
        return ""
    monkeypatch.setattr(ec2, "run", run)
    host = ec2.DockerHost(tmp_path, {})
    host.stage_web(release)
    assert calls[-1] == ["docker", "rm", "d" * 64]
    web = tmp_path / "releases" / REV / "web"
    index = web / "index.html"
    manifest_path = web / "manifest.json"
    index.chmod(0o644)
    manifest_path.chmod(0o644)
    index.write_text("rewritten")
    manifest = json.loads(manifest_path.read_text())
    manifest["files"]["index.html"] = hashlib.sha256(index.read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest))
    with pytest.raises(ec2.HostError):
        host.stage_web(release)
