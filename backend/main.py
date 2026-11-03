# main.py
import re
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from model import AnomalyModel

MAX_UPLOAD_BYTES = 25 * 1024 * 1024

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = AnomalyModel()

_HDFS_LINE_PREFIX = re.compile(r"^\d{6} \d{6} ")


def _looks_like_hdfs_log(text: str, sample_size: int = 20) -> bool:
    lines = [ln for ln in text.splitlines()[:sample_size * 3] if ln.strip()][:sample_size]
    if not lines:
        return False
    matches = sum(1 for ln in lines if _HDFS_LINE_PREFIX.match(ln))
    return matches / len(lines) >= 0.8


@app.get("/")
async def root():
    return {"message": "Log Anomaly Detection API"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    # 1. Read the file (with size cap)
    raw = await file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large ({len(raw) / 1_048_576:.1f} MB). "
                   f"Limit is {MAX_UPLOAD_BYTES / 1_048_576:.0f} MB.",
        )

    if len(raw) == 0:
        raise HTTPException(status_code=400, detail="Empty file")

    # 2. Check the file looks like an HDFS log
    text = raw.decode("utf-8", errors="replace")
    if not _looks_like_hdfs_log(text):
        raise HTTPException(
            status_code=400,
            detail="File does not look like an HDFS log "
                   "(expected lines beginning with a 6-digit YYMMDD timestamp).",
        )
    # 3. Run the model
    try:
        return model.predict(raw)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Analysis failed: {type(e).__name__}: {e}")
    
    return result

@app.get("/session/{block_id}")
async def session_detail(block_id: str):
    result = model.get_session_detail(block_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)