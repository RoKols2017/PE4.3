import voice


def test_get_voices_returns_list():
	voices = voice.get_voices()
	assert isinstance(voices, list)
	assert len(voices) >= 1
	assert {"id", "name", "labels"}.issubset(voices[0].keys())


def test_synthesize_speech_returns_bytes():
	data = voice.synthesize_speech("hello", voice_id="test")
	assert isinstance(data, (bytes, bytearray))
