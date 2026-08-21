/** One API/media origin for H5, APP and WeChat builds. */
const buildEnv = (import.meta as any).env || {}
const configuredOrigin = String(buildEnv.VITE_API_TARGET || '').replace(/\/+$/, '')

let API_BASE_URL = `${configuredOrigin}/api/v1`
// #ifdef H5
API_BASE_URL = '/api/v1'
// #endif

export const apiBaseUrl = API_BASE_URL

export function getApiUrl(path: string): string {
  const normalized = `/${String(path || '').replace(/^\/+/, '')}`
  return `${apiBaseUrl}${normalized}`
}

export function getMediaBaseUrl(): string {
  // #ifdef H5
  return '/media'
  // #endif
  return `${configuredOrigin}/media`
}
