import os
from starlette.responses import PlainTextResponse
from fastapi import APIRouter, Request, HTTPException, Header

from app.utils import verify_x_hub_signature

webhook_router = APIRouter()

INSTAGRAM_CLIENT_ID = os.getenv("CLIENT_ID")
INSTAGRAM_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
received_updates = []


@webhook_router.get("/instagram")
async def verify_subscription(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    return HTTPException(status_code=400, detail="Verification failed")


@webhook_router.post("/instagram", summary="Receive Instagram Updates")
async def receive_update(request: Request, x_hub_signature: str = Header(None)):
    body_bytes = await request.body()

    if not verify_x_hub_signature(INSTAGRAM_CLIENT_SECRET, body_bytes, x_hub_signature or ""):
        raise HTTPException(status_code=403, detail="Invalid X-Hub signature")

    body_json = await request.json()
    print("Instagram request body:")
    print(body_json)
    received_updates.insert(0, body_json)
    return PlainTextResponse("OK", status_code=200)