from graphlayout import pydot_layout_relabeling_example


def test_pydot_layout_example_uses_relabelled_graph() -> None:
    assert (
        pydot_layout_relabeling_example()
        == 'H_layout = nx.nx_pydot.pydot_layout(H, prog="dot")'
    )
