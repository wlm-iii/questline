/**
 * Copy text to the clipboard. `navigator.clipboard` only exists on HTTPS and localhost, so phones
 * opening the dev server by LAN IP fall back to a hidden textarea and `execCommand('copy')`.
 * Resolves false when neither works, so callers can show the text instead.
 */
export async function copyText(text: string): Promise<boolean> {
  if (navigator.clipboard) {
    try {
      await navigator.clipboard.writeText(text)
      return true
    } catch {
      // Permission denied or not focused: try the fallback.
    }
  }
  const area = document.createElement('textarea')
  area.value = text
  area.setAttribute('readonly', '')
  area.style.position = 'fixed'
  area.style.opacity = '0'
  document.body.appendChild(area)
  area.select()
  area.setSelectionRange(0, text.length)
  try {
    return document.execCommand('copy')
  } catch {
    return false
  } finally {
    area.remove()
  }
}
