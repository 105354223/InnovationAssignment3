# Getting Started with Create React App

This project was bootstrapped with [Create React App](https://github.com/facebook/create-react-app).

## Available Scripts

In the project directory, you can run:

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.

## Learn More

You can learn more in the [Create React App documentation](https://facebook.github.io/create-react-app/docs/getting-started).

To learn React, check out the [React documentation](https://reactjs.org/).

### Code Splitting

This section has moved here: [https://facebook.github.io/create-react-app/docs/code-splitting](https://facebook.github.io/create-react-app/docs/code-splitting)

### Analyzing the Bundle Size

This section has moved here: [https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size](https://facebook.github.io/create-react-app/docs/analyzing-the-bundle-size)

### Making a Progressive Web App

This section has moved here: [https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app](https://facebook.github.io/create-react-app/docs/making-a-progressive-web-app)

### Advanced Configuration

This section has moved here: [https://facebook.github.io/create-react-app/docs/advanced-configuration](https://facebook.github.io/create-react-app/docs/advanced-configuration)

### Deployment

This section has moved here: [https://facebook.github.io/create-react-app/docs/deployment](https://facebook.github.io/create-react-app/docs/deployment)

### `npm run build` fails to minify

This section has moved here: [https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify](https://facebook.github.io/create-react-app/docs/troubleshooting#npm-run-build-fails-to-minify)


# 2.6 Questions 
1. Who would want to attack our application? 
The main attackers would be malicious users or intruders who want to hide their activities from being deteected. This could potentially include
hackers who have gained access to a system or insiders attempting to cover up unauthorised actions.

2. What are they trying to achieve? 
Their main goal would be to avoid detection by making malicious activities appear normal within the logs. Attackers may also attempt to manipulate the results. access sensitive infomration which could be contained in the log files or even disrupt the application so that it cannot detect suspicious behaviour.

3. What can they actually do to it?
Attackers could:
    Mainipulate log entries: Insert fake or misleading log messages to hide suspicious activity
    Inject malicious content: Include harmful inputs within log lines to exploit weaknesses in the application's processing or display.
    Upload malicious files: Submit specfically crafted or oversized files to crash the application or consume excessive resources.
    Access sensitive infromation: Attempt to iew log data or detection results without authorisation.



## Defence: Unsafe file upload (Section 2.7, Intermediate)

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

### How to run the demonstration

**Terminal 1 (server)** from the `backend` folder:

| Mode | Command Prompt | Git Bash |
|---|---|---|
| Defence ON (default) | `set HARDENING=on` then `python main.py` | `HARDENING=on python main.py` |
| Defence OFF | `set HARDENING=off` then `python main.py` | `HARDENING=off python main.py` |

Check the variable with `echo %HARDENING%` (Command Prompt). Any value other than `on` disables the defence.

**Terminal 2 (attacks)** in Git Bash, from `backend/testing_files`:

| File | Purpose |
|---|---|
| `sample.log` | valid HDFS log (control) |
| `big.log` | 30 MB file, over the limit |
| `logo.png` | PNG used as fake log |
| `mixed.log` | valid lines followed by junk |

```bash
# 0. Control: must return 200
curl -i -F "file=@sample.log" http://127.0.0.1:8000/analyze

# 1. Oversized (declared Content-Length)
curl -i -F "file=@big.log" http://127.0.0.1:8000/analyze

# 1b. Oversized (chunked, no honest Content-Length)
curl -i -H "Transfer-Encoding: chunked" -F "file=@big.log" http://127.0.0.1:8000/analyze

# 2. Crafted filename
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

| Test | Status | `error.code` 
|---|---|---|---|
| 0. Control | 200 | n/a 
| 1. Oversized | 413 | `payload_too_large` 
| 1b. Oversized, chunked | 413 | `payload_too_large` 
| 2. Crafted filename | 400 | `invalid_filename` 
| 3. PNG as log | 400 | `invalid_content`
| 4a. `sample.log.exe` | 400 | `unsupported_file_type`
| 4b. Empty file | 400 | `empty_file`

## TO CHECK
I tested this purely on the backend but have nesured that the sample that worked before works still, additionally the frontend properly gives an error matching what the issue with the file is, for example trying to upload the big.log will properly give the 
**File too large (28.6 MB). Max 25 MB.** which im happy about and make sure to show in the video!
But the empty file doesn't properly return an error for the front end, just stating a 
error in analyzing file, something to fix but its 4am and im sleepy