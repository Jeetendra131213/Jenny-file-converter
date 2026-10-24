# AnyFile Converter

A Flask-based file converter with real server-side conversions. It includes PDF/document, image, spreadsheet/CSV, and video/audio tools.

## Architecture and hosting

- Frontend: HTML, CSS, vanilla JavaScript.
- Backend: Flask + conversion libraries.
- FFmpeg handles audio extraction/transcoding; LibreOffice handles Office-to-PDF.
- **Recommended deployment:** Docker-capable host (for example, Render web service using the included Dockerfile). The Docker image installs FFmpeg and LibreOffice. A basic Python-only host may not provide those system packages.
- This is an MVP, not a high-volume conversion service. Public deployment needs monitoring, resource limits, and abuse protection.

## Local setup (Windows)

1. Install Python 3.11 or 3.12.
2. Install FFmpeg and LibreOffice, and ensure `ffmpeg.exe` and `soffice.exe`/`libreoffice` are on PATH. Windows installers: https://ffmpeg.org/download.html and https://www.libreoffice.org/download/download-libreoffice/
3. Open PowerShell in this folder:
   ```powershell
   py -3.12 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install --upgrade pip
   pip install -r requirements.txt
   python app.py
   ```
4. Open http://127.0.0.1:5000

If PowerShell blocks activation, run `Set-ExecutionPolicy -Scope Process Bypass` in that terminal, then activate again.

## Supported conversions

- PDF → DOCX (layout may vary; scanned PDFs need OCR)
- PDF → XLSX (extracts detected tables; otherwise exports text lines)
- PDF → PPTX (each page is a slide image, not editable slide text)
- DOCX/XLSX/PPTX → PDF (LibreOffice)
- TXT → PDF/DOCX
- JPG/JPEG/PNG → PDF; PNG/JPG/WEBP image conversions
- CSV → XLSX; XLSX → CSV (first worksheet)
- MP4/MKV/MOV/AVI/WEBM → MP3/WAV/M4A/AAC/FLAC
- WAV ↔ MP3
- Merge multiple PDFs; split a PDF into one-page PDFs in a ZIP

Some conversions are lossy or approximate. The app does not include OCR.

## Deploy using Docker on Render

1. Push this project to a GitHub repository.
2. In Render, choose **New + → Web Service**, connect the repository.
3. Select **Docker** as the runtime/environment and use the repository root as the Docker context.
4. Add environment variables:
   - `MAX_UPLOAD_MB` = `100`
   - `FILE_TTL_HOURS` = `2`
   - `CONVERTER_TEMP_DIR` = `/tmp`
5. Deploy. Render provides a public HTTPS URL. Open it and test with small sample files.
6. Check the Render logs if conversion fails. Confirm the service has enough memory/disk for the files you test.

Free hosting policies, availability, and resource limits change. Large media conversions may exceed free-tier CPU, memory, execution, or disk limits; use a paid instance if necessary. Temporary files are ephemeral and should not be treated as permanent storage.

## GitHub upload

```bash
git init
git add .
git commit -m "Build AnyFile Converter"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/anyfile-converter.git
git push -u origin main
```

Create the empty repository on GitHub first and replace `YOUR-USERNAME` with your account name.

## Testing checklist

- Test each listed conversion using small, non-sensitive sample files.
- Test wrong extensions, corrupt files, empty submissions, and uploads above `MAX_UPLOAD_MB`.
- Test PDF merge with 2+ PDFs and split with a multi-page PDF.
- Verify download links expire after `FILE_TTL_HOURS`.
- Test mobile layout and deployed HTTPS URL.
- Check logs for dependency or resource errors; do not upload confidential files to a public test deployment.

## Security and limitations

- Upload size is capped; random per-job IDs are used; downloads are limited to known conversion IDs.
- Temporary files are deleted after expiry by a cleanup thread, and after failed conversions. On a host that stops the process, cleanup runs when the service is alive again.
- Files are processed on the server. Avoid uploading sensitive documents. HTTPS is provided by the deployment platform.
- There is no login, persistent storage, OCR, distributed queue, or strong per-IP rate limiting in this MVP. For public high-traffic use, add a reverse-proxy rate limit, job queue, malware scanning, and isolated workers.
