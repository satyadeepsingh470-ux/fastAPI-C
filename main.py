from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

app = FastAPI()
templates = Jinja2Templates(directory="templates")
subscribers: dict[str, list[WebSocket]] = {}   # order_id -> connected clients
order_status: dict[str, str] = {}

class StatusUpdate(BaseModel):
    status: str

# Home page: links to tracking and admin
@app.get("/")
async def home_page(request: Request):
    return templates.TemplateResponse(request, "home.html")

# Test page: open http://127.0.0.1:8000/track/{order_id} in a browser to watch live updates
@app.get("/track/{order_id}")
async def tracking_page(request: Request, order_id: str):
    return templates.TemplateResponse(request, "track.html", {"order_id": order_id})

# Admin page: open http://127.0.0.1:8000/admin to push status updates for any order
@app.get("/admin")
async def admin_page(request: Request):
    return templates.TemplateResponse(request, "admin.html")

@app.websocket("/ws/orders/{order_id}")
async def track_order(websocket: WebSocket, order_id: str):
    await websocket.accept()
    subscribers.setdefault(order_id, []).append(websocket)
    await websocket.send_json({"order_id": order_id, "status": order_status.get(order_id, "pending")})
    try:
        while True:
            await websocket.receive_text()  # just keeps connection alive
    except WebSocketDisconnect:
        subscribers[order_id].remove(websocket)

# A normal REST endpoint — e.g. called by an admin dashboard or a delivery driver's app
@app.post("/orders/{order_id}/status")
async def update_status(order_id: str, update: StatusUpdate):
    order_status[order_id] = update.status
    for ws in subscribers.get(order_id, []):
        await ws.send_json({"order_id": order_id, "status": update.status})
    return {"ok": True, "order_id": order_id, "status": update.status}
