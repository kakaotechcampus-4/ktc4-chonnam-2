import shutil
import subprocess
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from daesingo.common import load_env_file
from eval import manifests_io, paths
from eval.runners.errors import RunnerPreflightError

MINIMUM_SDK = (2, 13, 0)


class PreflightError(RunnerPreflightError):
    pass


@dataclass(frozen=True, slots=True)
class PreparedClip:
    clip_id: str
    path: Path
    duration_sec: float
    sha256: str


@dataclass(frozen=True, slots=True)
class PreparedEval:
    api_key: str
    sdk_version: str
    clips: tuple[PreparedClip, ...]


def prepare(scope: dict[str, str]) -> PreparedEval:
    problems: list[str] = []
    env = load_env_file()
    if scope.get("manifest") != "b_youtube":
        problems.append("search:gemini-coarse-p3 supports manifest=b_youtube only")
    if scope.get("stage") != "candidate":
        problems.append("search:gemini-coarse-p3 supports stage=candidate only")

    api_key = env.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        problems.append("GEMINI_API_KEY is not set (.env)")
    sdk_version = _sdk_version(problems)
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        problems.append("ffprobe is not installed or not on PATH")

    manifest = manifests_io.load_clips("b_youtube")
    clips = manifest.get("clips", [])
    if len(clips) != 123:
        problems.append(f"b_youtube must contain 123 clips, found {len(clips)}")
    data_root = env.get("DAESINGO_EVAL_DATA_ROOT", "").strip()
    root = Path(data_root) if data_root else Path(paths.REPO_ROOT)
    prepared: list[PreparedClip] = []
    for clip in clips:
        clip_id = str(clip["clip_id"])
        clip_path = root / str(clip["file_path"])
        if not clip_path.is_file():
            problems.append(f"{clip_id}: media file does not exist ({clip_path})")
            continue
        actual_sha = _sha256_file(clip_path)
        expected_sha = str(clip.get("sha256") or "")
        if not expected_sha:
            problems.append(f"{clip_id}: manifest sha256 is missing")
        elif actual_sha != expected_sha:
            problems.append(f"{clip_id}: sha256 mismatch")
        actual_duration = _probe_duration(clip_path, ffprobe) if ffprobe else None
        expected_duration = float(clip["duration_sec"])
        if actual_duration is None:
            problems.append(f"{clip_id}: ffprobe could not read duration")
        elif abs(actual_duration - expected_duration) > 0.25:
            problems.append(
                f"{clip_id}: duration mismatch ({actual_duration:.3f}s != {expected_duration:.3f}s)"
            )
        prepared.append(PreparedClip(clip_id, clip_path, expected_duration, actual_sha))

    if problems:
        preview = "\n".join(f"- {problem}" for problem in problems[:30])
        omitted = len(problems) - 30
        suffix = f"\n- ... and {omitted} more" if omitted > 0 else ""
        raise PreflightError(
            "Gemini evaluation preflight failed before any paid API call:\n"
            + preview
            + suffix
        )
    return PreparedEval(api_key, sdk_version, tuple(prepared))


def _sdk_version(problems: list[str]) -> str:
    try:
        installed = version("google-genai")
    except PackageNotFoundError:
        problems.append("google-genai is not installed; sync the eval-gemini extra")
        return "missing"
    try:
        parts = tuple(int(part) for part in installed.split(".")[:3])
    except ValueError:
        problems.append(f"google-genai version is not parseable ({installed})")
        return installed
    if parts < MINIMUM_SDK:
        required = ".".join(str(part) for part in MINIMUM_SDK)
        problems.append(f"google-genai>={required} is required, found {installed}")
    return installed


def _sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe_duration(path: Path, ffprobe: str) -> float | None:
    completed = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        return float(completed.stdout.strip())
    except ValueError:
        return None
