import asyncio
import mimetypes
import coolname
from typing import Dict, Optional
from fastapi import FastAPI, Request, HTTPException, Response, Header
from fastapi.responses import FileResponse, RedirectResponse
from sse_starlette.sse import EventSourceResponse

app = FastAPI()

# Store pending requests. Key: request_id, Value: Future
pending_requests: Dict[str, asyncio.Future] = {}
active_queues: Dict[str, asyncio.Queue] = {}

def generate_host_id():
    while True:
        new_id = coolname.generate_slug(2)
        if new_id != "admin" and new_id not in active_queues:
            return new_id

# --- 1. Middleware for Branding ---
@app.middleware("http")
async def add_custom_header(request: Request, call_next):
    response = await call_next(request)
    response.headers["Server"] = "Browserver/1.1"
    return response

# --- 2. Root Redirects ---
@app.get("/")
async def root_redirect():
    return RedirectResponse(url=f"/admin/{generate_host_id()}")

@app.get("/admin/admin")
async def admin_nested_redirect():
    return RedirectResponse(url=f"/admin/{generate_host_id()}")

# --- 3. Admin Client Routes ---
@app.get("/admin/{client_id}")
async def serve_admin_client(client_id: str):
    return FileResponse("client/index.html")

@app.get("/admin/{client_id}/events")
async def sse_endpoint(client_id: str, request: Request):
    queue = asyncio.Queue()
    active_queues[client_id] = queue
    async def event_generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                data = await queue.get()
                yield data
        finally:
            active_queues.pop(client_id, None)
    return EventSourceResponse(event_generator())

@app.post("/admin/{client_id}/upload/{request_id}")
async def receive_file_content(
    client_id: str, 
    request_id: str, 
    request: Request,
    x_content_type: Optional[str] = Header(None) # Read custom header
):
    if request_id not in pending_requests:
        raise HTTPException(status_code=404, detail="Request ID not found")
    
    content = await request.body()
    future = pending_requests[request_id]
    
    if not future.done():
        # Pass both content and type back to the waiter
        future.set_result((content, x_content_type))
        
    return {"status": "received"}

@app.post("/admin/{client_id}/error/{request_id}")
async def receive_file_error(client_id: str, request_id: str):
    if request_id in pending_requests:
        future = pending_requests[request_id]
        if not future.done():
            future.set_exception(FileNotFoundError())
    return {"status": "error_logged"}

# --- 4. Public Access Route ---
@app.api_route("/{client_id}/{file_path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def public_file_access(client_id: str, file_path: str, request: Request):
    if client_id not in active_queues:
        return Response(f"Host '{client_id}' is not online.", status_code=404)

    # Note: We are currently only supporting GET from the admin side for simplicity,
    # but we capture the method here in case we expand later.
    
    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_requests[req_id] = future

    try:
        # Send request to browser
        await active_queues[client_id].put({
            "event": "request_file",
            "data": f'{{"id": "{req_id}", "path": "{file_path}", "method": "{request.method}"}}'
        })

        # Wait for (content, content_type) tuple
        content, content_type = await asyncio.wait_for(future, timeout=15.0)

        # Use the Content-Type sent by the browser, or guess if missing
        if not content_type:
            mime_type, _ = mimetypes.guess_type(file_path)
            content_type = mime_type or "application/octet-stream"

        return Response(content=content, media_type=content_type)

    except asyncio.TimeoutError:
        return Response("Host timed out.", status_code=504)
    except FileNotFoundError:
        return Response("File not found on host.", status_code=404)
    finally:
        pending_requests.pop(req_id, None)

# Needed imports
import uuid