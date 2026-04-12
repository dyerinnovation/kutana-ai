# Screen Sharing & Agent Vision — Architecture Pattern

> Research basis: `/Users/jonathandyer/Documents/dev/research-and-planning/kutana-screen-sharing-research.md` (April 2026)

## Overview

Screen sharing is a first-class LiveKit track type (`TrackSource.ScreenShare`). The SFU forwards it to all subscribers without special server-side handling. Agents receive the track via the standard `track_subscribed` event, consume frames via `VideoStream`, and expose a `kutana_screenshot` MCP tool to reason over them using Claude's vision API.

---

## Encoding

| Property | Recommendation |
|----------|---------------|
| Codec | VP9 preferred (sharp edges, text, UI). H264 fallback. |
| `contentHint` | Set `"text"` on the `MediaStreamTrack` to improve encoding quality for UI/code content. |
| Simulcast | Single high-quality layer only (multiple layers hurt legibility at lower resolutions). |
| Frame rate | 5–15 fps is sufficient for screen content. |

---

## Client Publishing

### Web (React)
```ts
await room.localParticipant.setScreenShareEnabled(true, { contentHint: "text" });
```
Triggers browser's native `getDisplayMedia()` picker. Handle remote tracks via `trackSubscribed` event; detect `TrackSource.ScreenShare` and render in a dedicated panel separate from camera tiles.

### Electron
Electron does not surface a native `getDisplayMedia` picker. Intercept it in `main.ts`:
```ts
session.defaultSession.setDisplayMediaRequestHandler(async (request, callback) => {
  const sources = await desktopCapturer.getSources({ types: ['screen', 'window'] });
  callback({ video: sources[0] }); // or present a picker UI
});
```
After this, the renderer-side LiveKit JS SDK call (`setScreenShareEnabled`) works identically to the web client — no LiveKit-specific Electron code needed.

### Android
Use `MediaProjection` API with a foreground service:
- Declare `android:foregroundServiceType="mediaProjection"` in `AndroidManifest.xml`
- Request permission via `mediaProjectionManager.createScreenCaptureIntent()` (non-bypassable system dialog)
- Pass result to `ScreenCaptureParams(mediaProjectionPermissionResultData = resultData)`
- Call `room.localParticipant.setScreenShareEnabled(true, screenCaptureParams)`

### iOS
- **v1 (in-app):** `room.localParticipant.setScreenShare(enabled: true)` with default `captureMode: .inApp`. No extensions required, but only captures content within the Kutana app.
- **v2 (full device):** Requires a Broadcast Upload Extension (separate process, App Group, IPC) — defer to v2.

---

## Agent Gateway — VideoStream Pipeline

When a screen share track is published, the Agent Gateway subscribes via the Python SDK and buffers the latest frame:

```python
from livekit import rtc

latest_frame: rtc.VideoFrame | None = None

@room.on("track_subscribed")
def on_track_subscribed(track, pub, participant):
    if track.kind == rtc.TrackKind.KIND_VIDEO and \
       pub.source == rtc.TrackSource.SOURCE_SCREENSHARE:
        asyncio.ensure_future(capture_frames(track))

async def capture_frames(track: rtc.RemoteVideoTrack):
    global latest_frame
    async for event in rtc.VideoStream(track):
        latest_frame = event.frame  # overwrite with latest only
```

Frame → PIL → base64 PNG conversion:
```python
from livekit.rtc import VideoBufferType
from PIL import Image
import base64, io

def frame_to_base64_png(frame: rtc.VideoFrame) -> str:
    rgba = frame.convert(VideoBufferType.RGBA)
    img = Image.frombytes("RGBA", (rgba.width, rgba.height), bytes(rgba.data))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
```

`livekit-agents[images]` provides an `encode()` helper that performs this conversion automatically.

---

## `kutana_screenshot` MCP Tool

Registered alongside existing MCP tools (e.g. `kutana_raise_hand`):

```python
@mcp_tool(
    name="kutana_screenshot",
    description="Capture the current state of the shared screen. Returns a vision-model description of what is visible. Only works when a participant is actively sharing their screen.",
    required_capability="screen_view",
)
async def kutana_screenshot(ctx: ToolContext) -> dict:
    if latest_frame is None:
        return {"error": "No screen share active in this room"}
    b64 = frame_to_base64_png(latest_frame)
    response = await anthropic.messages.create(
        model="claude-sonnet-4-6",
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}},
            {"type": "text", "text": "Describe what is visible on this screen."}
        ]}],
    )
    await broadcast_chat("Agent took a screenshot of the shared screen.")
    return {"description": response.content[0].text}
```

Use `claude-sonnet-4-6` for vision calls — best balance of quality and cost for 1080p UI/code screenshots.

---

## Privacy Rules

| Rule | Detail |
|------|--------|
| On-demand only | `kutana_screenshot` fires only on explicit `tool_use` in the agent's reasoning loop — no passive background capture. |
| Chat broadcast | Every screenshot triggers `kutana.chat` message: "Agent [name] took a screenshot at [time]." |
| UI banner | MeetingRoomPage shows a banner when screen share is active AND an agent with `screen_view` capability is in the room. |
| No persistence | Base64 frame data is used in-memory for the Anthropic API call only — never stored in PostgreSQL or Redis. |
| Latest frame only | Only the most recent frame is buffered (`latest_frame`). No historical frame buffer. |
| Capability gate | Agent must declare `screen_view` capability at join time to access the tool. |

---

## Rate Limits

- 5 screenshots per minute per agent (Redis sliding window — same pattern as other MCP tools).
- Consider downscaling to 1280×720 before encoding to reduce API latency and token cost.
- 1080p PNG screenshots are typically 500 KB–3 MB depending on content complexity.
- Expected Anthropic API round-trip: 1–4 seconds for a `claude-sonnet-4-6` vision call.
