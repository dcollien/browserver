# 🌐 Browserver

> **The inside-out web server.** \> *Turn your browser tab into a file host.*

**Browserver** is a "reverse" web server. Instead of hosting files on a cloud server, the server acts as a tunnel. The *browser itself* reads files from your local disk (via the File System Access API) and streams them to the public web in real-time.

## ✨ How it Works

1.  **The Hub:** You run a lightweight FastAPI server (the "Tunnel").
2.  **The Admin:** You visit the admin page and select a local folder using the native Directory Picker.
3.  **The Tunneling:** The browser establishes a **Server-Sent Events (SSE)** connection to the Hub.
4.  **The Magic:** When an outsider requests `http://server/cool-slug/image.png`:
      * The Hub pauses the request.
      * The Hub pings your Browser via SSE: *"I need image.png"*.
      * Your Browser reads the file from disk and uploads it.
      * The Hub unpauses the request and serves the file.

## 🚀 Quick Start

### Prerequisites

  * Python 3.11+
  * [uv](https://github.com/astral-sh/uv)

### Installation & Running

1.  **Clone or create the project:**
    Ensure your directory looks like this:

    ```text
    browserver/
    ├── main.py          # The FastAPI Hub
    ├── pyproject.toml   # Dependencies
    └── client/
        └── index.html   # The "Server" Logic
    ```

2.  **Run with one command:**
    Browserver uses `uv` to handle virtual environments and dependencies automatically.

    ```bash
    uv run uvicorn main:app --reload
    ```

3.  **Become the Server:**

      * Open your browser to `http://localhost:8000`.
      * You will be redirected to a unique session (e.g., `/admin/happy-otter`).
      * Click **"Select Directory to Host"** and grant permission.

4.  **Test it:**

      * Click the **Public Link** generated on the page.
      * Any file in your selected folder is now accessible via that URL\!

## 📦 Dependencies

Defined in `pyproject.toml`:

  * **FastAPI**: The web framework.
  * **Uvicorn**: The ASGI server.
  * **SSE-Starlette**: For real-time signaling to the browser.
  * **Coolname**: For generating readable slugs (e.g., `brave-lion`).

## ⚠️ Limitations & Security

  * **HTTPS Required:** The [File System Access API](https://developer.mozilla.org/en-US/docs/Web/API/File_System_API) is a powerful feature. Browsers only allow it on **secure contexts** (HTTPS) or `localhost`. If you deploy the `main.py` hub to a public server (like AWS or Heroku), you **must** use HTTPS (SSL), or the "Select Directory" button will do nothing.
  * **Tab Must Stay Open:** Since the browser *is* the file server, closing the tab kills the site.
  * **Read-Only:** This implementation allows the public web to *read* your files, but currently does not support *writing* back to your disk (though the API supports it).

## 📄 License

MIT. Go wild.
