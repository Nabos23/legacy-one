# Showcase screenshots

The landing page (`components/landing/showcase.tsx`) renders real product
screenshots from this folder. Drop in PNG/WebP files with these exact names:

| File             | Tab        | Suggested capture                          |
| ---------------- | ---------- | ------------------------------------------ |
| `agents.png`     | Agents     | `/client/agents` or `/admin/agents`        |
| `tracing.png`    | Tracing    | `/admin/tracing` or `/client/tracing`      |
| `playground.png` | Playground | `/client/playground` or `/admin/playground`|

Recommended: ~1600×1000px, captured in the **dark** theme for best contrast
inside the glass frame. If a file is missing, the showcase automatically falls
back to a built-in CSS mock — no error.

To add more tabs, edit the `SHOTS` array in `components/landing/showcase.tsx`.
