

## How to start the backend

To set up the backend ensure you have run these commands:

pip install -r requirements.txt
python main.py

By deafult our system runs with the defenses enabled so if you wish to
test without any defenses running ensure you run HARDENING="off" before running the python main.py

The back end is running when you see `Uvicorn running on http://127.0.0.1:8000`.
Leave this terminal open.


## how to start the front end

Ensure you're inside the frontend folder and then

npm install

npm start

The app opens at http://localhost:3000. If it does not open by itself, go to that
address in your browser. Leave this terminal open too.


# 2.6 Threat Model
1. Who would want to attack our application? 
The main attackers would be malicious users or intruders who want to hide their activities from being detected by their log files. This could potentially include
hackers who have gained access to a system or insiders attempting to cover up unauthorised actions.

2. What are they trying to achieve? 
Their main goal would be to avoid detection by making malicious activities appear normal within the logs. Attackers may also attempt to manipulate the results. access sensitive infomration which could be contained in the log files or even disrupt the application so that it cannot detect suspicious behaviour.

3. What can they actually do to it?
Attackers could:
    **Mainipulate log entries:** Insert fake or misleading log messages to hide suspicious activity
    **Inject malicious content:** Include harmful inputs within log lines to exploit weaknesses in the application's processing or display.
    **Upload malicious files:** Submit specfically crafted or oversized files to crash the application or consume excessive resources.
    Access sensitive infromation: Attempt to view log data or detection results without authorisation.



## Section 2.7, Intermediate Unsafe File Upload

### Threat addressed
The `/analyze` endpoint accepts a log file. An attacker bypassing the
front end can send an oversized body, a crafted filename, or content that is not
an HDFS log. Frontend checks are for usability only; every check below is
enforced on the back end in `backend/security.py`.

### Layers
1. **Size cap:** rejects bodies over 25 MB with `413` before the
   multipart body is parsed. Checks the declared `Content-Length` and also counts
   bytes actually received, so chunked uploads with no honest header are caught.
2. **Filename validation:** allows a list of characters, no `..`, length limit, and the
   final extension must be `.log` or `.txt` (so `x.log.exe` fails). The filename is
   never used as a storage path.
3. **Content validation:** rejects empty files, NUL bytes, invalid UTF-8, lines over
   4096 characters, and files where fewer than 95% of *all* lines (minimum 5) match
   the HDFS line format. The `Content-Type` header and extension are not trusted.

All rejections use the shared error format `{"error": {"code": ..., "message": ...}}`.



**Terminal 2 (attacks)** in Git Bash, from `backend/testing_files`:

`sample.log`  valid HDFS log (control) 
`big.log`  30 MB file, over the limit 
`logo.png`  PNG used as fake log 

```bash
# 0. Control: must return 200
curl -i -F "file=@sample.log" http://127.0.0.1:8000/analyze

# 1. Oversized (declared Content-Length)
curl -i -F "file=@big.log" http://127.0.0.1:8000/analyze

# 1b. Oversized (chunked, no honest Content-Length)
curl -i -H "Transfer-Encoding: chunked" -F "file=@big.log" http://127.0.0.1:8000/analyze

# 2. Fake filename
curl -i -F "file=@sample.log;filename=../../etc/passwd" http://127.0.0.1:8000/analyze

# 3. Wrong content claiming to be a log
curl -i -F "file=@logo.png;filename=hdfs.log;type=text/plain" http://127.0.0.1:8000/analyze

# 4. Variations
#double extension
curl -i -F "file=@sample.log;filename=sample.log.exe" http://127.0.0.1:8000/analyze   # 
#empty file
curl -i -F "file=@empty.log" http://127.0.0.1:8000/analyze                           
```

Run every command once with the defence **OFF**, then again with it **ON**.

### Results (hopefully if it works on yours)

 Test, Status, `error.code` 

0. Control  200  n/a 
1. Oversized  413  `payload_too_large` 
1b. Oversized, chunked  413  `payload_too_large` 
2. Crafted filename  400  `invalid_filename` 
3. PNG as log  400  `invalid_content`
4a. `sample.log.exe`  400  `unsupported_file_type`
4b. Empty file  400  `empty_file`

## TO CHECK
I tested this purely on the backend but have ensured that the sample that worked before works still, additionally the frontend properly gives an error matching what the issue with the file is, for example trying to upload the big.log will properly give the 
**File too large (28.6 MB). Max 25 MB.** which im happy about and make sure to show in the video!
But the empty file doesn't properly return an error for the front end, just stating a 
error in analyzing file, something to fix but its 4am and im sleepy

### 2.7 Basic rate limiting

pip install slowapi


### Start the server in each mode (not at the same time)
Run from the `backend` folder in a separate terminal from the attacks.

Defences ON (default) `python main.py`
Defences OFF `set HARDENING=off` then `python main.py` 

`HARDENING=off` disables the size limit, filename and content validation, and
the rate limiter, so the attacks succeed.

### Run the attacks
From `backend/testing_files` in Git Bash:

```bash
# Control: must return 200
curl -i -F "file=@sample.log" http://127.0.0.1:8000/analyze

# Upload defence
curl -i -F "file=@big.log" http://127.0.0.1:8000/analyze
curl -i -H "Transfer-Encoding: chunked" -F "file=@big.log" http://127.0.0.1:8000/analyze
curl -i -F "file=@sample.log;filename=../../etc/passwd" http://127.0.0.1:8000/analyze
curl -i -F "file=@logo.png;filename=hdfs.log;type=text/plain" http://127.0.0.1:8000/analyze
curl -i -F "file=@mixed.log" http://127.0.0.1:8000/analyze
curl -i -F "file=@sample.log;filename=sample.log.exe" http://127.0.0.1:8000/analyze
curl -i -F "file=@empty.log" http://127.0.0.1:8000/analyze

# Rate limiting defence
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "%{http_code}\n" -F "file=@sample.log" http://127.0.0.1:8000/analyze
done

# Rate limiting variation: spoofed X-Forwarded-For
for i in $(seq 1 8); do
  curl -s -o /dev/null -w "%{http_code}\n" -H "X-Forwarded-For: 10.0.0.$i" \
    -F "file=@sample.log" http://127.0.0.1:8000/analyze
done
```

### Expected results
Flood (8 requests) 200 x5, then 429 x3 (if defences off then 200 x8)
Spoofed `X-Forwarded-For`200 x5, then 429 x3  (same as above if done correctly)

