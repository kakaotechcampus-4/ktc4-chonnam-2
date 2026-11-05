"""Real pinned source identity without MySQL or alternate product imports."""
import subprocess

import test_compatible_revisions_mysql as revisions


def test_revision_roles_pin_real_b_and_use_current_c(tmp_path_factory):
    assert revisions.REVISIONS == {
        'e50': 'e50b2976ef4edc3a030cfc5b03a5206340dd917b',
        'bridge': 'ce0750d5a3317ad1c810783d67f8a05ba88bce08',
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
