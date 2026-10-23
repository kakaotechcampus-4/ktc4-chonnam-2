"""Mutation fixtures must isolate writes without copying unrelated evidence."""

from copy import deepcopy

from mysql_report_mutations import copy_parameter_evidence


def test_parameter_mutation_cannot_change_the_original_evidence():
    report = {
        "server_version": "8.4.7", "collection_errors": [],
        "collected": [
            {"nodeid": "target", "checks": [{"role": "frame", "parameter": "a"}],
             "junit": ["module", "target"]},
            {"nodeid": "other", "checks": [], "junit": ["module", "other"]},
        ],
        "selected": ["target", "other"],
        "reports": [{"nodeid": node, "when": phase, "outcome": "passed", "xfail": False}
                    for node in ("target", "other") for phase in ("setup", "call", "teardown")],
    }
    original = deepcopy(report)
    broken = copy_parameter_evidence(report, "target")
    broken["collected"][0]["checks"][0].pop("parameter")
    broken["collected"][0]["junit"].pop()
    broken["collected"].pop()
    broken["selected"].remove("target")
    for phase in broken["reports"]:
        if phase["nodeid"] == "target":
            phase["outcome"] = "failed"
            phase["xfail"] = True
    broken["reports"].pop()
    assert report == original
    assert copy_parameter_evidence(report, "target") == original


def test_parameter_mutation_does_not_traverse_unrelated_evidence():
    class UnrelatedEvidence(dict):
        def __deepcopy__(self, memo):
            raise AssertionError("unrelated evidence copied for each parameter")

    report = {"collected": [{"nodeid": "target"}, UnrelatedEvidence(nodeid="other")],
              "selected": ["target", "other"],
              "reports": [UnrelatedEvidence(nodeid="other", when="call", outcome="passed")]}
    broken = copy_parameter_evidence(report, "target")
    broken["collected"][0]["nodeid"] = "changed"
    assert report["collected"][0]["nodeid"] == "target"
    assert broken["collected"][1] == {"nodeid": "other"}
    assert broken["reports"] == report["reports"]
