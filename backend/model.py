"""
Model wrapper for the HDFS anomaly detection web app.

Loads hdfs_model.joblib once at import time and exposes AnomalyModel.predict().
The loaded model expects a feature table where each row is one HDFS block trace,
with columns:
    length, n_unique, first_event, last_event, event_0 ... event_67
This module re-implements the parsing + templating + featurisation steps so
raw HDFS.log bytes can be converted into that exact table shape.
"""

import re
import joblib
import pandas as pd


# Load model
_MODEL = joblib.load("hdfs_model.joblib")

_LAST_PARSED: pd.DataFrame | None = None


# Regex model patterns
_HDFS_LINE = re.compile(r"^(\d{6}) (\d{6}) (\d+) (\S+) (\S+): (.*)$")
_BLK       = re.compile(r"(blk_-?\d+)")
_BLOCK_ID  = re.compile(r"blk_-?\d+")
_IP_PORT   = re.compile(r"\d+\.\d+\.\d+\.\d+:\d+")
_IP        = re.compile(r"\d+\.\d+\.\d+\.\d+")
_JOB_DIR   = re.compile(r"(/user/root/)\w+")
_NUM       = re.compile(r"\d+")


def _template(msg: str) -> str:
    """ Mask variable parts so equivalent events collapse to one string. """
    msg = _BLOCK_ID.sub("blk_<*>", msg)
    msg = _IP_PORT.sub("<IP:PORT>", msg)
    msg = _IP.sub("<IP>", msg)
    msg = _JOB_DIR.sub(r"\1<JOB>", msg)
    msg = _NUM.sub("<NUM>", msg)
    return msg


def _parse(text: str) -> pd.DataFrame:
    """ Parse raw HDFS log text into a DataFrame of (date, time, blockId, message). """
    rows = []
    for line in text.splitlines():
        m = _HDFS_LINE.match(line)
        if not m:
            continue
        date, time, pid, level, component, message = m.groups()
        blk = _BLK.search(message)
        if not blk:
            continue
        rows.append({
            "date": date,
            "time": time,
            "blockId": blk.group(1),
            "message": message,
        })
    return pd.DataFrame(rows)


def _build_feature_table(df: pd.DataFrame) -> pd.DataFrame:
    """ Turn parsed lines into the per-block feature table the model expects. """
    df = df.copy()
    df["timestamp"] = pd.to_datetime(
        df["date"] + df["time"],
        format="%y%m%d%H%M%S",
        errors="coerce",
        utc=True,
    )
    df = df.dropna(subset=["timestamp"])

    # Template each message
    df["template"] = df["message"].apply(_template)

    # Rebuild the same vocab the training used: sorted template strings -> 0..N-1
    vocab = {t: i for i, t in enumerate(sorted(df["template"].unique()))}
    df["event_id"] = df["template"].map(vocab)

    # Group into per-block traces, chronological order
    traces = (
        df.sort_values("timestamp")
          .groupby("blockId")["event_id"]
          .apply(list)
          .reset_index()
    )
    traces.columns = ["blockId", "sequence"]

    # Summary features
    traces["length"]      = traces["sequence"].apply(len)
    traces["n_unique"]    = traces["sequence"].apply(lambda s: len(set(s)))
    traces["first_event"] = traces["sequence"].apply(lambda s: s[0])
    traces["last_event"]  = traces["sequence"].apply(lambda s: s[-1])

    # Bag-of-events
    exploded = traces[["blockId", "sequence"]].explode("sequence")
    exploded["sequence"] = exploded["sequence"].astype(int)
    bag = (
        exploded.groupby(["blockId", "sequence"])
                .size()
                .unstack(fill_value=0)
                .rename_axis(columns=None)
                .reset_index()
    )
    bag.columns = ["blockId"] + [f"event_{int(c)}" for c in bag.columns[1:]]

    feats = traces[["blockId", "length", "n_unique",
                    "first_event", "last_event"]].merge(
        bag, on="blockId", how="left"
    )

    # The trained pipeline expects 68 event columns (event_0 .. event_67),
    # regardless of how many unique templates appear in this particular
    # uploaded file. Missing events are filled with 0, which is correct:
    # those events didn't occur in this file.
    EXPECTED_EVENT_IDS = 68
    expected = (
        ["length", "n_unique", "first_event", "last_event"]
        + [f"event_{i}" for i in range(EXPECTED_EVENT_IDS)]
    )

    for col in expected:
        if col not in feats.columns:
            feats[col] = 0

    return feats[["blockId"] + expected]


class AnomalyModel:
    """Thin wrapper around the pre-trained HDFS pipeline."""

    def predict(self, raw_bytes: bytes) -> dict:
        """
        Analyse an uploaded HDFS log.

        Returns a dict with:
            summary  : {total_sessions, normal, anomaly}
            sessions : list of {block_id, anomaly_score, label, event_count}
        """
        text = raw_bytes.decode("utf-8", errors="replace")
        df = _parse(text)
        global _LAST_PARSED
        df = _parse(text)
        _LAST_PARSED = df          # keep for /session/{block_id} lookups
        if df.empty:
            return {
                "summary": {"total_sessions": 0, "normal": 0, "anomaly": 0},
                "sessions": [],
                "error": "No valid HDFS lines found",
            }

        feats = _build_feature_table(df)
        feature_cols = [c for c in feats.columns if c != "blockId"]

        # Probability of being Anomaly (LabelEncoder assigned 0 = Anomaly, 1 = Normal)
        probs_anomaly = _MODEL.predict_proba(feats[feature_cols])[:, 0]

        sessions = []
        for i, block_id in enumerate(feats["blockId"]):
            score = float(probs_anomaly[i])
            sessions.append({
                "block_id": block_id,
                "anomaly_score": round(score, 4),
                "label": "Anomaly" if score > 0.5 else "Normal",
                "event_count": int(feats["length"].iloc[i]),
            })

        sessions.sort(key=lambda s: s["anomaly_score"], reverse=True)

        anomaly_count = sum(1 for s in sessions if s["label"] == "Anomaly")
        return {
            "summary": {
                "total_sessions": len(sessions),
                "normal": len(sessions) - anomaly_count,
                "anomaly": anomaly_count,
            },
            "sessions": sessions[:100],     # only the 100 most anomalous
            "session_total": len(sessions),
        }
    
    def get_session_detail(self, block_id: str) -> dict:
        """Return the raw log messages for one block from the last upload."""
        if _LAST_PARSED is None or _LAST_PARSED.empty:
            return {"error": "No file has been uploaded yet"}
        lines = _LAST_PARSED[_LAST_PARSED["blockId"] == block_id]["message"].tolist()
        if not lines:
            return {"error": f"No messages found for {block_id}"}
        return {"block_id": block_id, "messages": lines[:50]}
