"""Own the mutable evidence for one parameter mutation of a valid report."""

from copy import deepcopy


def copy_parameter_evidence(report, node):
    # Only this node's metadata/phases are edited. Other evidence is read-only;
    # own the lists so omissions cannot remove evidence from the original.
    return {
        **report,
        "collected": [deepcopy(item) if item["nodeid"] == node else item
                      for item in report["collected"]],
        "selected": list(report["selected"]),
        "reports": [dict(item) if item["nodeid"] == node else item
                    for item in report["reports"]],
    }


def omit_evidence_nodes(report, removed):
    # Family omissions replace lists, never edit retained evidence. Preserve the
    # fresh report and own only the containers that the mutation changes.
    return {
        **report,
        "collected": [n for n in report["collected"] if n["nodeid"] not in removed],
        "selected": [n for n in report["selected"] if n not in removed],
        "reports": [n for n in report["reports"] if n["nodeid"] not in removed],
    }
