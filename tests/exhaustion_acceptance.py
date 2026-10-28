"""Independent #405 acceptance inventory; checker must not import this file."""
EXHAUSTION_PARAMETERS = tuple(('exhaustion', family, mode) for family, modes in (
    ('creation', ('final','retry','cancel','COARSE_SEARCH','FINE_VERIFY','PLATE_READ','REPORT_VIDEO_EXPORT')),
    ('atomicity', ('commit','rollback','insert_error')),
    ('identity', ('rollback_retry','commit_unknown','parallel','unique_job')),
    ('delivery', ('APPLIED','CANCELLED','REFLECTED','EXHAUSTED','receipt')),
    ('rollback', ('case','enqueue','receipt','commit','rollback')),
    ('invalid', ('missing_case','unknown_job','kind','execution','job','case','attempt','status','reason','exhausted_at','trace')),
    ('redelivery', ('parallel','commit_unknown','isolation','scan')),
    ('composition', ('startup','periodic','absent')),
    ('migration', ('clean','upgrade','constraints','downgrade')),
    ('port', ('stored', 'job_record_kind', 'reason', 'terminal_status', 'result_type', 'cross_case', 'receipt_zero', 'unowned', 'store_connection', 'nochange_commit_unknown','exact_execution_id')),
    ('scan_policy', ('startup', 'periodic')),
    ('cancellation', ('delivery','recovery')),
) for mode in modes)
EXHAUSTION_CHECKS = tuple(sorted({(r,s) for r,s,p in EXHAUSTION_PARAMETERS}))
