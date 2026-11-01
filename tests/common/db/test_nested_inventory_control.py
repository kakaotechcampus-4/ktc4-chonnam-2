"""Execute the real nested gate's omission stage with only exhaustion evidence.

This runs the artifact's statements, rather than comparing its source text. It
keeps the full nested entrypoint in CI while exercising this inventory addition
locally without repeating the database child suite.
"""
import ast
import importlib.util
import json
from pathlib import Path
from xml.etree import ElementTree

from mysql_report_mutations import copy_parameter_evidence, omit_evidence_nodes
from exhaustion_acceptance import EXHAUSTION_CHECKS, EXHAUSTION_PARAMETERS
import pytest


def test_nested_exhaustion_metadata_and_family_omission_counts(tmp_path):
    root=Path(__file__).resolve().parents[3]
    path=root/'tests/common/db/integration/test_migration_gate.py'
    tree=ast.parse(path.read_text(encoding='utf-8'))
    function,=(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='test_actual_report_rejects_each_missing_migration_check')
    start=next(i for i,n in enumerate(function.body) if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='omissions' for t in n.targets))
    # Execute only the omission stage. The production gate may append summary
    # reporting that depends on values created by earlier parameter stages.
    end=next(i for i,n in enumerate(function.body[start:],start) if isinstance(n,ast.Expr)
        and isinstance(n.value,ast.Call) and isinstance(n.value.func,ast.Name)
        and n.value.func.id=='print')
    stage=function.body[start:end]
    # Read the checker exactly as the real nested gate does; only its required
    # inventory is narrowed for this isolated stage, no calculations are replaced.
    spec=importlib.util.spec_from_file_location('nested_exhaustion_checker',root/'scripts/check_mysql_test_report.py')
    gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(gate)
    gate.REQUIRED_CHECKS=frozenset(EXHAUSTION_CHECKS)
    gate.REQUIRED_PARAMETERS=frozenset(EXHAUSTION_PARAMETERS)
    gate.REQUIRED_CASE_TESTS={};gate.REQUIRED_SCENARIOS=frozenset()
    nodes=[]
    for i,(role,scenario,parameter) in enumerate(EXHAUSTION_PARAMETERS):
        nodes.append({'nodeid':f'tests/worker/test_opaque_mysql.py::test_{i}',
            'junit':['opaque',f'case_{i}'],'scenarios':[],
            'checks':[{'role':role,'scenario':scenario,'parameter':parameter}]})
    report={'server_version':'8.4.7','collected':nodes,'selected':[n['nodeid'] for n in nodes],
        'collection_errors':[], 'reports':[{'nodeid':n['nodeid'],'when':phase,'outcome':'passed','xfail':False}
            for n in nodes for phase in ('setup','call','teardown')]}
    xml=ElementTree.Element('testsuites');suite=ElementTree.SubElement(xml,'testsuite')
    for n in nodes:ElementTree.SubElement(suite,'testcase',classname=n['junit'][0],name=n['junit'][1])
    junit_path=tmp_path/'input.xml';ElementTree.ElementTree(xml).write(junit_path,encoding='utf-8')
    gate.validate_report(report);gate.validate_junit(junit_path,report)
    # The unrelated inventory is empty in this controlled execution. Every
    # current exhaustion obligation remains, including the final count assertion.
    names={n.id for n in ast.walk(ast.Module(body=stage,type_ignores=[])) if isinstance(n,ast.Name)}
    namespace={n:() for n in names if n.endswith(('_PARAMETERS','_CHECKS'))}
    namespace.update(EXHAUSTION_PARAMETERS=EXHAUSTION_PARAMETERS,EXHAUSTION_CHECKS=EXHAUSTION_CHECKS,
        report=report,gate=gate,ElementTree=ElementTree,junit_path=junit_path,tmp_path=tmp_path,
        copy_parameter_evidence=copy_parameter_evidence,omit_evidence_nodes=omit_evidence_nodes,
        pytest=pytest,json=json)
    exec(compile(ast.Module(body=stage,type_ignores=[]),str(path),'exec'),namespace)
    omissions=namespace['omissions']
    assert len([o for o in omissions if len(o['identity'])==3])==244
    # Individual-family evidence is also required in the nested stage.
    assert len([o for o in omissions if len(o['identity'])==2])==12
