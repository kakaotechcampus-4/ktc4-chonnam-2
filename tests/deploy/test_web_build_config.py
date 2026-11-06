"""선택적인 공개 JavaScript 키의 build 배선 control. 실제 Vite 검증은 별도다."""
from pathlib import Path
import re
import os
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]


def test_optional_map_key_is_consumed_only_by_web_build():
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    before, web = dockerfile.split(" AS web-build\n", 1)
    web, runtime = web.split("FROM base AS runtime", 1)
    assert 'ARG VITE_KAKAO_MAP_KEY=""' in web
    assert 'RUN VITE_KAKAO_MAP_KEY="$VITE_KAKAO_MAP_KEY" npm run build --workspace=daesingo-web' in web
    assert web.index("ARG VITE_KAKAO_MAP_KEY") < web.index("npm run build")
    assert "VITE_KAKAO_MAP_KEY" not in before + runtime
    assert 'node docker/web_release.mjs apps/web/dist "$REVISION"' in web
    assert 'COPY --from=web-build /build/apps/web/dist ./web/dist' in runtime
    assert 'python /app/docker/web_artifact.py /app/web/dist "$REVISION"' in runtime
    assert "**/.env.*" in (ROOT / ".dockerignore").read_text(encoding="utf-8")


def test_publish_supplies_public_repository_variable_only_to_build_step():
    workflow = (ROOT / ".github/workflows/rt14-deploy.yml").read_text(encoding="utf-8")
    steps = re.split(r"(?m)^      - ", workflow)
    build, = [step for step in steps if "run: docker build " in step]
    assert 'VITE_KAKAO_MAP_KEY: ${{ vars.RT14_KAKAO_MAP_JS_KEY }}' in build
    assert '--build-arg VITE_KAKAO_MAP_KEY' in build
    assert '--build-arg REVISION="$PUBLISH_REVISION"' in build
    assert '--tag daesingo-rt14:verified "$RUNNER_TEMP/rt14-publish-source"' in build
    assert workflow.count("RT14_KAKAO_MAP_JS_KEY") == 1
    assert all("VITE_KAKAO_MAP_KEY" not in step for step in steps if step != build)
    assert '"$PUBLISH_IMAGE_ID" -I /app/docker/web_artifact.py /app/web/dist "$PUBLISH_REVISION"' in workflow
    assert 'run: python3 deploy/aws.py prepare-publish' in workflow
    assert 'id: publish_image' in workflow
    assert 'PUBLISH_IMAGE_ID: ${{ steps.publish_image.outputs.image_id }}' in workflow
    assert "run: python3 deploy/aws.py publish" in workflow


def test_target_entrypoint_and_optimization_cannot_bypass_acceptance():
    workflow = (ROOT / ".github/workflows/rt14-deploy.yml").read_text(encoding="utf-8")
    acceptance = workflow.split('      - name: Exact image media and offline model acceptance\n', 1)[1]
    acceptance = acceptance.split('      - name: Publish verified image', 1)[0]
    assert acceptance.count('docker run') == 4
    assert acceptance.count('--entrypoint /app/.venv/bin/python --env PYTHONOPTIMIZE=0') == 4
    assert acceptance.count('"$PUBLISH_IMAGE_ID" -I ') == 4
    result = subprocess.run([sys.executable, '-I', '-c', 'assert False'],
                            env={**os.environ, 'PYTHONOPTIMIZE': '1'}, capture_output=True)
    assert result.returncode != 0 and b'AssertionError' in result.stderr
