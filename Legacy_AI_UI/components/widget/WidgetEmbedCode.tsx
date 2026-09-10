'use client'

import { useState } from 'react'
import { Check, Copy, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { API_BASE_URL } from '@/lib/config'

interface WidgetEmbedCodeProps {
  widgetId: string
}

type PlatformKey = 'html' | 'react' | 'vue' | 'angular' | 'wordpress' | 'shopify' | 'gtm'

const PLATFORMS: { key: PlatformKey; label: string }[] = [
  { key: 'html', label: 'HTML' },
  { key: 'react', label: 'React / Next.js' },
  { key: 'vue', label: 'Vue' },
  { key: 'angular', label: 'Angular' },
  { key: 'wordpress', label: 'WordPress' },
  { key: 'shopify', label: 'Shopify' },
  { key: 'gtm', label: 'Google Tag Manager' },
]

/** Everything is the same loader under the hood -- widget.js + OneAIWidget.init.
 * The per-platform variants just wrap that in the idiom each stack expects. */
function buildSnippets(widgetId: string, apiUrl: string, chatUrl: string): Record<PlatformKey, { note: string; code: string }> {
  const initArgs = `{
      widgetId: '${widgetId}',
      apiUrl: '${apiUrl}',
      chatUrl: '${chatUrl}'
    }`

  const htmlSnippet = `<script src="${chatUrl}/widget.js" defer></script>
<script>
  window.addEventListener('load', function () {
    OneAIWidget.init(${initArgs});
  });
</script>`

  return {
    html: {
      note: 'Paste this before the closing </body> tag of any page you want the chat widget on.',
      code: htmlSnippet,
    },
    react: {
      note: 'Add this component once, e.g. in your root layout (Next.js App Router: mark it "use client"). It loads the script on mount and cleans up on unmount.',
      code: `'use client'

import { useEffect } from 'react'

export function OneAIChatWidget() {
  useEffect(() => {
    const script = document.createElement('script')
    script.src = '${chatUrl}/widget.js'
    script.defer = true
    script.onload = () => {
      window.OneAIWidget?.init(${initArgs})
    }
    document.body.appendChild(script)
    return () => {
      window.OneAIWidget?.destroy?.()
      script.remove()
    }
  }, [])

  return null
}

// TypeScript: declare the global once, e.g. in a globals.d.ts
// declare global { interface Window { OneAIWidget?: any } }`,
    },
    vue: {
      note: 'Drop this component into your root App.vue (Vue 3, script setup). It loads the script on mount.',
      code: `<script setup>
import { onMounted, onUnmounted } from 'vue'

let script

onMounted(() => {
  script = document.createElement('script')
  script.src = '${chatUrl}/widget.js'
  script.defer = true
  script.onload = () => {
    window.OneAIWidget?.init(${initArgs})
  }
  document.body.appendChild(script)
})

onUnmounted(() => {
  window.OneAIWidget?.destroy?.()
  script?.remove()
})
</script>

<template><!-- renders nothing; the widget attaches to <body> --></template>`,
    },
    angular: {
      note: 'Add this to your root component (e.g. app.component.ts). It loads the script after the view initializes.',
      code: `import { AfterViewInit, Component, OnDestroy } from '@angular/core';

declare global {
  interface Window { OneAIWidget?: any }
}

@Component({ selector: 'app-root', templateUrl: './app.component.html' })
export class AppComponent implements AfterViewInit, OnDestroy {
  private script?: HTMLScriptElement;

  ngAfterViewInit(): void {
    this.script = document.createElement('script');
    this.script.src = '${chatUrl}/widget.js';
    this.script.defer = true;
    this.script.onload = () => {
      window.OneAIWidget?.init(${initArgs});
    };
    document.body.appendChild(this.script);
  }

  ngOnDestroy(): void {
    window.OneAIWidget?.destroy?.();
    this.script?.remove();
  }
}`,
    },
    wordpress: {
      note: "Add this to your theme's functions.php (or a small custom plugin). Alternatively, paste the plain HTML snippet into a footer HTML widget or a plugin like WPCode.",
      code: `function oneai_chat_widget() {
  ?>
${htmlSnippet
  .split('\n')
  .map(l => '  ' + l)
  .join('\n')}
  <?php
}
add_action('wp_footer', 'oneai_chat_widget');`,
    },
    shopify: {
      note: 'In your Shopify admin: Online Store → Themes → Edit code → layout/theme.liquid, paste this just before </body>.',
      code: htmlSnippet,
    },
    gtm: {
      note: 'In Google Tag Manager: create a Custom HTML tag with this content, trigger it on All Pages (Page View), then publish the container.',
      code: htmlSnippet,
    },
  }
}

export function WidgetEmbedCode({ widgetId }: WidgetEmbedCodeProps) {
  const [copied, setCopied] = useState(false)
  const [platform, setPlatform] = useState<PlatformKey>('html')
  const frontendOrigin = typeof window !== 'undefined' ? window.location.origin : ''

  const snippets = buildSnippets(widgetId, API_BASE_URL, frontendOrigin)
  const active = snippets[platform]

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(active.code)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch {
      /* clipboard unavailable — the code block is still selectable/copyable by hand */
    }
  }

  // The embed page (app/(embed)/embed/[widgetId]/page.tsx) never calls the
  // API on its own -- it's a pure postMessage rendering surface, by design --
  // so it can't be opened standalone. This links to a dedicated preview page
  // that installs the widget the same way a real site would instead.
  const previewHref = `${frontendOrigin}/widget-preview/${widgetId}`

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {PLATFORMS.map(p => (
          <button
            key={p.key}
            type="button"
            onClick={() => { setPlatform(p.key); setCopied(false) }}
            className={`px-2.5 py-1 rounded-full text-[12px] border transition-colors ${
              platform === p.key
                ? 'border-violet-500 bg-violet-500/10 text-violet-700 dark:text-violet-300 font-medium'
                : 'border-[var(--border)] text-[var(--text-2)] hover:border-violet-300'
            }`}
          >
            {p.label}
          </button>
        ))}
      </div>
      <p className="text-[12px] text-[var(--text-3)]">
        {active.note} The widget only activates on origins you&apos;ve added to the allowed origins list —
        remember to add your production domain there.
      </p>
      <div className="relative">
        <pre className="rounded-[var(--radius-md)] bg-[var(--surface-2)] border border-[var(--border)] p-4 text-[12px] font-mono overflow-x-auto whitespace-pre max-h-[420px] overflow-y-auto">
          {active.code}
        </pre>
        <Button
          variant="outline"
          size="xs"
          className="absolute top-2 right-2"
          onClick={handleCopy}
        >
          {copied ? <Check className="w-3.5 h-3.5 mr-1.5" /> : <Copy className="w-3.5 h-3.5 mr-1.5" />}
          {copied ? 'Copied' : 'Copy'}
        </Button>
      </div>
      <a
        href={previewHref}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1.5 text-[12px] text-violet-600 dark:text-violet-400 hover:underline"
      >
        <ExternalLink className="w-3.5 h-3.5" />
        Test this widget in a new tab
      </a>
    </div>
  )
}
