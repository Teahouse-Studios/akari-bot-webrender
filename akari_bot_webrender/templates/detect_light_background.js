function detect_light_background() {
  function parse(value) {
    const match = value && value.match(/rgba?\(([^)]+)\)/)
    if (!match) return null
    const [r, g, b, a = 1] = match[1].split(',').map((part) => parseFloat(part))
    return { r, g, b, a }
  }

  function isLight(el) {
    if (!el) return null
    const color = parse(getComputedStyle(el).backgroundColor)
    if (!color || color.a === 0) return null
    const luminance = (0.2126 * color.r + 0.7152 * color.g + 0.0722 * color.b) / 255
    return luminance > 0.5
  }

  const bodyVerdict = isLight(document.body)
  if (bodyVerdict !== null) return bodyVerdict

  const rootVerdict = isLight(document.documentElement)
  if (rootVerdict !== null) return rootVerdict

  // A fully transparent document is painted on the browser's white canvas.
  return true
}
