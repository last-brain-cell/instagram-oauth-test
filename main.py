import hashlib
import hmac
import json
from enum import Enum

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.responses import JSONResponse
import httpx
import os
from dotenv import load_dotenv
from starlette.responses import HTMLResponse, PlainTextResponse

load_dotenv()


class MediaType(Enum):
    IMAGE = "IMAGE"
    VIDEO = "VIDEO"
    CAROUSEL = "CAROUSEL_ALBUM"


app = FastAPI()

INSTAGRAM_CLIENT_ID = os.getenv("CLIENT_ID")
INSTAGRAM_CLIENT_SECRET = os.getenv("CLIENT_SECRET")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
USER_ID = os.getenv("USER_ID")
REDIRECT_URI = os.getenv("REDIRECT_URI")
VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
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

def verify_x_hub_signature(app_secret: str, request_body: bytes, x_hub_signature: str) -> bool:
    # Parse the signature
    try:
        algo, signature = x_hub_signature.split("=")
    except ValueError:
        return False
    if algo != "sha1":
        return False

    expected_signature = hmac.new(
        app_secret.encode(), request_body, hashlib.sha1
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)

@app.get("/auth/instagram/callback", summary="Instagram OAuth Callback")
async def instagram_callback(request: Request):
    if not INSTAGRAM_CLIENT_ID or not INSTAGRAM_CLIENT_SECRET or not REDIRECT_URI:
        raise HTTPException(status_code=500, detail="Instagram credentials are not set in environment variables")
    code = request.query_params.get("code")
    code = code.strip("#_") if code else None
    error = request.query_params.get("error")


    if error:
        raise HTTPException(status_code=400, detail=f"Instagram authorization error: {error}")

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

    token_url = "https://api.instagram.com/oauth/access_token"
    data = {
        "client_id": INSTAGRAM_CLIENT_ID,
        "client_secret": INSTAGRAM_CLIENT_SECRET,
        "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
        "code": code
    }

    async with httpx.AsyncClient() as client:
        token_response = await client.post(token_url, data=data)

    if token_response.status_code != 200:
        raise HTTPException(status_code=token_response.status_code, detail=token_response.text)

    short_token_data = token_response.json()
    short_access_token = short_token_data.get("access_token")

    if not short_access_token:
        raise HTTPException(status_code=500, detail="Failed to get short-lived access token")

    long_token_url = "https://graph.instagram.com/access_token"
    params = {
        "grant_type": "ig_exchange_token",
        "client_secret": INSTAGRAM_CLIENT_SECRET,
        "access_token": short_access_token
    }

    async with httpx.AsyncClient() as client:
        long_token_response = await client.get(long_token_url, params=params)

    if long_token_response.status_code != 200:
        raise HTTPException(status_code=long_token_response.status_code, detail=long_token_response.text)

    long_token_data = long_token_response.json()
    return JSONResponse(content=long_token_data)


@app.get("/", response_class=HTMLResponse)
async def instagram_redirect_page():
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

@app.get("/ids", summary="Get Instagram User ID")
async def get_ids(access_token: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://graph.instagram.com/v23.0/me?fields=id,user_id,username,name,account_type,profile_picture_url,followers_count,follows_count,media_count&access_token={access_token}")
    return JSONResponse(content=response.json())


@app.get("/insights/user")
async def get_insights(account_id: str = USER_ID, access_token: str = ACCESS_TOKEN):
    metrics = [
        "reach",
        "follower_count",
        "website_clicks",
        "profile_views",
        "online_followers",
        "accounts_engaged",
        "total_interactions",
        "likes",
        "engaged_audience_demographics",
        "reached_audience_demographics",
        "follower_demographics",
        "follows_and_unfollows",
        "profile_links_taps",
    ]
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://graph.instagram.com/{account_id}/insights?metric={','.join(metrics)}&metric_type=total_value&period=day&access_token={access_token}")
    return JSONResponse(content=response.json())


@app.get("/insights/media")
async def get_insights(media_id: str, access_token: str = ACCESS_TOKEN, media_type: MediaType = MediaType.IMAGE):
    image_metrics = [
        "shares",
        "comments",
        "likes",
        "saved",
        "shares",
        "total_interactions",
        "reach",
        "views"
    ]
    carousel_metrics = [
        "shares",
        "comments",
        "likes",
        "saved",
        "shares",
        "total_interactions",
        "reach",
        "views",
        "impressions",
        "replies",
    ]
    video_metrics = [
        "shares",
        "comments",
        "likes",
        "saved",
        "shares",
        "total_interactions",
        "reach",
        "views",
        "ig_reels_video_view_total_time",
        "ig_reels_avg_watch_time",
    ]
    metrics = []
    if media_type == MediaType.IMAGE:
        metrics = image_metrics
    elif media_type == MediaType.CAROUSEL:
        metrics = carousel_metrics
    elif media_type == MediaType.VIDEO:
        metrics = video_metrics
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://graph.instagram.com/{media_id}/insights?metric={','.join(metrics)}&metric_type=total_value&period=day&access_token={access_token}")
    return JSONResponse(content=response.json())


@app.get("/list-media")
async def list_media(account_id: str = USER_ID, access_token: str = ACCESS_TOKEN):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://graph.instagram.com/{account_id}/media?fields=id,caption,media_type,media_url,thumbnail_url,timestamp&access_token={access_token}")
    return JSONResponse(content=response.json())


@app.get("/instagram")
async def verify_subscription(hub_mode: str, hub_verify_token: str, hub_challenge: str):
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