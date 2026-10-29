from app.adapters import adapter_bundle
from app.adapters.mock import MockTranscriber
from app.adapters.real import AdapterNotConfigured, RealTranscriber


def test_mock_bundle_is_selected_by_default() -> None:
    bundle = adapter_bundle()
    assert isinstance(bundle["transcriber"], MockTranscriber)


def test_real_adapter_raises_clear_error() -> None:
    adapter = RealTranscriber()
    try:
        adapter.transcribe(None, {})
    except AdapterNotConfigured as exc:
        assert "PROCESSING_MODE=real" in str(exc)
    else:
        raise AssertionError("expected AdapterNotConfigured")
