/** Client-side dominant-color extraction for "use my logo's colors" in the
 * widget builder. Canvas-samples the image, ignores background-ish pixels
 * (transparent / near-white / near-black / washed-out grays), clusters the
 * rest into coarse RGB buckets, and returns the two most distinct dominant
 * colors. No dependencies; ~1ms for a 64x64 sample. */

interface ExtractedBrandColors {
  primary: string
  secondary: string
}

function toHex(r: number, g: number, b: number): string {
  return '#' + [r, g, b].map(v => Math.round(v).toString(16).padStart(2, '0')).join('')
}

function hueOf(r: number, g: number, b: number): number {
  const max = Math.max(r, g, b) / 255
  const min = Math.min(r, g, b) / 255
  if (max === min) return 0
  const d = max - min
  const rn = r / 255, gn = g / 255, bn = b / 255
  let h: number
  if (max === rn) h = ((gn - bn) / d + (gn < bn ? 6 : 0)) / 6
  else if (max === gn) h = ((bn - rn) / d + 2) / 6
  else h = ((rn - gn) / d + 4) / 6
  return h * 360
}

function saturationOf(r: number, g: number, b: number): number {
  const max = Math.max(r, g, b) / 255
  const min = Math.min(r, g, b) / 255
  const l = (max + min) / 2
  if (max === min) return 0
  const d = max - min
  return l > 0.5 ? d / (2 - max - min) : d / (max + min)
}

export function extractBrandColors(imageUrl: string): Promise<ExtractedBrandColors | null> {
  return new Promise(resolve => {
    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.onload = () => {
      try {
        const SIZE = 64
        const canvas = document.createElement('canvas')
        canvas.width = SIZE
        canvas.height = SIZE
        const ctx = canvas.getContext('2d')
        if (!ctx) return resolve(null)
        ctx.drawImage(img, 0, 0, SIZE, SIZE)
        const { data } = ctx.getImageData(0, 0, SIZE, SIZE)

        // Coarse 3-bit-per-channel buckets: key -> {count, rSum, gSum, bSum}
        const buckets = new Map<number, { count: number; r: number; g: number; b: number }>()
        for (let i = 0; i < data.length; i += 4) {
          const r = data[i], g = data[i + 1], b = data[i + 2], a = data[i + 3]
          if (a < 128) continue
          const lum = (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255
          if (lum > 0.92 || lum < 0.08) continue
          if (saturationOf(r, g, b) < 0.15) continue
          const key = ((r >> 5) << 6) | ((g >> 5) << 3) | (b >> 5)
          const bucket = buckets.get(key) ?? { count: 0, r: 0, g: 0, b: 0 }
          bucket.count++; bucket.r += r; bucket.g += g; bucket.b += b
          buckets.set(key, bucket)
        }
        if (buckets.size === 0) return resolve(null)

        const ranked = [...buckets.values()]
          .sort((x, y) => y.count - x.count)
          .map(bkt => ({ r: bkt.r / bkt.count, g: bkt.g / bkt.count, b: bkt.b / bkt.count, count: bkt.count }))

        const primary = ranked[0]
        const primaryHue = hueOf(primary.r, primary.g, primary.b)
        // Secondary: the most common color whose hue is meaningfully different;
        // fall back to a lightened primary when the logo is monochrome.
        const distinct = ranked.find(c => {
          const dh = Math.abs(hueOf(c.r, c.g, c.b) - primaryHue)
          return Math.min(dh, 360 - dh) > 40
        })
        const secondary = distinct ?? {
          r: primary.r + (255 - primary.r) * 0.45,
          g: primary.g + (255 - primary.g) * 0.45,
          b: primary.b + (255 - primary.b) * 0.45,
        }
        resolve({
          primary: toHex(primary.r, primary.g, primary.b),
          secondary: toHex(secondary.r, secondary.g, secondary.b),
        })
      } catch {
        // Canvas tainted (no CORS on the image host) or decode failure.
        resolve(null)
      }
    }
    img.onerror = () => resolve(null)
    img.src = imageUrl
  })
}
