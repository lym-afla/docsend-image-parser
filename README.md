# DocSend Image Downloader

This parser recovers a DocSend document as verified page images and an optional PDF. It is intentionally **review-first**: authorization is supplied only for a document the operator is allowed to access, and recovery reports bounded status codes instead of credentials, signed page URLs, or document text.

## Install

This repository uses the dependencies in `requirements.txt`. Run commands through `uv`:

```powershell
uv run --no-project --with-requirements requirements.txt python -m unittest -v
```

Install Tesseract separately when using `tesseract` OCR; `ocrmypdf` also requires its system dependencies.

## Authorized recovery: three-command flow

Use a reviewed `https://docsend.com/view/...` URL and replace only the angle-bracket placeholders below. Send the entire request as JSON on standard input; do not put the URL, email, passcode, or any authorization value in command-line arguments.

1. Run recovery. This starts with the page-one access probe. If it reports `authentication_required`, no pages or PDF are created.

   ```powershell
   @'
   {"url":"https://docsend.com/view/<document-id>/d/<view-id>","cookie_file":"cookies.json","image_directory":"recovery-pages","target_pdf_path":"recovered-document.pdf","ocr_mode":"none","language":"eng"}
   '@ | uv run --no-project --with-requirements requirements.txt python docsend_recover.py
   ```

2. If authorization is required, run the refresh helper. It opens a visible browser for the reviewed document. Supply `email` and `passcode` only when they are approved and needed; both remain stdin-only. The helper owns `cookies.json`: it replaces that file only after the browser candidate succeeds at a second access probe. A failed or interrupted refresh preserves the previous file.

   ```powershell
   @'
   {"url":"https://docsend.com/view/<document-id>/d/<view-id>","cookie_file":"cookies.json","email":"<approved-email>","passcode":"<approved-passcode>","approved_at":"<approval-timestamp>"}
   '@ | uv run --no-project --with-requirements requirements.txt python docsend_cookie_refresh.py
   ```

   When CAPTCHA or OTP appears, complete it yourself in the visible browser while the helper is still running. The helper keeps Chrome open for a bounded human-interaction window, then resumes the authorization state loop and re-probes the requested document before replacing the cookie file. If the window expires, Chrome closes and the JSON response says `user_interaction_required` with `captcha_detected` or `otp_detected`; rerun only with the required approval. The helper does not bypass CAPTCHA or OTP challenges. Do not manually edit or copy cookie values into `cookies.json`.

3. Run the same recovery request again.

   ```powershell
   @'
   {"url":"https://docsend.com/view/<document-id>/d/<view-id>","cookie_file":"cookies.json","image_directory":"recovery-pages","target_pdf_path":"recovered-document.pdf","ocr_mode":"none","language":"eng"}
   '@ | uv run --no-project --with-requirements requirements.txt python docsend_recover.py
   ```

Treat recovery as successful only when its JSON has `status: "success"`, a continuous `downloaded_pages` sequence, and `pdf_page_count` equal to `expected_pages`. The parser verifies image bytes by their decodable image signature, including when the server labels a valid image as `binary/octet-stream`.

### Authorization safety

The presence of cookie keys, a local `cookies.json`, or a browser session does **not** prove authorization. The parser’s access probe is the decision point. Keep cookie files, browser traces, downloaded pages, and PDFs local; they are ignored by Git.

The public command responses include only status, counts, OCR mode, and bounded diagnostic codes. Do not add verbose browser/network logging to obtain authorization details.

## Legacy components

`docsend_image_downloader.py` and `compile_to_pdf.py` remain available for local, already-authorized use. Prefer `docsend_recover.py` for new work because it enforces the access probe, continuous-page check, and matching PDF page-count check.
