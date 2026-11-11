import os
from fastapi import FastAPI, UploadFile, File, Request, HTTPException, Path
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from model import AnomalyModel
from security import (MAX_UPLOAD_BYTES, SizeLimitMiddleware, UploadRejected,
                      error_body, validate_filename, validate_log_content)
from slowapi.errors import RateLimitExceeded
from security import limiter  
from schemas import AnalyzeResponse, SessionDetailResponse, ErrorResponse

# turn on or off defences, default is on
HARDENING = os.getenv("HARDENING", "on") == "on"

# fast api call to frontend
app = FastAPI(
    title="Log Anomaly Detection API",
    version="1.0.0",
    description="Upload HDFS logs and get per-session anomaly scores.",
)

# this is so we can run the file with hardening off, this will allow the attacks to work
#in the demonstration video
if HARDENING:
    app.add_middleware(SizeLimitMiddleware, max_bytes=MAX_UPLOAD_BYTES)

# only allows frontend at localhost:8000 to have POST/GET
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


app.state.limiter = limiter    # slowapi looks the limiter up here

model = AnomalyModel()

# when rate limit exceeds turns slowapi's exeption into a consistant JSON error with a retry-after
@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        error_body("rate_limited", "Too many requests. Please wait and try again."),
        status_code=429,
        headers={"Retry-After": "60"},
    )

# custom exception
@app.exception_handler(UploadRejected)
async def upload_rejected(request: Request, exc: UploadRejected):
    return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status)

# returns full traceback serverside but returns a generic message client side
@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    import logging
    logging.getLogger("app").exception("Unhandled error")
    return JSONResponse(error_body("internal_error", "Something went wrong."),
                        status_code=500)

# info
@app.get("/")
async def root():
    return {"message": "Log Anomaly Detection API"}

# main endpoint
# 5 requests per minute and requires a request perameter to identify caller
# reads file to memory and when hardening=off no file size limit
# file content validation only run when hardening = on
# model prediction CPU bound
@app.post("/analyze",
    response_model=AnalyzeResponse,
    summary="Analyse an HDFS log file",
    description=(
        "Upload an HDFS log (.log or .txt, max 25 MB). The log is grouped into "
        "per-block sessions, each scored by the model. Returns a summary and the "
        "100 most anomalous sessions.\n\n"
        "Example: `curl -F \"file=@sample.log\" http://127.0.0.1:8000/analyze`"
    ),
    responses={
        400: {"model": ErrorResponse, "description": "Bad filename, empty file or content is not an HDFS log"},
        413: {"model": ErrorResponse, "description": "File exceeds the 25 MB limit"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded (5 per minute)"},
        500: {"model": ErrorResponse, "description": "Unexpected server error"},
    },
    tags=["Analysis"],
)
@limiter.limit("5/minute")
async def analyze(request: Request, file: UploadFile = File(...)):
    raw = await file.read()
    if HARDENING:
        validate_filename(file.filename)
        validate_log_content(raw)
    return await run_in_threadpool(model.predict, raw)

# read only lookup
# block_id parameter passed straight to the model
# block_id length and char set under hardening and could cause injection if get_session_detail did DB lookups
# returns 404 error if model reports error otherwise returns JSON session
@app.get("/session/{block_id}",
    response_model=SessionDetailResponse,
    summary="Get raw log messages for one session",
    description="Returns up to 50 raw messages for a block from the most recent upload.",
    responses={
        404: {"model": ErrorResponse, "description": "No upload yet, or block not found"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded (60 per minute)"},
    },
    tags=["Analysis"],
)
@limiter.limit("60/minute")
async def session_detail(request: Request, block_id: str):
    result = model.get_session_detail(block_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

# runs dev server directly, only need to run this file with python main.py
# runs in localhost/loopback ip 
# disabled proxy header to avoid attackers spoofing X-Forward-forto avoid rate limit hardening
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000,
                server_header=False, proxy_headers=False)