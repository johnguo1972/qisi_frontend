import { getMediaBaseUrl } from './api-config'

/** Convert a server media path into a URL usable on H5, APP and MP. */
export function getMediaUrl(path?: string | null): string {
  if (!path) return ''
  const value = String(path).replace(/\\/g, '/')
  if (/^(https?:\/\/|data:|blob:)/i.test(value)) return value
  const relative = value.replace(/^\/+/, '').replace(/^media\//i, '')
  return `${getMediaBaseUrl()}/${relative}`
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
  return `${getMediaBaseUrl()}/${relative}`
}
