# Next.js template

This is a Next.js template with shadcn/ui.

## Testing the Modal reframe logic

The face-layout switch lives in `modal/main.py`. Use the Modal `reframe` endpoint to test it with two kinds of clips:

- a podcast clip with `1-2` visible faces, which should keep the existing active-speaker behavior
- a stream/panel clip with `3+` visible faces, which should switch to the blurred letterbox layout with the larger foreground

### 1. Start the Modal app

```bash
modal serve modal/main.py
```

Modal will print the `AIReframe.reframe` endpoint URL in the terminal.

### 2. Send a test request

Replace the URL below with the endpoint Modal prints:

```bash
curl -X POST 'https://ms8460149--makemyclip-ai-rendering-aireframe-reframe.modal.run' \
  -H 'Content-Type: application/json' \
  -d '{
    "video_url": "https://pub-dab84dec13074258806f788a00943c46.r2.dev/clip2.mp4",
    "start_time": 0,
    "end_time": 23,
    "fps": 25,
    "transcript": [],
    "show_watermark": false
  }'
```

If you want to test a YouTube source, use a YouTube URL in `video_url` instead of a direct MP4.
If your test clip is local, `video_url` still needs to be a reachable HTTP URL.
The simplest approach is to upload `clip.mp4` to R2/S3 or expose it through a temporary public URL, then paste that URL into the request body.

### 3. Verify the result

- For `1-2` faces, confirm the output still behaves like before.
- For `3+` faces, confirm the output uses the blurred background and keeps the main content taller instead of collapsing to a single-person crop.
- If the layout flips too easily on borderline clips, use a clip with sustained 3+ faces for a few seconds so the stabilized face-count decision is easier to observe.

## Adding components

To add components to your app, run the following command:

```bash
npx shadcn@latest add button
```

This will place the ui components in the `components` directory.

## Using components

To use the components in your app, import them as follows:

```tsx
import { Button } from "@/components/ui/button";
```
