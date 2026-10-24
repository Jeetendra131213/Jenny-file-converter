import os, uuid, shutil, tempfile, threading, time
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, abort
from werkzeug.utils import secure_filename
from werkzeug.exceptions import RequestEntityTooLarge
from converters import convert_file, merge_pdfs, split_pdf

BASE = Path(os.environ.get("CONVERTER_TEMP_DIR", tempfile.gettempdir())) / "anyfile-converter"
BASE.mkdir(parents=True, exist_ok=True)
MAX_MB = int(os.environ.get("MAX_UPLOAD_MB", "500"))
TTL_HOURS = int(os.environ.get("FILE_TTL_HOURS", "2"))
app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
jobs = {}
lock = threading.Lock()

def cleanup_loop():
    while True:
        now = time.time()
        with lock:
            for key, item in list(jobs.items()):
                if now - item["created"] > TTL_HOURS * 3600:
                    shutil.rmtree(item["dir"], ignore_errors=True)
                    jobs.pop(key, None)
        for p in BASE.iterdir():
            try:
                if now - p.stat().st_mtime > TTL_HOURS * 3600:
                    shutil.rmtree(p, ignore_errors=True)
            except OSError:
                pass
        time.sleep(600)

threading.Thread(target=cleanup_loop, daemon=True).start()

@app.get("/")
def home():
    return render_template("index.html", max_mb=MAX_MB)

@app.get("/health")
def health():
    return jsonify({"status":"ok"})

@app.post("/api/convert")
def convert():
    tool = request.form.get("tool", "convert")
    output_format = request.form.get("output_format", "").lower().strip().lstrip(".")
    bitrate = request.form.get("bitrate", "192k")
    uploads = request.files.getlist("files")
    if not uploads or all(not f.filename for f in uploads):
        return jsonify(error="Choose at least one file."), 400
    if tool not in ("convert", "merge-pdf", "split-pdf"):
        return jsonify(error="Unsupported tool."), 400
    if tool == "convert" and not output_format:
        return jsonify(error="Choose an output format."), 400
    jid = uuid.uuid4().hex
    work = BASE / jid
    inp, out = work / "input", work / "output"
    inp.mkdir(parents=True); out.mkdir()
    try:
        paths = []
        for f in uploads:
            safe = secure_filename(f.filename or "")
            if not safe:
                raise ValueError("Invalid filename.")
            dest = inp / (uuid.uuid4().hex[:8] + "_" + safe)
            f.save(dest)
            paths.append(dest)
        if tool == "merge-pdf":
            result = merge_pdfs(paths, out)
            outname = result.name
        elif tool == "split-pdf":
            results = split_pdf(paths[0], out)
            if len(results) == 1:
                result = results[0]; outname = result.name
            else:
                import zipfile
                result = out / "split-pages.zip"
                with zipfile.ZipFile(result, "w", zipfile.ZIP_DEFLATED) as z:
                    for p in results: z.write(p, p.name)
                outname = result.name
        else:
            result = convert_file(paths, output_format, out, bitrate)
            outname = result.name
        if not result.exists() or result.stat().st_size == 0:
            raise RuntimeError("The converter did not produce a valid output file.")
        with lock:
            jobs[jid] = {"dir":str(work), "created":time.time(), "result":str(result), "name":outname}
        return jsonify(id=jid, filename=outname, download_url=f"/api/download/{jid}")
    except Exception as e:
        shutil.rmtree(work, ignore_errors=True)
        msg = str(e)
        if "No such file or directory" in msg and ("ffmpeg" in msg.lower() or "libreoffice" in msg.lower()):
            msg = "A required system tool is missing. Check the deployment dependencies and logs."
        return jsonify(error=msg[:500]), 400

@app.get("/api/download/<jid>")
def download(jid):
    with lock:
        item = jobs.get(jid)
    if not item or time.time() - item["created"] > TTL_HOURS * 3600:
        abort(404, description="This download has expired. Convert the file again.")
    path = Path(item["result"])
    if not path.is_file():
        abort(404, description="Converted file is no longer available.")
    return send_file(path, as_attachment=True, download_name=item["name"], conditional=True)

@app.errorhandler(RequestEntityTooLarge)
def too_large(_):
    return jsonify(error=f"File too large. Maximum upload size is {MAX_MB} MB."), 413

@app.errorhandler(404)
def not_found(e):
    if request.path.startswith("/api/"):
        return jsonify(error=getattr(e, "description", "Not found.")), 404
    return "Page not found", 404

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
