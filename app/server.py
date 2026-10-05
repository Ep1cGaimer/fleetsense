from pathlib import Path
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parents[1]


def create_app(data_path=None):
    application = FastAPI(title="FleetSense evidence", docs_url=None, redoc_url=None)

    @application.middleware("http")
    async def loopback_only(request: Request, call_next):
        if request.client and request.client.host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse({"detail": "Loopback access only"}, status_code=403)
        return await call_next(request)

    target = Path(data_path or os.environ.get("FLEETSENSE_UI_DATA", ROOT / "results/ui"))
    target.mkdir(parents=True, exist_ok=True)
    application.mount("/data", StaticFiles(directory=target), name="data")
    application.mount("/", StaticFiles(directory=ROOT / "app/ui", html=True), name="ui")
    return application


app = create_app()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8601)
