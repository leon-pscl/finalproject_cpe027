import io
import time

from app import main
from app.jobs import JobStore
from fastapi.testclient import TestClient


def fake(path, on_progress=None, on_segment=None, **_):
    time.sleep(0.1)
    from app.asr import Transcript
    return Transcript(language="en", duration=1.0, segments=[])


store = JobStore(transcriber=fake, workers=1)
main.app.dependency_overrides[main.get_store] = lambda: store
client = TestClient(main.app)

def wav():
    import wave
    b = io.BytesIO()
    with wave.open(b, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(8000)
        w.writeframes(b"\x00" * 3200)
    return b.getvalue()

res = client.post("/api/transcriptions", files={"file": ("lecture.wav", io.BytesIO(wav()), "audio/wav")})
print("upload status", res.status_code)
print("upload body", res.json())
jid = res.json()["id"]

end = time.time() + 5
while time.time() < end:
    body = client.get(f"/api/transcriptions/{jid}").json()
    if body["status"] in ("completed", "failed"):
        print("FINAL", body["status"])
        print("ERROR", body.get("error"))
        print("DSP", body.get("dsp"))
        break
    time.sleep(0.1)

main.app.dependency_overrides.clear()
PY