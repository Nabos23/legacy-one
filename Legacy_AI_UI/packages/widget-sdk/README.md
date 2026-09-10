# @one-ai/widget

Typed loader for the One-AI embeddable chatbot widget.

This package contains **no widget logic**. It injects the hosted `widget.js`
from your One-AI deployment — so every embed stays on the latest loader
automatically — and wraps `window.OneAIWidget` in a typed, promise-based API
that plays well with SPA lifecycles.

If you don't need types or a package manager, the plain `<script>` snippet
from the dashboard's **Embed Code** tab does the same thing.

## Install

```bash
npm install @one-ai/widget
```

## Usage

```ts
import { initWidget, destroyWidget } from '@one-ai/widget'

const widget = await initWidget({
  widgetId: 'YOUR_WIDGET_ID',   // dashboard → widget → Embed Code
  apiUrl: 'https://api.your-one-ai.com',
  chatUrl: 'https://app.your-one-ai.com',
})

widget.open()      // also: close(), toggle()
widget.destroy()   // full teardown (SPA unmount)
```

### React

```tsx
import { useEffect } from 'react'
import { initWidget, destroyWidget } from '@one-ai/widget'

export function OneAIChatWidget() {
  useEffect(() => {
    void initWidget({
      widgetId: process.env.NEXT_PUBLIC_ONEAI_WIDGET_ID!,
      apiUrl: process.env.NEXT_PUBLIC_ONEAI_API_URL!,
      chatUrl: process.env.NEXT_PUBLIC_ONEAI_CHAT_URL!,
    })
    return () => destroyWidget()
  }, [])
  return null
}
```

Re-initializing replaces any existing instance instead of stacking launchers,
so hot reloads and remounts are safe.

## Notes

- The widget only activates on origins added to the widget's **allowed
  origins** list in the dashboard.
- `previewToken` exists for the dashboard's draft-preview flow; omit it in
  production.

## Publishing (maintainers)

```bash
cd packages/widget-sdk
npm run build     # dist/index.js + index.cjs + index.d.ts
npm publish --access restricted
```
