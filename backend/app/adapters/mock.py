from app.adapters.base import Transcriber
from app.contracts import TranscriptSegment

class MockTranscriber:
    """Simple mock transcriber used in tests.

    Returns an empty list of transcript segments, satisfying the Transcriber protocol
    without performing any real work.
    """
    def transcribe(self, audio_asset, config) -> list[TranscriptSegment]:
        return []
