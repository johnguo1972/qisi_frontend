/**
 * KaTeX rendering utility.
 *
 * Loads KaTeX 0.16.9 dynamically from CDN and renders LaTeX formulas
 * embedded in text using \[...\] (display) and \(...\) (inline) delimiters.
 */

let katexPromise: Promise<any> | null = null

function loadKatex(): Promise<any> {
  if (katexPromise) return katexPromise
  katexPromise = new Promise((resolve, reject) => {
    // #ifdef H5
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css'
    link.onload = () => {
      const script = document.createElement('script')
      script.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js'
      script.onload = () => resolve((window as any).katex)
      script.onerror = reject
      document.head.appendChild(script)
    }
    link.onerror = reject
    document.head.appendChild(link)
    // #endif
    // #ifndef H5
    reject(new Error('KaTeX is only supported in H5 environment'))
    // #endif
  })
  return katexPromise
}

/**
 * Escape plain-text characters for safe HTML embedding.
 */
function escapeHtml(text: string): string {
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
}

/**
 * Render a text string that may contain LaTeX formulas.
 *
 * - $$ ... $$ → display-mode math
 * - $ ... $ → inline-mode math
 * - \[ ... \] → display-mode math
 * - \( ... \) → inline-mode math
 * - \n → <br/>
 */
export async function renderWithKatex(text: string): Promise<string> {
  // 1. Empty check
  if (!text || text.trim() === '') {
    return '<span style="color:#999">(无内容)</span>'
  }

  // 2. Protect LaTeX blocks ($$...$$ and $...$) from HTML escaping
  //    Replace them with placeholders, then escape the rest
  const mathBlocks: { formula: string; display: boolean }[] = []
  let protected_text = text

  // First: protect $$...$$ (display mode)
  protected_text = protected_text.replace(/\$\$([\s\S]*?)\$\$/g, (_match, formula) => {
    const idx = mathBlocks.length
    mathBlocks.push({ formula, display: true })
    return `__MATH_BLOCK_${idx}__`
  })

  // Then: protect $...$ (inline mode)
  protected_text = protected_text.replace(/\$((?!\$).+?)\$/g, (_match, formula) => {
    const idx = mathBlocks.length
    mathBlocks.push({ formula, display: false })
    return `__MATH_BLOCK_${idx}__`
  })

  // 3. Escape HTML for non-math content
  let result = escapeHtml(protected_text)

  // 4. Try to load KaTeX (H5 only)
  let katex: any
  try {
    katex = await loadKatex()
  } catch {
    // Fallback: restore placeholders and convert newlines
    result = result.replace(/__MATH_BLOCK_(\d+)__/g, (_m, idx) => {
      const b = mathBlocks[parseInt(idx)]
      return '$' + (b.display ? '$' : '') + b.formula + (b.display ? '$' : '')
    })
    return result.replace(/\n/g, '<br/>')
  }

  // 5. Render protected math blocks
  result = result.replace(/__MATH_BLOCK_(\d+)__/g, (_m, idx) => {
    const block = mathBlocks[parseInt(idx)]
    try {
      return katex.renderToString(block.formula, { displayMode: block.display, throwOnError: false })
    } catch {
      return `<span style="color:#e74c3c">[公式渲染失败]</span>`
    }
  })

  // 6. Render display math: \[ ... \]
  result = result.replace(/\\\[([\s\S]*?)\\\]/g, (_match, formula) => {
    try {
      return katex.renderToString(formula, { displayMode: true, throwOnError: false })
    } catch {
      return `<span style="color:#e74c3c">[公式渲染失败]</span>`
    }
  })

  // 7. Render inline math: \( ... \)
  result = result.replace(/\\\(([\s\S]*?)\\\)/g, (_match, formula) => {
    try {
      return katex.renderToString(formula, { displayMode: false, throwOnError: false })
    } catch {
      return `<span style="color:#e74c3c">[公式渲染失败]</span>`
    }
  })

  // 8. Convert newlines to <br/>
  result = result.replace(/\n/g, '<br/>')

  return result
}
