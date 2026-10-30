# OmniVox Consumer Portal

The consumer portal is a Vite/React application served on port `3000` during development. It uses the local FastAPI gateway on port `8000` for safe configuration and WebRTC signalling.

## Run locally

```powershell
python -m uvicorn backend.api.app:app --host 127.0.0.1 --port 8000
cd consumer_ui
npm run dev
```

Open `http://127.0.0.1:3000/`. The browser requests a microphone only after the guest selects **Connect**. Push-to-Talk begins muted by default, avoiding an accidental open microphone.

## Embed the floating concierge

After publishing the built `voice-widget.js` asset, place this one line on a trusted hotel site:

```html
<script src="https://concierge.example.com/voice-widget.js" data-tenant="grand-meridian" data-app-url="https://concierge.example.com/" defer></script>
```

The script mounts an isolated Shadow DOM launcher and a microphone-permitted iframe. Set `data-autostart="false"` and call `window.OmniVoxWidget.mount({...})` when the host page needs explicit control.

No card, CVV, or bank data is collected by this portal. Screen interactions are conversational context only; booking, cancellation, and payment actions still require the backend’s mandatory confirmation and secure-provider gates.
