from video_editor.transcript import _parse_whisper_json


def test_parse_whisper_json_uses_millisecond_offsets():
    payload = {
        "result": {"language": "en"},
        "transcription": [
            {
                "offsets": {"from": 1250, "to": 2480},
                "text": "  hello world  ",
            }
        ],
    }
    result = _parse_whisper_json(payload)
    assert result.language == "en"
    assert len(result.segments) == 1
    assert result.segments[0].start == 1.25
    assert result.segments[0].end == 2.48
    assert result.segments[0].text == "hello world"


def test_parse_whisper_json_skips_empty_segments():
    payload = {
        "result": {"language": "ru"},
        "transcription": [
            {"offsets": {"from": 0, "to": 1000}, "text": ""},
            {"offsets": {"from": 1000, "to": 1000}, "text": "x"},
        ],
    }
    result = _parse_whisper_json(payload)
    assert result.language == "ru"
    assert result.segments == []
