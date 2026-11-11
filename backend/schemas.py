from pydantic import BaseModel, Field

class Summary(BaseModel):
    total_sessions: int = Field(examples=[4])
    normal: int = Field(examples=[3])
    anomaly: int = Field(examples=[1])

class SessionResult(BaseModel):
    block_id: str = Field(examples=["blk_-9073992586687739851"])
    anomaly_score: float = Field(ge=0, le=1, examples=[0.9132])
    label: str = Field(examples=["Anomaly"])
    event_count: int = Field(examples=[13])

class AnalyzeResponse(BaseModel):
    summary: Summary
    sessions: list[SessionResult]
    session_total: int = Field(examples=[4])

class SessionDetailResponse(BaseModel):
    block_id: str
    messages: list[str]

class ErrorDetail(BaseModel):
    code: str = Field(examples=["invalid_content"])
    message: str = Field(examples=["File does not look like an HDFS log."])

class ErrorResponse(BaseModel):
    error: ErrorDetail