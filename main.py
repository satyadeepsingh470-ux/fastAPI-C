from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

app = FastAPI()
subscribers: dict[str, list[WebSocket]] = {}   # order_id -> connected clients
order_status: dict[str, str] = {}

class StatusUpdate(BaseModel):
    status: str

# Test page: open http://127.0.0.1:8000/track/{order_id} in a browser to watch live updates
@app.get("/track/{order_id}", response_class=HTMLResponse)
async def tracking_page(order_id: str):
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8" />
      <title>Order {order_id}</title>
      <style>
        :root {{ color-scheme: light dark; }}
        * {{ box-sizing: border-box; }}
        body {{
          font-family: -apple-system, Segoe UI, Roboto, sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 35%, #f093fb 70%, #f5576c 100%);
          background-attachment: fixed;
          display: flex;
          justify-content: center;
          padding: 48px 16px;
          margin: 0;
          min-height: 100vh;
        }}
        .card {{
          background: rgba(255,255,255,0.97);
          border-radius: 20px;
          box-shadow: 0 20px 50px rgba(0,0,0,0.25);
          padding: 32px;
          width: 100%;
          max-width: 420px;
          border: 1px solid rgba(255,255,255,0.5);
        }}
        h1 {{
          font-size: 22px; margin: 0 0 4px;
          background: linear-gradient(90deg, #764ba2, #f5576c);
          -webkit-background-clip: text;
          background-clip: text;
          color: transparent;
          font-weight: 800;
        }}
        .order-id {{ color: #999; font-size: 13px; margin-bottom: 24px; font-weight: 600; }}
        .conn {{
          display: inline-flex;
          align-items: center;
          gap: 6px;
          font-size: 12px;
          color: #888;
          margin-bottom: 20px;
          background: #f4f5fb;
          padding: 5px 12px;
          border-radius: 999px;
        }}
        .dot {{
          width: 9px; height: 9px; border-radius: 50%;
          background: #f59e0b;
          transition: background 0.3s;
        }}
        .dot.live {{ background: #10b981; box-shadow: 0 0 0 4px rgba(16,185,129,0.25); animation: pulse 1.6s infinite; }}
        .dot.down {{ background: #ef4444; }}
        @keyframes pulse {{
          0%, 100% {{ box-shadow: 0 0 0 4px rgba(16,185,129,0.25); }}
          50% {{ box-shadow: 0 0 0 7px rgba(16,185,129,0.12); }}
        }}
        .steps {{ list-style: none; margin: 0; padding: 0; }}
        .steps li {{
          display: flex;
          align-items: center;
          gap: 14px;
          padding: 12px 10px;
          margin-bottom: 4px;
          border-radius: 12px;
          color: #bbb;
          font-size: 14px;
          font-weight: 600;
          transition: all 0.3s;
        }}
        .steps li .circle {{
          width: 30px; height: 30px;
          border-radius: 50%;
          border: 2px solid #e2e4ec;
          flex-shrink: 0;
          transition: all 0.3s;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 15px;
          background: #fff;
        }}
        .steps li.done {{ color: #333; }}
        .steps li.done .circle {{
          background: linear-gradient(135deg, #10b981, #34d399);
          border-color: transparent;
          color: #fff;
        }}
        .steps li.current {{
          color: #fff;
          background: linear-gradient(90deg, #667eea, #764ba2);
          box-shadow: 0 6px 16px rgba(118,75,162,0.35);
          transform: scale(1.03);
        }}
        .steps li.current .circle {{
          border-color: #fff;
          background: #fff;
          color: #764ba2;
          box-shadow: 0 0 0 4px rgba(255,255,255,0.3);
        }}
        .badge {{
          margin-top: 24px;
          display: inline-block;
          font-size: 13px;
          font-weight: 700;
          letter-spacing: 0.02em;
          padding: 8px 16px;
          border-radius: 999px;
          background: linear-gradient(90deg, #f093fb, #f5576c);
          color: #fff;
          box-shadow: 0 6px 16px rgba(245,87,108,0.35);
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>Order tracking</h1>
        <div class="order-id">Order #{order_id}</div>
        <div class="conn"><span class="dot" id="dot"></span><span id="connText">connecting...</span></div>
        <ul class="steps" id="steps">
          <li data-status="pending"><span class="circle">⏳</span>Pending</li>
          <li data-status="confirmed"><span class="circle">✅</span>Confirmed</li>
          <li data-status="preparing"><span class="circle">👨‍🍳</span>Preparing</li>
          <li data-status="shipped"><span class="circle">📦</span>Shipped</li>
          <li data-status="out_for_delivery"><span class="circle">🚚</span>Out for delivery</li>
          <li data-status="delivered"><span class="circle">🎉</span>Delivered</li>
        </ul>
        <div class="badge" id="badge">pending</div>
      </div>

      <script>
        const order = "{order_id}";
        const order_map = ["pending", "confirmed", "preparing", "shipped", "out_for_delivery", "delivered"];
        const dot = document.getElementById("dot");
        const connText = document.getElementById("connText");
        const badge = document.getElementById("badge");
        const items = [...document.querySelectorAll("#steps li")];

        function render(rawStatus) {{
          badge.textContent = rawStatus;
          const normalized = rawStatus.trim().toLowerCase().replace(/[\s-]+/g, "_");
          const idx = order_map.indexOf(normalized);
          items.forEach((li, i) => {{
            li.classList.remove("done", "current");
            if (idx === -1) return;
            if (i < idx) li.classList.add("done");
            else if (i === idx) li.classList.add("current");
          }});
        }}

        function connect() {{
          const ws = new WebSocket(`ws://${{location.host}}/ws/orders/${{order}}`);
          ws.onopen = () => {{
            dot.className = "dot live";
            connText.textContent = "live";
          }};
          ws.onmessage = (event) => {{
            const data = JSON.parse(event.data);
            render(data.status);
          }};
          ws.onclose = () => {{
            dot.className = "dot down";
            connText.textContent = "reconnecting...";
            setTimeout(connect, 1500);
          }};
          ws.onerror = () => ws.close();
        }}
        connect();
      </script>
    </body>
    </html>
    """

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