import { apiBaseUrl as BASE_URL } from './api-config'

interface ApiResponse<T = any> {
  code: number
  message: string
  data: T
  trace_id: string
}

interface RequestError {
  errMsg: string
  statusCode?: number
  data?: any
}

export interface RequestOptions {
  silentError?: boolean
}

// 保存最近的请求日志到全局数组，方便调试时查看
const requestLogs: Array<{ url: string; method: string; status: string; detail: string }> = []
;(globalThis as any).__requestLogs = requestLogs

function responseErrorMessage(data, statusCode) {
  if (data && typeof data === 'object') {
    const detail = data.detail || data.message || data.error
    if (typeof detail === 'string' && detail.trim()) return detail.trim()
  }
  return `请求失败（${statusCode}）`
}

function request<T>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'GET',
  data?: object,
  options: RequestOptions = {}
): Promise<ApiResponse<T>> {
  const token = uni.getStorageSync('accessToken')
  let fullUrl = `${BASE_URL}${url}`

  // For GET/DELETE, append data as query string
  if ((method === 'GET' || method === 'DELETE') && data && Object.keys(data).length > 0) {
    const qs: string[] = []
    for (const [key, value] of Object.entries(data)) {
      if (value !== undefined && value !== null) {
        qs.push(encodeURIComponent(key) + '=' + encodeURIComponent(String(value)))
      }
    }
    if (qs.length > 0) {
      fullUrl += (url.includes('?') ? '&' : '?') + qs.join('&')
    }
  }

  console.log(`[request] ${method} ${fullUrl}`, { hasToken: !!token })

  return new Promise((resolve, reject) => {
    uni.request({
      url: fullUrl,
      method: method as any,
      data: (method === 'POST' || method === 'PUT' || method === 'PATCH') ? data : undefined,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (res) => {
        console.log(`[request] ${method} ${fullUrl} -> ${res.statusCode}`, res.data)
        try {
          requestLogs.push({ url: fullUrl, method, status: `${res.statusCode}`, detail: JSON.stringify(res.data).slice(0, 200) })
        } catch { /* ignore log errors */ }
        if (res.statusCode === 401) {
          uni.removeStorageSync('accessToken')
          uni.removeStorageSync('refreshToken')
          uni.removeStorageSync('tokenExpiry')
          uni.reLaunch({ url: '/pages/login/index' })
          return
        }
        // 手动解析 JSON（兼容 APP 平台）
        let parsed = res.data
        if (typeof parsed === 'string') {
          try { parsed = JSON.parse(parsed) } catch { /* 已经是字符串，保持原样 */ }
        }
        // 非 2xx 状态码仍保持原有 resolve 行为，避免改变已有业务调用链，
        // 但优先展示后端返回的真实错误信息（如 DRF 的 detail）。
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const msg = responseErrorMessage(parsed, res.statusCode)
          console.error(`[request] ${method} ${fullUrl} -> ${res.statusCode}: ${msg}`)
          if (!options.silentError) uni.showToast({ title: msg.slice(0, 80), icon: 'none', duration: 3000 })
        }
        resolve(parsed as ApiResponse<T>)
      },
      fail: (err) => {
        console.error(`[request FAIL] ${method} ${fullUrl}`, err)
        const nativeErr = (err as any)?.errMsg || '未知错误'
        const msg = `接口失败: ${method} ${fullUrl}\n错误: ${nativeErr}`
        requestLogs.push({ url: fullUrl, method, status: 'FAIL', detail: nativeErr })
        // 使用更长的提示方式显示完整信息
        if (!options.silentError) uni.showModal({
          title: '网络请求失败',
          content: msg.slice(0, 300),
          showCancel: false,
        })
        const error: RequestError = {
          errMsg: nativeErr,
        }
        reject(error)
      },
    })
  })
}

export const get = <T>(url: string, data?: object, options?: RequestOptions) => request<T>(url, 'GET', data, options)
export const post = <T>(url: string, data?: object, options?: RequestOptions) => request<T>(url, 'POST', data, options)
export const put = <T>(url: string, data?: object, options?: RequestOptions) => request<T>(url, 'PUT', data, options)
export const patch = <T>(url: string, data?: object, options?: RequestOptions) => request<T>(url, 'PATCH', data, options)
export const del = <T>(url: string, data?: object, options?: RequestOptions) => request<T>(url, 'DELETE', data, options)
