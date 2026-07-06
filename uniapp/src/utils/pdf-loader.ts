/**
 * PDF.js dynamic loader.
 *
 * Loads PDF.js 3.11.174 from CDN at runtime (H5 only).
 * Returns `true` if successfully loaded, `false` otherwise.
 */

let pdfJsPromise: Promise<boolean> | null = null

export function loadPdfJs(): Promise<boolean> {
  if (pdfJsPromise) return pdfJsPromise
  pdfJsPromise = new Promise((resolve) => {
    // #ifdef H5
    const script = document.createElement('script')
    script.src = 'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.min.js'
    script.onload = () => {
      const pdfjsLib = (window as any).pdfjsLib
      if (pdfjsLib) {
        // Set worker source to CDN
        pdfjsLib.GlobalWorkerOptions.workerSrc =
          'https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js'
        resolve(true)
      } else {
        resolve(false)
      }
    }
    script.onerror = () => resolve(false)
    document.head.appendChild(script)
    // #endif
    // #ifndef H5
    resolve(false)
    // #endif
  })
  return pdfJsPromise
}
