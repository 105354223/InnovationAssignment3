# main.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from model import AnomalyModel

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],       # or "http://localhost:3000" if using React
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

model = AnomalyModel()


@app.get("/")
async def root():
    return {"message": "Log Anomaly Detection API"}


@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    try:
        raw = await file.read()
        if not raw:
            raise HTTPException(status_code=400, detail="Empty file")

        result = model.predict(raw)
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)