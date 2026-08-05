/** Convert a server media path into a URL usable on H5 and APP-PLUS. */
export function getMediaUrl(path?: string | null): string {
  if (!path) return ''
  const value = String(path).replace(/\\/g, '/')
  if (/^(https?:\/\/|data:|blob:)/i.test(value)) return value
  const relative = value.replace(/^\/+/, '').replace(/^media\//i, '')
  // #ifdef APP-PLUS
  return `https://qisi.chengxuelu.com/media/${relative}`
  // #endif
  // #ifndef APP-PLUS
  return `/media/${relative}`
  // #endif
}
