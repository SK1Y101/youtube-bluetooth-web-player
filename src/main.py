import logging

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .devices import (
    ConnectError,
    DeviceAction,
    DeviceManager,
    DisconnectError,
    SinkAction,
    SinkError,
)
from .host_device import get_device_details
from .playback import PlaybackManager, VideoAction
from .websockets import WebSocketManager

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger("main")
app = FastAPI()

app.mount("/static", StaticFiles(directory="src/static"), name="static")
templates = Jinja2Templates(directory="src/templates")

application_details = {"title": "AutoBreezeBeats", "version": "0.2"}

ws_manager = WebSocketManager(log)
device_manager = DeviceManager(log, ws_manager.notifier)
playback_manager = PlaybackManager(log, ws_manager.notifier)

device_manager.start_scanning()


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "application": application_details,
            "host": get_device_details(),
        },
    )


@app.get("/devices")
async def list_devices() -> list[dict[str, str | bool]]:
    return device_manager.list_devices


@app.post("/devices/connect")
async def bluetooth_connect(action: DeviceAction):
    address = action.address
    log.info(f"request to connect {address} recieved")
    if not (device_manager.connect_device(address)):
        raise ConnectError(address)
    log.info(f"Successfully connected to {address}")
    return {"status": "Connected"}


@app.post("/devices/disconnect")
async def bluetooth_disconnect(action: DeviceAction):
    address = action.address
    log.info(f"request to disconnect {address} recieved")
    if not (device_manager.disconnect_device(address)):
        raise DisconnectError(address)
    log.info(f"Successfully disconnected from {address}")
    return {"status": "Disconnected"}


@app.put("/devices/set-sink")
async def bluetooth_sink(action: SinkAction):
    if address := action.address:
        log.info(f"Set {address} as new playback device")
        if not device_manager.set_sink(address):
            raise SinkError(f"Could not set sink to {address}")
        return {"message": f"{address} set as new sink"}
    else:
        log.info("Set default as playback device")
        if not device_manager.unset_sinks():
            raise SinkError("Could not set sink to default")
        return {"message": "default set as new sink"}


@app.post("/video")
async def load_video(action: VideoAction):
    url = action.url
    log.info(f"Request to add {url} recieved")
    video = playback_manager.queue_video_url(url)
    return video.to_dict


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    async for data in ws_manager.recieve_data(websocket):
        match data:
            case "play":
                playback_manager.play
            case "pause":
                playback_manager.pause
            case "next_chapter":
                playback_manager.skip_next
            case "prev_chapter":
                playback_manager.skip_prev
            case "next_video":
                playback_manager.skip_queue
            case _:
                ws_manager.warn(f"Unknown data {data}")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
