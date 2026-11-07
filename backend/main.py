# main.py
import os
from fastapi import FastAPI, UploadFile, File, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from model import AnomalyModel
from security import (MAX_UPLOAD_BYTES, SizeLimitMiddleware, UploadRejected,
                      error_body, validate_filename, validate_log_content)

HARDENING = os.getenv("HARDENING", "on") == "on"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# this is so we can run the file with hardening off, this will allow the attacks to work
#in the demonstration video
if HARDENING:
    app.add_middleware(SizeLimitMiddleware, max_bytes=MAX_UPLOAD_BYTES)


@app.exception_handler(UploadRejected)
async def upload_rejected(request: Request, exc: UploadRejected):
    return JSONResponse(error_body(exc.code, exc.message), status_code=exc.status)

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    raw = await file.read()
    if HARDENING:
        validate_filename(file.filename)
        validate_log_content(raw)
    return await run_in_threadpool(model.predict, raw)

model = AnomalyModel()

@app.get("/")
async def root():
    return {"message": "Log Anomaly Detection API"}


@app.get("/session/{block_id}")
async def session_detail(block_id: str):
    result = model.get_session_detail(block_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)