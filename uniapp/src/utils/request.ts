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

function request<T>(
  url: string,
  method: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE' = 'GET',
  data?: object
): Promise<ApiResponse<T>> {
  const token = uni.getStorageSync('accessToken')
  let fullUrl = `${BASE_URL}${url}`

  // For GET/DELETE, append data as query string
  if ((method === 'GET' || method === 'DELETE') && data && Object.keys(data).length > 0) {
    const params = new URLSearchParams()
    for (const [key, value] of Object.entries(data)) {
      if (value !== undefined && value !== null) {
        params.append(key, String(value))
      }
    }
    fullUrl += (url.includes('?') ? '&' : '?') + params.toString()
  }

  console.log(`[request] ${method} ${fullUrl}`, { hasToken: !!token })
  return new Promise((resolve, reject) => {
    uni.request({
      url: fullUrl,
      method,
      data: (method === 'POST' || method === 'PUT' || method === 'PATCH') ? data : undefined,
      header: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      success: (res) => {
        console.log(`[request] ${method} ${fullUrl} -> ${res.statusCode}`, res.data)
        if (res.statusCode === 401) {
          uni.removeStorageSync('accessToken')
          uni.removeStorageSync('refreshToken')
          uni.removeStorageSync('tokenExpiry')
          uni.reLaunch({ url: '/pages/login/index' })
          return
        }
        resolve(res.data as ApiResponse<T>)
      },
      fail: (err) => {
        console.error(`[request FAIL] ${method} ${fullUrl}`, err)
        const error: RequestError = {
          errMsg: (err as any)?.errMsg || '网络请求失败',
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
