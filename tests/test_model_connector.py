"""Tests for model_connector.py utility functions."""
import base64
import pytest
import requests
from unittest.mock import patch, MagicMock


def test_extract_json_by_regex_finds_object():
    import model_connector
    result = model_connector._extract_json_by_regex('some text {"key": "value"} more text')
    assert result == '{"key": "value"}'


def test_extract_json_by_regex_no_match_returns_input():
    import model_connector
    text = "no json here"
    result = model_connector._extract_json_by_regex(text)
    assert result == text


def test_extract_json_object_simple():
    import model_connector
    result = model_connector._extract_json_object('prefix {"a": 1} suffix')
    assert result == '{"a": 1}'


def test_extract_json_object_no_brace_returns_input():
    import model_connector
    text = "no braces"
    result = model_connector._extract_json_object(text)
    assert result == text


def test_extract_json_object_nested():
    import model_connector
    result = model_connector._extract_json_object('{"outer": {"inner": 1}}')
    assert result == '{"outer": {"inner": 1}}'


def test_get_image_base64_from_bytes():
    import model_connector
    data = b"hello"
    result = model_connector._get_image_base64(data)
    assert result == base64.b64encode(data).decode("utf-8")


def test_get_image_base64_from_file_object():
    import model_connector
    from io import BytesIO
    data = b"image bytes"
    f = BytesIO(data)
    result = model_connector._get_image_base64(f)
    assert result == base64.b64encode(data).decode("utf-8")


def test_get_model_response_by_image_returns_none_on_failure():
    import model_connector
    with patch("model_connector._call_model_with_retry", return_value=None):
        result = model_connector.get_model_response_by_image("model", b"img")
    assert result is None


def test_get_model_response_by_image_returns_dict_on_success():
    import model_connector
    with patch("model_connector._call_model_with_retry", return_value={"title": "T", "summary": "S"}):
        result = model_connector.get_model_response_by_image("model", b"img")
    assert result["title"] == "T"


def test_get_diary_response_by_image_delegates():
    import model_connector
    expected = {"title": "X", "describe": "Y", "main_emotion": "Z"}
    with patch("model_connector._call_model_with_retry", return_value=expected):
        result = model_connector.get_diary_response_by_image("model", b"img")
    assert result["main_emotion"] == "Z"


def test_get_diary_response_uses_fallback_prompt_when_missing():
    """When image_context_prompt is absent from config, a default prompt is used."""
    import model_connector
    import pet_model_config
    original = getattr(pet_model_config, "image_context_prompt", "SENTINEL")
    # Remove attribute to test fallback
    if hasattr(pet_model_config, "image_context_prompt"):
        delattr(pet_model_config, "image_context_prompt")
    try:
        with patch("model_connector._call_model_with_retry", return_value={"title": "T", "describe": "D", "main_emotion": "M"}):
            result = model_connector.get_diary_response_by_image("model", b"img")
        assert result is not None
    finally:
        if original != "SENTINEL":
            pet_model_config.image_context_prompt = original


def test_get_text_response_returns_none_on_failure():
    import model_connector
    with patch("model_connector._call_model_with_retry", return_value=None):
        result = model_connector.get_model_response("model", "prompt")
    assert result is None


def test_get_text_response_returns_string_on_success():
    import model_connector
    with patch("model_connector._call_model_with_retry", return_value={"response": "hello"}):
        result = model_connector.get_model_response("model", "prompt")
    assert result == "hello"


def test_encode_image_to_base64_file_not_found():
    import model_connector
    with pytest.raises(FileNotFoundError):
        model_connector.encode_image_to_base64("/nonexistent/path/image.jpg")


def test_encode_image_to_base64_existing_file(tmp_path):
    import model_connector
    f = tmp_path / "test.jpg"
    f.write_bytes(b"imgdata")
    result = model_connector.encode_image_to_base64(str(f))
    assert result == base64.b64encode(b"imgdata").decode("utf-8")


def test_extract_json_object_with_escape_sequence():
    import model_connector
    text = r'prefix {"key": "val\"ue"} suffix'
    result = model_connector._extract_json_object(text)
    assert '{"key"' in result


def test_extract_json_object_unclosed_returns_from_start():
    import model_connector
    text = '{"key": "value"'
    result = model_connector._extract_json_object(text)
    assert result == text[text.find("{"):]


def test_get_image_base64_from_string_path(tmp_path):
    import model_connector
    f = tmp_path / "img.jpg"
    f.write_bytes(b"pixels")
    result = model_connector._get_image_base64(str(f))
    assert result == base64.b64encode(b"pixels").decode("utf-8")


def test_get_model_response_calls_requests_post():
    import model_connector
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": "hello world"}
    with patch("requests.post", return_value=mock_resp):
        result = model_connector.get_model_response("model", "prompt")
    assert result == "hello world"


def test_get_model_response_by_image_parses_json_response():
    import model_connector
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": '{"title": "T", "summary": "S"}'}
    with patch("requests.post", return_value=mock_resp):
        result = model_connector.get_model_response_by_image("model", b"imgdata")
    assert result is not None
    assert result.get("title") == "T"


def test_get_model_response_by_image_regex_fallback():
    import model_connector
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"response": 'some text {"title": "T2", "summary": "S2"} end'}
    with patch("requests.post", return_value=mock_resp):
        result = model_connector.get_model_response_by_image("model", b"imgdata")
    assert result is not None
    assert result.get("title") == "T2"


def test_get_model_response_by_image_non_dict_result():
    import model_connector
    with patch("model_connector._call_model_with_retry", return_value="not a dict"):
        result = model_connector.get_model_response_by_image("model", b"img")
    assert result is not None
    assert result.get("title") == "解析失敗"
