from apidocs.api import control_plane_description


def test_control_plane_description_spells_programmatically() -> None:
    assert (
        control_plane_description()
        == "Control plane APIs for programmatically building/deploying Chalice apps."
    )
