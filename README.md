# LectureFlow

LectureFlow is a lecture transcription prototype organized as separate frontend and backend applications:

- `frontend/` — React 19, Vite 6, TypeScript, and Tailwind CSS 3.4. The current workflow and generated lecture data remain mock-only.
- `backend/` — a Python/FastAPI API scaffold, independently runnable and containerized.

## Docker

Start both services:

```sh
docker compose up --build -d
```

Open `http://localhost:8080` on the host. On another device on the same network, open `http://<host-LAN-IP>:8080`. On Windows, find the host IPv4 address with `ipconfig`. The network must allow device-to-device connections, and the host firewall must allow inbound TCP on the selected port.

The frontend container serves the built app and proxies `/api/` requests to FastAPI. The API is available through the frontend at `http://localhost:8080/api/health`. The backend port is not published directly to the host.

Use another host port when 8080 is occupied:

```powershell
$env:APP_PORT = "8090"
docker compose up --build -d
```

Stop services with `docker compose down`.

## Local development

Frontend:

```powershell
cd frontend
npm ci
npm run dev
```

Backend (in a separate terminal):

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Vite proxies `/api/` calls to the local backend at port 8000. FastAPI's interactive API documentation is available at `http://localhost:8000/docs`.
