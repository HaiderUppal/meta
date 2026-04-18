# Ghost Protocol

Metadata erasure engine. Cleans and spoofs metadata on images and videos. All processing runs in the browser — nothing is uploaded.

## Structure

- `index.html` — landing
- `images.html` — JPEG / PNG lossless metadata strip + EXIF spoof (GPS, camera)
- `videos.html` — MP4 / MOV / M4V stream-copy remux + metadata spoof (GPS, camera) via ffmpeg.wasm
- `metadata_cleaner.py` — optional Python CLI (same philosophy as images.html)

## Deploy

### Netlify Drop — easiest, no terminal

1. Go to https://app.netlify.com/drop
2. Drag the entire `GHOST METADATA` folder onto the page
3. Wait for deploy — you'll get a URL like `ghost-protocol-xyz.netlify.app`
4. Done. Share the URL or set a custom domain from the Netlify dashboard.

The included `netlify.toml` sets COOP/COEP headers so ffmpeg.wasm runs at full speed.

### Vercel

Drag-and-drop via the Vercel dashboard, or connect the repo for auto-deploy on every commit.

### GitHub Pages

Push the folder to a GitHub repo → Settings → Pages → source: `main` branch, root → Save.

## Local testing

The videos page needs HTTP (not `file://`) because ffmpeg.wasm loads via `fetch`. From this folder:

```
python3 -m http.server 8000
```

Open `http://localhost:8000`.

The images page works on `file://` directly — open `index.html`.

## Technical notes

- Image processing is zero-dependency. JPEG and PNG are byte-exact lossless — metadata segments are stripped at the binary level and replaced with a hand-built EXIF block.
- Video processing uses ffmpeg stream-copy (`-c copy -map_metadata -1`) — no re-encode, bit-identical video and audio.
- Videos: MP4 / MOV / M4V, under 500 MB (browser memory ceiling).

## Contact

inararecs@gmail.com
