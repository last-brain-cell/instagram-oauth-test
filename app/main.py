import os
import json
from dotenv import load_dotenv
from app.routers.insights import insights_router
from app.routers.webhook import webhook_router
from fastapi.middleware.cors import CORSMiddleware
from fastapi import FastAPI, Request, HTTPException, Header
from starlette.responses import PlainTextResponse, HTMLResponse
from app.utils import verify_x_hub_signature

load_dotenv()

INSTAGRAM_CLIENT_ID = os.getenv("CLIENT_ID")
INSTAGRAM_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
REDIRECT_URI = os.getenv("REDIRECT_URI")
EMBED_URL = (
    f"https://www.instagram.com/oauth/authorize"
    f"?enable_fb_login=0&force_authentication=1"
    f"&client_id={INSTAGRAM_CLIENT_ID}"
    f"&redirect_uri={REDIRECT_URI}"
    f"&response_type=code"
    f"&scope=instagram_business_basic,instagram_business_manage_messages,"
    f"instagram_business_manage_comments,instagram_business_content_publish,"
    f"instagram_business_manage_insights"
)
received_updates = []

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router=insights_router, prefix="/insights", tags=["Insights"])
app.include_router(router=webhook_router, prefix="/webhooks", tags=["Webhooks"])

@app.get("/", summary="Root Endpoint")
async def root():
    return HTMLResponse(content=f"""
        <html>
          <body>
            <a href="{EMBED_URL}">
                Connect Instagram
            </a>
            <pre>{json.dumps(received_updates, indent=2)}</pre>
          </body>
        </html>
        """)

@app.get("/health", summary="Health Check")
async def health_check():
    return {"status": "ok", "message": "API is running smoothly"}

@app.get("/instagram")
async def verify_subscription(request: Request):
    hub_mode = request.query_params.get("hub.mode")
    hub_challenge = request.query_params.get("hub.challenge")
    hub_verify_token = request.query_params.get("hub.verify_token")
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        return PlainTextResponse(content=hub_challenge)
    return HTTPException(status_code=400, detail="Verification failed")


@app.post("/instagram", summary="Receive Instagram Updates")
async def receive_update(request: Request, x_hub_signature: str = Header(None)):
    body_bytes = await request.body()

    if not verify_x_hub_signature(INSTAGRAM_CLIENT_SECRET, body_bytes, x_hub_signature or ""):
        raise HTTPException(status_code=403, detail="Invalid X-Hub signature")

    body_json = await request.json()
    print("Instagram request body:")
    print(body_json)
    received_updates.insert(0, body_json)
    return PlainTextResponse("OK", status_code=200)