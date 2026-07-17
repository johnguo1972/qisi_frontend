// #ifdef APP-PLUS
// App 环境（APK）：使用完整域名
const BASE_URL = 'https://qisi.chengxuelu.com/study/api/v1'
// #endif
// #ifndef APP-PLUS
// H5 环境：根据当前路径自动判断是否在 /study/ 子路径下
const isStudyPath = typeof window !== 'undefined' && window.location.pathname.startsWith('/study/')
const BASE_URL = isStudyPath ? '/study/api/v1' : '/api/v1'
// #endif

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

// 保存最近的请求日志到全局数组，方便调试时查看
const requestLogs: Array<{ url: string; method: string; status: string; detail: string }> = []
;(globalThis as any).__requestLogs = requestLogs

function request<T>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'GET',
  data?: object
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
        // 非 2xx 状态码也算失败，但能拿到响应
        if (res.statusCode < 200 || res.statusCode >= 300) {
          const msg = `接口 ${method} ${fullUrl} 返回异常状态码 ${res.statusCode}`
          console.error(msg, res.data)
          uni.showToast({ title: `请求异常(${res.statusCode})`, icon: 'none', duration: 3000 })
        }
        // 手动解析 JSON（兼容 APP 平台）
        let parsed = res.data
        if (typeof parsed === 'string') {
          try { parsed = JSON.parse(parsed) } catch { /* 已经是字符串，保持原样 */ }
        }
        resolve(parsed as ApiResponse<T>)
      },
      fail: (err) => {
        console.error(`[request FAIL] ${method} ${fullUrl}`, err)
        const nativeErr = (err as any)?.errMsg || '未知错误'
        const msg = `接口失败: ${method} ${fullUrl}\n错误: ${nativeErr}`
        requestLogs.push({ url: fullUrl, method, status: 'FAIL', detail: nativeErr })
        // 使用更长的提示方式显示完整信息
        uni.showModal({
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

export const get = <T>(url: string, data?: object) => request<T>(url, 'GET', data)
export const post = <T>(url: string, data?: object) => request<T>(url, 'POST', data)
export const put = <T>(url: string, data?: object) => request<T>(url, 'PUT', data)
export const patch = <T>(url: string, data?: object) => request<T>(url, 'PATCH', data)
export const del = <T>(url: string, data?: object) => request<T>(url, 'DELETE', data)
