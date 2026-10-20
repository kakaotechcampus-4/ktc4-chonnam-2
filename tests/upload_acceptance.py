"""Independent RT-11(a) execution inventory; production checker must not import."""

UPLOAD_PARAMETERS = tuple(('api_upload', scenario, parameter) for scenario, parameter in (
    ('durability', 'commit_restore'), ('durability', 'response_loss'),
    ('atomicity', 'case_reject'), ('atomicity', 'case_failure'),
    ('concurrency', 'same_case'), ('receive', 'zero_checkout'),
    ('receive', 'probe_before_checkout'), ('receive', 'prepared_mutation'),
    ('taxonomy', 'unsupported'), ('taxonomy', 'tool'), ('taxonomy', 'read'), ('taxonomy', 'unexpected'),
    ('filename', 'traversal'), ('filename', 'absolute'), ('filename', 'separator'), ('filename', 'unicode'),
    ('abort', 'idle'), ('abort', 'duration'), ('abort', 'disconnect'),
    ('failure', 'missing_case'), ('failure', 'postcommit_view'), ('failure', 'commit_ack_loss'),
    ('interruption', 'before_publish'), ('interruption', 'after_publish'),
    ('interruption', 'before_commit'), ('interruption', 'after_commit'),
    ('limit', 'exact_declared'), ('limit', 'excess_declared'),
    ('limit', 'exact_stream'), ('limit', 'excess_stream'),
    ('transport', 'media'), ('transport', 'missing'), ('transport', 'multiple'),
    ('transport', 'filename'), ('transport', 'truncated'),
    ('storage', 'fsync'), ('storage', 'device'), ('storage', 'publish'),
))
UPLOAD_CHECKS = tuple(sorted({(r, s) for r, s, p in UPLOAD_PARAMETERS}))
