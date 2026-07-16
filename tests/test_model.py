"""Headless tests: BlockModel construction and serialization.

This is the contract the Model-group commands rely on.
"""

import compas
import pytest

pytest.importorskip("compas_dem", reason="compas_dem not installed")
# BlockModel hard-imports compas_cgal at module level, so the pipeline tests
# are skipped without it (it ships wheels for macOS/Windows/most Linux).
pytest.importorskip("compas_cgal", reason="compas_cgal not installed")


def test_arch_template_produces_blocks(arch_model):
    blocks = list(arch_model.elements())
    assert len(blocks) == 20


def test_supports_flag_roundtrip(arch_model):
    nodes = list(arch_model.graph.nodes())
    first, last = nodes[0], nodes[-1]
    arch_model.graph.node_element(first).is_support = True
    arch_model.graph.node_element(last).is_support = True

    supports = list(arch_model.supports())
    assert len(supports) == 2

    blocks = list(arch_model.blocks())  # non-support blocks
    assert len(blocks) == 18


def test_model_json_roundtrip(tmp_path, arch_model):
    filepath = tmp_path / "model.json"
    compas.json_dump(arch_model, filepath)
    loaded = compas.json_load(filepath)

    assert len(list(loaded.elements())) == len(list(arch_model.elements()))
    # identity must survive serialization: Problem links to model via guid
    assert str(loaded.guid) == str(arch_model.guid)


def test_contacts_detected(arch_model_with_contacts):
    contacts = list(arch_model_with_contacts.contacts())
    # 20 blocks in a single arch ring -> 19 interfaces
    assert len(contacts) == 19


def test_contacts_survive_json_roundtrip(tmp_path, arch_model_with_contacts):
    filepath = tmp_path / "model.json"
    compas.json_dump(arch_model_with_contacts, filepath)
    loaded = compas.json_load(filepath)
    assert len(list(loaded.contacts())) == len(list(arch_model_with_contacts.contacts()))


@pytest.mark.parametrize("stub", ["from_stack", "from_wall", "from_crossvault", "from_fanvault", "from_pavilionvault"])
def test_template_stubs_still_unimplemented(stub):
    """Guard: these constructors are NotImplementedError stubs upstream.

    If this test starts failing, a stub has been implemented in compas_dem
    and can be exposed in the Create Model command.
    """
    from compas_dem.models import BlockModel

    with pytest.raises(NotImplementedError):
        getattr(BlockModel, stub)()
