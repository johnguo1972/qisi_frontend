/**
 * Image upload utility functions
 *
 * Reusable wrappers around the photo-upload.vue patterns:
 * - chooseImage: pick or capture, returns local path (+ File on H5)
 * - uploadImage: uni.uploadFile with Authorization header
 * - checkCameraSupport: H5 desktop detection
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ChooseImageResult {
  /** Local file path or blob URL */
  path: string
  /** File object (H5 only; undefined on non-H5 platforms) */
  file?: File
}

export interface UploadImageOptions {
  /** Local path returned by chooseImage */
  filePath: string
  /** Full upload URL (absolute or relative) */
  uploadUrl: string
  /** Form field name for the file (default: "image") */
  fieldName?: string
  /** Override the access token (defaults to uni.getStorageSync('accessToken')) */
  token?: string
}

export interface UploadImageResult {
  /** HTTP status code */
  statusCode: number
  /** Parsed JSON data from the response body */
  data: any
}

// ---------------------------------------------------------------------------
// chooseImage
// ---------------------------------------------------------------------------

/**
 * Pick one image from album or camera.
 *
 * H5: creates a dynamic <input type="file" accept="image/*">.
 *     If `camera` is true, adds capture="environment" to prefer the rear camera.
 * Non-H5: delegates to uni.chooseImage.
 *
 * @param options.count  max number of images (default 1)
 * @param options.sourceType  'camera' | 'album' | ['camera','album'] (default ['camera','album'])
 * @returns Promise<ChooseImageResult[]>
 */
export function chooseImage(options?: {
  count?: number
  sourceType?: 'camera' | 'album' | Array<'camera' | 'album'>
}): Promise<ChooseImageResult[]> {
  const count = options?.count ?? 1
  const sourceType = options?.sourceType ?? ['camera', 'album']

  // ---------- H5 ----------
  // #ifdef H5
  return new Promise((resolve, reject) => {
    const input = document.createElement('input')
    input.type = 'file'
    input.accept = 'image/*'
    input.multiple = count > 1

    // Prefer rear camera when camera is the sole source
    if (
      sourceType === 'camera' ||
      (Array.isArray(sourceType) && sourceType.length === 1 && sourceType[0] === 'camera')
    ) {
      input.capture = 'environment'
    }

    input.onchange = (e: Event) => {
      const files = (e.target as HTMLInputElement).files
      if (!files || files.length === 0) {
        resolve([])
        return
      }
      const results: ChooseImageResult[] = []
      for (const f of Array.from(files)) {
        results.push({ path: URL.createObjectURL(f), file: f as File })
      }
      resolve(results)
    }
    input.click()
  })
  // #endif

  // ---------- Non-H5 ----------
  // #ifndef H5
  return new Promise((resolve, reject) => {
    const normalizedSourceType: Array<'camera' | 'album'> =
      typeof sourceType === 'string' ? [sourceType] : sourceType

    uni.chooseImage({
      count,
      sizeType: ['compressed'],
      sourceType: normalizedSourceType,
      success: (res) => {
        const results: ChooseImageResult[] = res.tempFilePaths.map((p) => ({ path: p }))
        resolve(results)
      },
      fail: (err) => reject(err),
    })
  })
  // #endif
}

/** Convenience: open rear camera directly */
export function capturePhoto(options?: { count?: number }): Promise<ChooseImageResult[]> {
  return chooseImage({ count: options?.count ?? 1, sourceType: 'camera' })
}

/** Convenience: pick from album */
export function pickFromAlbum(options?: { count?: number }): Promise<ChooseImageResult[]> {
  return chooseImage({ count: options?.count ?? 1, sourceType: 'album' })
}

// ---------------------------------------------------------------------------
// uploadImage
// ---------------------------------------------------------------------------

/**
 * Upload a single local image to a server endpoint.
 *
 * H5: wraps the File into FormData and uses fetch().
 * Non-H5: uses uni.uploadFile().
 *
 * Both paths automatically attach an Authorization: Bearer <token> header.
 *
 * @returns Promise<UploadImageResult>
 */
export async function uploadImage(opts: UploadImageOptions): Promise<UploadImageResult> {
  const { filePath, uploadUrl, fieldName = 'image' } = opts
  const token = opts.token ?? (uni.getStorageSync('accessToken') as string) ?? ''

  // ---------- H5 ----------
  // #ifdef H5
  const formData = new FormData()
  // On H5, filePath from chooseImage is a blob URL; the actual File is in opts.result.file
  // Callers should pass the File object; we try to resolve it from a hidden map if needed.
  // For maximum compatibility with the chooseImage result, callers pass the File directly:
  // If filePath is a blob URL and no file is provided, attempt to fetch it back.
  const file = (opts as any).file as File | undefined
  if (file) {
    formData.append(fieldName, file)
  } else {
    // Fallback: try to reconstruct from blob URL (may fail if URL was revoked)
    try {
      const resp = await fetch(filePath)
      const blob = await resp.blob()
      formData.append(fieldName, blob, 'image.jpg')
    } catch {
      throw new Error('H5 upload requires a File object; blob URL could not be fetched')
    }
  }

  const httpResp = await fetch(uploadUrl, {
    method: 'POST',
    headers: { Authorization: 'Bearer ' + token },
    body: formData,
  })

  const data = await httpResp.json()
  return { statusCode: httpResp.status, data }
  // #endif

  // ---------- Non-H5 ----------
  // #ifndef H5
  return new Promise((resolve, reject) => {
    uni.uploadFile({
      url: uploadUrl,
      filePath,
      name: fieldName,
      header: { Authorization: 'Bearer ' + token },
      success: (res) => {
        let parsed: any
        try {
          parsed = JSON.parse(res.data)
        } catch {
          reject(new Error('Upload response is not valid JSON'))
          return
        }
        resolve({ statusCode: res.statusCode, data: parsed })
      },
      fail: (err) => reject(err),
    })
  })
  // #endif
}

// ---------------------------------------------------------------------------
// checkCameraSupport
// ---------------------------------------------------------------------------

/**
 * Check whether the current environment supports camera capture.
 *
 * On H5 running on a desktop browser, the `capture` attribute on <input>
 * is ignored; the user would need a phone. This function returns `{ supported: false }`
 * with a hint message in that case.
 *
 * @returns { supported: true } | { supported: false, hint: string }
 */
export function checkCameraSupport(): { supported: boolean; hint?: string } {
  // #ifdef H5
  const ua = navigator.userAgent.toLowerCase()
  const isMobile = /mobile|android|iphone|ipad|ipod|phone/i.test(ua)
  if (!isMobile) {
    return {
      supported: false,
      hint: '桌面浏览器不支持拍照，请使用手机访问或使用相册上传图片。',
    }
  }
  // Check MediaDevices API
  if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    return { supported: true }
  }
  return {
    supported: false,
    hint: '当前浏览器不支持相机访问。',
  }
  // #endif

  // #ifndef H5
  // On mini-program / app platforms, camera is always available
  // (permission is requested at runtime by uni.chooseImage / uni.chooseMedia)
  return { supported: true }
  // #endif
}
