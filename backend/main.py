# main.py
import os
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from model import AnomalyModel
from security import (MAX_UPLOAD_BYTES, SizeLimitMiddleware, UploadRejected,
                      error_body, validate_filename, validate_log_content)
from slowapi.errors import RateLimitExceeded
from security import limiter   # add to your existing security import



HARDENING = os.getenv("HARDENING", "on") == "on"

app = FastAPI()

# this is so we can run the file with hardening off, this will allow the attacks to work
#in the demonstration video
if HARDENING:
    app.add_middleware(SizeLimitMiddleware, max_bytes=MAX_UPLOAD_BYTES)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


app.state.limiter = limiter    # slowapi looks the limiter up here

model = AnomalyModel()

@app.exception_handler(RateLimitExceeded)
async def rate_limited(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        error_body("rate_limited", "Too many requests. Please wait and try again."),
        status_code=429,
        headers={"Retry-After": "60"},
    )


@app.exception_handler(UploadRejected)
async def upload_rejected(request: Request, exc: UploadRejected):
    return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status)

@app.exception_handler(Exception)
async def unexpected_error(request: Request, exc: Exception):
    import logging
    logging.getLogger("app").exception("Unhandled error")
    return JSONResponse(error_body("internal_error", "Something went wrong."),
                        status_code=500)

@app.get("/")
async def root():
    return {"message": "Log Anomaly Detection API"}


@app.post("/analyze")
@limiter.limit("5/minute")
async def analyze(request: Request, file: UploadFile = File(...)):
    raw = await file.read()
    if HARDENING:
        validate_filename(file.filename)
        validate_log_content(raw)
    return await run_in_threadpool(model.predict, raw)


@app.get("/session/{block_id}")
@limiter.limit("60/minute")
async def session_detail(request: Request, block_id: str):
    result = model.get_session_detail(block_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000,
                server_header=False, proxy_headers=False)