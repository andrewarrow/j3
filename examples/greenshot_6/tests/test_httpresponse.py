import warnings

from httpresponse.response import HTTPResponse


def test_getheader_deprecation_warning_names_httpresponse() -> None:
    response = HTTPResponse({"content-type": "text/plain"})
    replacement = "HTTPResponse.headers.get(name, default)"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert response.getheader("content-type") == "text/plain"

    assert len(caught) == 1
    assert str(caught[0].message) == (
        "HTTPResponse.getheader() is deprecated and will be removed "
        f"in urllib3 v2.1.0. Instead use {replacement}."
    )
