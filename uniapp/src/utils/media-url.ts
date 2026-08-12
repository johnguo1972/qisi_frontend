/** Convert a server media path into a URL usable on H5 and APP-PLUS. */
export function getMediaUrl(path?: string | null): string {
  if (!path) return ''
  const value = String(path).replace(/\\/g, '/')
  if (/^(https?:\/\/|data:|blob:)/i.test(value)) return value
  const relative = value.replace(/^\/+/, '').replace(/^media\//i, '')
  // #ifdef APP-PLUS
  return `https://qisi.chengxuelu.com/media/${relative}`
  // #endif
  // #ifdef MP-WEIXIN
  return `https://qisi.chengxuelu.com/media/${relative}`
  // #endif
  // #ifdef APP-PLUS
  return `https://qisi.chengxuelu.com/media/${relative}`
  // #endif
  // #ifdef H5
  return `/media/${relative}`
  // #endif
}

/**
 * Return an absolute public URL for files that must be opened outside the app,
 * such as exported PDFs copied to a browser or downloaded by Mini Program.
 */
export function getPublicMediaUrl(path?: string | null): string {
  if (!path) return ''
  const value = String(path).replace(/\\/g, '/')
  if (/^(https?:\/\/|data:|blob:)/i.test(value)) return value

  const relative = value.replace(/^\/+/, '').replace(/^media\//i, '')
  return `https://qisi.chengxuelu.com/media/${relative}`
}
