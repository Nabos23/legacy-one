/**
 * @one-ai/widget — typed loader for the One-AI embeddable chatbot widget.
 *
 * This package deliberately contains NO widget logic. It injects the hosted
 * `widget.js` from your One-AI deployment (so every embed stays on the latest
 * loader automatically) and wraps `window.OneAIWidget` in a typed, promise-
 * based API that plays well with SPA lifecycles:
 *
 *   import { initWidget } from '@one-ai/widget'
 *
 *   const widget = await initWidget({
 *     widgetId: 'YOUR_WIDGET_ID',
 *     apiUrl: 'https://api.your-one-ai.com',
 *     chatUrl: 'https://app.your-one-ai.com',
 *   })
 *   widget.open()
 *   // on unmount:
 *   widget.destroy()
 */
export interface OneAIWidgetOptions {
    /** The widget's id from the One-AI dashboard (Embed Code tab). */
    widgetId: string;
    /** Base URL of the One-AI backend API, e.g. https://api.your-one-ai.com */
    apiUrl: string;
    /** Base URL of the One-AI app that hosts widget.js and the chat iframe. */
    chatUrl: string;
    /** Short-lived draft-preview token (dashboard use; omit in production). */
    previewToken?: string;
}
export interface OneAIWidgetInstance {
    open(): void;
    close(): void;
    toggle(): void;
    /** Full teardown: removes the launcher/iframe and every listener. */
    destroy(): void;
}
interface OneAIWidgetGlobal {
    init(opts: OneAIWidgetOptions): OneAIWidgetInstance;
    destroy(): void;
}
declare global {
    interface Window {
        OneAIWidget?: OneAIWidgetGlobal;
    }
}
/**
 * Load widget.js (once) and initialize the widget. Re-initializing replaces
 * any existing instance rather than stacking launchers, so calling this from
 * a remounting component is safe.
 */
export declare function initWidget(options: OneAIWidgetOptions): Promise<OneAIWidgetInstance>;
/** Tear down the active widget instance, if any. Safe to call repeatedly. */
export declare function destroyWidget(): void;
export {};
