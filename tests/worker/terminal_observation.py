"""Keep T1/T2 sink probes separate from A-1's real admission/tag reads."""

from sqlalchemy import event


def observe_terminal_transactions(run, engine, operation, *, observe, **kwargs):
    """Classify each actual attempt before DB faults; never suppress its sink.

    These fixtures persist T1 to job_execution and T2 to rt04b_case. Listen
    before execution so an injected disconnect on the first statement is still
    counted. All other attempts reach the same deliberately failing observer.
    """
    terminal = False

    def body(conn):
        nonlocal terminal
        terminal = False

        def mark(connection, statement, *args):
            nonlocal terminal
            if getattr(statement, "is_update", False) and statement.table.name == "job_execution":
                terminal = True
            if getattr(statement, "is_select", False):
                if any(table.name in ("job_execution", "rt04b_case")
                       for table in statement.get_final_froms()):
                    terminal = True

        event.listen(conn, "before_execute", mark)
        try:
            return operation(conn)
        finally:
            event.remove(conn, "before_execute", mark)

    return run(engine, body, observe=lambda attempt: observe(attempt, terminal), **kwargs)
