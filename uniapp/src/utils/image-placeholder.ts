/**
 * Image placeholder utilities for question-edit page.
 *
 * Placeholder format: {{image_N}} where N is the illustration image ID.
 */

/** Minimal image shape used by placeholder rendering. */
export interface PlaceholderImage {
  id: number
  file_path: string
  description?: string
}

/**
 * Insert `{{image_N}}` at the cursor position of a textarea,
 * then move the cursor to after the inserted placeholder.
 *
 * Returns the updated text value (the caller should assign it back to the model).
 */
export function insertImagePlaceholder(
  textarea: HTMLTextAreaElement,
  imageId: number,
): string {
  const placeholder = `{{image_${imageId}}}`
  const start = textarea.selectionStart ?? textarea.value.length
  const end = textarea.selectionEnd ?? textarea.value.length
  const before = textarea.value.substring(0, start)
  const after = textarea.value.substring(end)

  const newValue = before + placeholder + after
  const cursorPos = start + placeholder.length

  // Set value and restore cursor position
  textarea.value = newValue
  textarea.setSelectionRange(cursorPos, cursorPos)
  textarea.focus()

  // Dispatch input event so v-model stays in sync
  textarea.dispatchEvent(new Event('input', { bubbles: true }))

  return newValue
}

/**
 * Replace all `{{image_N}}` placeholders in text with `<img>` HTML tags.
 *
 * Unknown placeholders (image ID not found in `images`) are kept as-is.
 * Should be called after KaTeX rendering in the preview pipeline.
 */
export function renderImagePlaceholders(
  text: string,
  images: PlaceholderImage[],
): string {
  if (!text) return text

  const imageMap = new Map<number, PlaceholderImage>()
  for (const img of images) {
    imageMap.set(img.id, img)
  }

  return text.replace(/\{\{image_(\d+)\}\}/g, (match, idStr: string) => {
    const id = Number(idStr)
    const img = imageMap.get(id)
    if (!img) return match // keep unknown placeholder as-is

    const src = img.file_path.startsWith('http')
      ? img.file_path
      : `/media/${img.file_path}`
    const desc = img.description || `插图 ${id}`

    // Escape for safe HTML embedding (prevent XSS)
    const safeSrc = src.replace(/"/g, '&quot;').replace(/</g, '&lt;')
    const safeDesc = desc.replace(/"/g, '&quot;').replace(/</g, '&lt;')

    return `<img src="${safeSrc}" alt="${safeDesc}" style="max-width:100%;border-radius:4px;margin:4px 0;" />`
  })
}
