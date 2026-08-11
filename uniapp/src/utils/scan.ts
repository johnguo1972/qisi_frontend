export interface ScanResult { result: string; scanType: string }
export function scanCode(): Promise<ScanResult> {
  return new Promise((resolve, reject) => {
    // #ifdef MP-WEIXIN
    wx.scanCode({ onlyFromCamera: false, scanType: ['qrCode', 'barCode'], success: (res: any) => resolve({ result: res.result, scanType: res.scanType }), fail: reject })
    // #endif
    // #ifdef APP-PLUS
    uni.scanCode({ onlyFromCamera: false, success: (res: any) => resolve({ result: res.result, scanType: res.scanType }), fail: reject })
    // #endif
    // #ifdef H5
    reject(new Error('H5 不支持原生扫码，请输入作业码'))
    // #endif
  })
}
const CODE = 'ABCDEFGHJKMNPQRSTUVWXYZ23456789'
export function parseShortCode(value: string): string | null {
  const raw = String(value || '').trim().toUpperCase()
  const match = raw.match(new RegExp(`/HW/([${CODE}]{6})(?:[/?#]|$)`))
  if (match) return match[1]
  return new RegExp(`^[${CODE}]{6}$`).test(raw) ? raw : null
}
export function parsePaperCode(value: string) {
  const match = String(value || '').trim().toUpperCase().match(new RegExp(`/PAPER/([${CODE}]{8})/([${CODE}]{6})/P(\\d+)(?:[/?#]|$)`))
  return match ? { studentCode: match[1], missionCode: match[2], pageNo: Number(match[3]) } : null
}
