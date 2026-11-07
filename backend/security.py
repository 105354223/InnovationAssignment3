# security.py
import os
import re
from pathlib import PurePosixPath
from fastapi.responses import JSONResponse

MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_BYTES", 25 * 1024 * 1024))
# This is to check for unsually large line lengths so if we have a log file 
# with 2000 lines, with 99% of them being correct log lines but one of those lines 
# containing a super long script to do something bad. not going to catch everything but
# will catch some things.
MAX_LINE_LEN = 4096

# This is for tiny log files we just ensure we check a few lines
# to avoid allowing in files that have just one matching line to the log type.
MIN_MATCHING_LINES = 5

# we use this to set the percentage of lines in the log file that 
# will match the expected log structure,  this oculd led to some false positives
# with correct log files with large amounts of errored lines,
# may be room for adjustment here 
MIN_MATCH_RATIO = 0.95

# Setting allowed extension types lets us limit incorrect files and help secure us
# against malicous agents
ALLOWED_EXTENSIONS = {".log", ".txt"}

# Setting a limit for filename lengths will help catch attempted escape prompt injections
# lurking in the file names, or at least cut down on them as well as bogus files
MAX_FILENAME_LEN = 100 

# Setting an allowed filename pattern lets us stop filenames that try and utilise escape characters
_SAFE_FILENAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
_HDFS_LINE = re.compile(r"^\d{6} \d{6} \d+ \S+ \S+: .+$")

# defining a for errors to be expanded on in future
def error_body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


class UploadRejected(Exception):
    def __init__(self, status: int, code: str, message: str):
        self.status, self.code, self.message = status, code, message


# Oversized file checking we use two different checks, checking what the they are claiming
# is their file size, if this is already the file size limit we error them out 
# and an additional check where w ecould the bytes as they are arriving, seeing if they 
# go over their limit
class SizeLimitMiddleware:
    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # the easy check where we see if their declared size is good
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None:
            try:
                too_big = int(declared) > self.max_bytes
            except ValueError:
                return await self._reject(send, 400, "bad_request",
                                          "Invalid Content-Length header.")
            if too_big:
                return await self._reject(send)

        # our own check to count the bytes that actually arrive.
        received, too_large, started = 0, False, False

        async def counting_receive():
            nonlocal received, too_large
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    too_large = True
                    raise RuntimeError("body too large")  # stops parsing
            return message

        async def guarded_send(message):
            nonlocal started
            if too_large:
                return  # drop the 400/500 the app produces after our abort
            if message["type"] == "http.response.start":
                started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not too_large:
                raise
        if too_large and not started:
            await self._reject(send)
# here is where error we are returning on either toolarge check failing
    async def _reject(self, send, status=413, code="payload_too_large",
                      message=None):
        message = message or f"Upload exceeds the {self.max_bytes // 1_048_576} MB limit."
        resp = JSONResponse(error_body(code, message), status_code=status)
        await resp({"type": "http"}, None, send)


# this is the file name checking against being either too long or not existing
def validate_filename(name: str | None) -> str:
    if not name or len(name) > MAX_FILENAME_LEN:
        raise UploadRejected(400, "invalid_filename", "Missing or too-long filename.")
    #whether it includes unallowed characters
    if ".." in name or not _SAFE_FILENAME.match(name):
        raise UploadRejected(400, "invalid_filename",
                             "Filename contains disallowed characters.")
    # this is checking the last suffix only, so "x.log.exe" is rejected.
    if PurePosixPath(name).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UploadRejected(400, "unsupported_file_type",
                             "Only .log and .txt files are accepted.")
    return name


# here is where we are checking the actual contents of the file, where we check
# if the file exists first
def validate_log_content(raw: bytes) -> None:
    #here!
    if not raw:
        raise UploadRejected(400, "empty_file", "The file is empty.")
    # or whether the file is containing binary data
    if b"\x00" in raw:
        raise UploadRejected(400, "invalid_content", "File contains binary data.")
    try:
        text = raw.decode("utf-8")  # strict, no errors="replace"
    #or whether the text isn't proper utf-8 text
    except UnicodeDecodeError:
        raise UploadRejected(400, "invalid_content", "File is not valid UTF-8 text.")
# this is where we utilise the line checking, whether the file is empty
# or has any lines that go over the single line length cap
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines or any(len(ln) > MAX_LINE_LEN for ln in lines):
        raise UploadRejected(400, "invalid_content", "File is empty or has over-long lines.")
# this final section is checking that we have at least 5 matching lines 
# AND that we are hitting our expected ratio of matching lines 
    matching = sum(1 for ln in lines if _HDFS_LINE.match(ln))
    if matching < MIN_MATCHING_LINES or matching / len(lines) < MIN_MATCH_RATIO:
        raise UploadRejected(400, "invalid_content", "File does not look like an HDFS log.")