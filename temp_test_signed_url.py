import os, json
os.chdir('backend')
from fastapi.testclient import TestClient
from app.main import app
from app.dependencies import get_current_user
from app.auth import VerifiedUser
app.dependency_overrides[get_current_user] = lambda: VerifiedUser(uid='user-a')
client = TestClient(app)
resp = client.post('/api/lectures/uploads', json={'title':'Lecture','declared_type':'video/mp4','declared_size_bytes':24})
print('status', resp.status_code)
print('json', resp.json())
