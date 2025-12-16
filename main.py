import asyncio
import uuid
import mimetypes
from typing import Dict
from fastapi import FastAPI, Request, HTTPException, Response
from fastapi.responses import FileResponse, RedirectResponse
from sse_starlette.sse import EventSourceResponse

import coolname

app = FastAPI()

# Store pending requests. Key: request_id, Value: Future
pending_requests: Dict[str, asyncio.Future] = {}

# Store active admin connections. Key: client_id, Value: Queue
active_queues: Dict[str, asyncio.Queue] = {}

def generate_host_id():
    """Generates a readable ID like 'brave-lion'."""
    while True:
        # Generate 2 words (e.g. 'happy-panda')
        new_id = coolname.generate_slug(2)
        # Ensure we don't accidentally generate 'admin' or a duplicate
        if new_id != "admin" and new_id not in active_queues:
            return new_id
        
@app.get("/")
async def root_redirect():
    """Redirects new admins to a unique session URL."""
    return RedirectResponse(url=f"/admin/{generate_host_id()}")

@app.get("/admin/admin")
async def admin_root_redirect():
    """Redirects /admin to a unique session URL."""
    return RedirectResponse(url=f"/admin/{generate_host_id()}")

@app.get("/admin/{client_id}")
async def serve_admin_client(client_id: str):
    """
    Serves the static HTML client. 
    The client JS will read the URL to know its client_id.
    """
    return FileResponse("client/index.html")

@app.get("/admin/{client_id}/events")
async def sse_endpoint(client_id: str, request: Request):
    """
    SSE connection specific to one client_id.
    """
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
            # Cleanup when client disconnects
            active_queues.pop(client_id, None)
            print(f"Client {client_id} disconnected")

    return EventSourceResponse(event_generator())

@app.post("/admin/{client_id}/upload/{request_id}")
async def receive_file_content(client_id: str, request_id: str, request: Request):
    """Receives file data from the specific admin client."""
    if request_id not in pending_requests:
        raise HTTPException(status_code=404, detail="Request ID not found")
    
    content = await request.body()
    
    future = pending_requests[request_id]
    if not future.done():
        future.set_result(content)
        
    return {"status": "received"}

@app.post("/admin/{client_id}/error/{request_id}")
async def receive_file_error(client_id: str, request_id: str):
    if request_id in pending_requests:
        future = pending_requests[request_id]
        if not future.done():
            future.set_exception(FileNotFoundError())
    return {"status": "error_logged"}


@app.api_route("/{client_id}/{file_path:path}", methods=["GET"])
async def public_file_access(client_id: str, file_path: str):
    """
    The public entry point. 
    Example: /123-abc/images/logo.png
    """
    if client_id not in active_queues:
        return Response("This host is not online.", status_code=404)

    # Handle root path default
    if file_path == "":
        file_path = "index.html"

    req_id = str(uuid.uuid4())
    loop = asyncio.get_running_loop()
    future = loop.create_future()
    pending_requests[req_id] = future

    try:
        # Send request specifically to the queue for this client_id
        await active_queues[client_id].put({
            "event": "request_file",
            "data": f'{{"id": "{req_id}", "path": "{file_path}"}}'
        })

        # Wait for that specific client to upload the data
        content = await asyncio.wait_for(future, timeout=10.0)

        mime_type, _ = mimetypes.guess_type(file_path)
        return Response(content=content, media_type=mime_type or "application/octet-stream")

    except asyncio.TimeoutError:
        return Response("Host timed out.", status_code=504)
    except FileNotFoundError:
        return Response("File not found on host.", status_code=404)
    finally:
        pending_requests.pop(req_id, None)