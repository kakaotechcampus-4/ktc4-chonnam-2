"""Real pinned source identity without MySQL or alternate product imports."""
import subprocess

import test_compatible_revisions_mysql as revisions


def test_revision_roles_pin_real_b_and_use_current_c(tmp_path_factory):
    assert revisions.REVISIONS == {
        'e50': 'e50b2976ef4edc3a030cfc5b03a5206340dd917b',
        'bridge': 'ce0750d5a3317ad1c810783d67f8a05ba88bce08',
        'preview_source': '70f1c47cbc7c08fa848d057687f7130047f1126c',
        'preview_final': 'bb29d750d23765a73b7b6853b22086648684a392',
    }
    roots = revisions.releases.__wrapped__(tmp_path_factory)
    assert roots['final'] == revisions.ROOT
    assert roots['bridge'].resolve() != revisions.ROOT.resolve()
    name = 'src/daesingo/recording/mysql_repository.py'
    pinned = subprocess.run(
        ['git', '-c', f'safe.directory={revisions.ROOT}', 'show',
         revisions.REVISIONS['bridge'] + ':' + name],
        cwd=revisions.ROOT, check=True, capture_output=True,
    ).stdout
    assert (roots['bridge'] / name).read_bytes() == pinned
    assert b'PREPARED_WRITE_FORMAT = "legacy"' in pinned


def test_preview_baseline_has_same_case_worker_runtime_as_existing_bridge():
    # Reuse the existing mandatory old-job T1/T2 matrix only where trees are identical.
    result = subprocess.run(['git', '-c', f'safe.directory={revisions.ROOT}', 'diff', '--exit-code',
        revisions.REVISIONS['bridge'], revisions.REVISIONS['preview_source'], '--',
        'src/daesingo/case', 'src/daesingo/worker', 'src/daesingo/common'],
        cwd=revisions.ROOT, capture_output=True)
    assert result.returncode == 0


def test_revision_driver_redelivery_preserves_the_real_api_trace(monkeypatch):
    from contextlib import contextmanager
    from types import SimpleNamespace
    import compatibility_revision_driver as driver
    import daesingo.common.jobs.reflection as reflection
    row = {'execution_id': 'exec-preview', 'job_id': 'job-preview',
           'kind': 'CANDIDATE_VIDEO_PREVIEW', 'attempt': 1, 'status': 'SUCCEEDED',
           'produced': '[]', 'trace_id': 'real-api-trace'}

    class Connection:
        def exec_driver_sql(self, *args):
            return SimpleNamespace(mappings=lambda: SimpleNamespace(one=lambda: row))

    class Engine:
        @contextmanager
        def begin(self):
            yield Connection()

    def reflect(conn, incoming, reflector, trace):
        assert trace == row['trace_id']
        return SimpleNamespace(status='ALREADY_APPLIED')

    monkeypatch.setattr(reflection, 'reflect_terminal', reflect)
    assert driver.jobs(Engine(), {'action': 'job_reflect', 'case_id': 'case-preview',
                                'job_kind': 'CANDIDATE_VIDEO_PREVIEW'}) == {'reflection': 'ALREADY_APPLIED'}