const BASE_URL = '/api/v1'

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
      method: method as any,
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
