/**
 * KaTeX rendering utility.
 *
 * Loads KaTeX 0.16.9 dynamically from CDN and renders LaTeX formulas
 * embedded in text using $$...$$, $...$, \[...\] and \(...\) delimiters.
 *
 * 平台兼容：H5 + APP（WebView），统一使用 CDN 加载 KaTeX。
 * 若 CDN 加载失败，fallback 使用 simpleLatexRender 做基础渲染。
 */

let katexPromise: Promise<any> | null = null

function loadKatex(): Promise<any> {
  if (katexPromise) return katexPromise
  katexPromise = new Promise((resolve) => {
    const link = document.createElement('link')
    link.rel = 'stylesheet'
    link.href = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css'
    link.onload = () => {
      const script = document.createElement('script')
      script.src = 'https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js'
      script.onload = () => resolve((window as any).katex)
      script.onerror = () => resolve(null)  // JS 加载失败，返回 null
      document.head.appendChild(script)
    }
    link.onerror = () => resolve(null)  // CSS 加载失败，返回 null
    document.head.appendChild(link)
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
 * 简单 LaTeX 渲染（KaTeX 不可用时 fallback）。
 * 将常见 LaTeX 命令转为可读的 HTML 文本。
 */
function simpleLatexRender(text: string): string {
  let result = text
  // 块级公式 $$...$$ → 居中显示
  result = result.replace(/\$\$([\s\S]*?)\$\$/g, (_m, formula) => {
    return `<div style="text-align:center;margin:8px 0;font-style:italic">${simpleLatexRender(formula.trim())}</div>`
  })
  // 行内公式 $...$ → 斜体
  result = result.replace(/\$((?!\$).+?)\$/g, (_m, formula) => {
    return `<span style="font-style:italic">${simpleLatexRender(formula)}</span>`
  })
  // 分数 \frac{a}{b}
  result = result.replace(/\\(?:frac|dfrac)\{([^}]+)\}\{([^}]+)\}/g, '<sup>$1</sup>&frasl;<sub>$2</sub>')
  // 上标 x^2, x^{ab}
  result = result.replace(/\^\{([^}]+)\}/g, '<sup>$1</sup>')
  result = result.replace(/\^(\w)/g, '<sup>$1</sup>')
  // 下标 x_1, x_{ab}
  result = result.replace(/\_\{([^}]+)\}/g, '<sub>$1</sub>')
  result = result.replace(/\_(\w)/g, '<sub>$1</sub>')
  // 平方根 \sqrt{x}, \sqrt[n]{x}
  result = result.replace(/\\(?:sqrt)\[([^\]]+)\]\{([^}]+)\}/g, '√<sup>$1</sup>($2)')
  result = result.replace(/\\(?:sqrt)\{([^}]+)\}/g, '√($1)')
  // 常见数学符号映射
  const mathSymbols: Record<string, string> = {
    cdot: '·', times: '×', div: '÷', frac: '/',
    pm: '±', mp: '∓', ast: '∗', star: '⋆', circ: '∘', bullet: '•',
    cap: '∩', cup: '∪', mid: '|', parallel: '∥', setminus: '∖',
    subset: '⊂', supset: '⊃', subseteq: '⊆', supseteq: '⊇',
    in: '∈', notin: '∉', ni: '∋', emptyset: '∅', varnothing: '∅',
    le: '≤', leq: '≤', ge: '≥', geq: '≥', neq: '≠', ne: '≠',
    approx: '≈', equiv: '≡', sim: '∼', simeq: '≃', cong: '≅',
    propto: '∝', prop: '∝', infty: '∞', infinity: '∞',
    partial: '∂', nabla: '∇', exists: '∃', forall: '∀',
    neg: '¬', lnot: '¬', wedge: '∧', vee: '∨',
    to: '→', rightarrow: '→', Rightarrow: '⇒', leftarrow: '←', Leftarrow: '⇐',
    leftrightarrow: '↔', Leftrightarrow: '⇔', mapsto: '↦', longmapsto: '⟼',
    implies: '⇒', iff: '⇔', therefore: '∴', because: '∵',
    angle: '∠', perp: '⊥', triangle: '△', box: '□', diamond: '◇',
    oplus: '⊕', ominus: '⊖', otimes: '⊗', oslash: '⊘', odot: '⊙',
    dagger: '†', ddagger: '‡', aleph: 'ℵ', hbar: 'ℏ', ell: 'ℓ',
    Re: 'ℜ', Im: 'ℑ', prime: '′', surd: '√', top: '⊤', bot: '⊥',
    ldots: '…', cdots: '⋯', vdots: '⋮', ddots: '⋱',
    alpha: 'α', beta: 'β', gamma: 'γ', delta: 'δ', epsilon: 'ε',
    varepsilon: 'ε', zeta: 'ζ', eta: 'η', theta: 'θ', vartheta: 'ϑ',
    iota: 'ι', kappa: 'κ', lambda: 'λ', mu: 'μ', nu: 'ν', xi: 'ξ',
    omicron: 'ο', pi: 'π', varpi: 'ϖ', rho: 'ρ', sigma: 'σ',
    varsigma: 'ς', tau: 'τ', upsilon: 'υ', phi: 'φ', varphi: 'ϕ',
    chi: 'χ', psi: 'ψ', omega: 'ω',
    Alpha: 'Α', Beta: 'Β', Gamma: 'Γ', Delta: 'Δ', Epsilon: 'Ε',
    Zeta: 'Ζ', Eta: 'Η', Theta: 'Θ', Iota: 'Ι', Kappa: 'Κ',
    Lambda: 'Λ', Mu: 'Μ', Nu: 'Ν', Xi: 'Ξ', Omicron: 'Ο',
    Pi: 'Π', Rho: 'Ρ', Sigma: 'Σ', Tau: 'Τ', Upsilon: 'Υ',
    Phi: 'Φ', Chi: 'Χ', Psi: 'Ψ', Omega: 'Ω',
  }
  result = result.replace(/\\([a-zA-Z]+)/g, (m, name) => mathSymbols[name] || m)
  // 括号修饰符
  result = result.replace(/\\(?:left|right|big|bigg|bigl|bigr|biggl|biggr)\s*([\(\)\[\]\{\}])/g, '$1')
  // 大括号 \{ \}
  result = result.replace(/\\([{}])/g, '$1')
  // 移除剩余反斜杠（但保留未被替换的字母命令）
  result = result.replace(/\\(?!\s)/g, '')
  return result
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

  // 2. Protect LaTeX blocks from HTML escaping
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

  // Then: protect \[...\] (display mode)
  protected_text = protected_text.replace(/\\\[([\s\S]*?)\\\]/g, (_match, formula) => {
    const idx = mathBlocks.length
    mathBlocks.push({ formula, display: true })
    return `__MATH_BLOCK_${idx}__`
  })

  // Then: protect \(...\) (inline mode)
  protected_text = protected_text.replace(/\\\(([\s\S]*?)\\\)/g, (_match, formula) => {
    const idx = mathBlocks.length
    mathBlocks.push({ formula, display: false })
    return `__MATH_BLOCK_${idx}__`
  })

  // 3. Escape HTML for non-math content
  let result = escapeHtml(protected_text)

  // 4. Try to load KaTeX (CDN, 支持 H5 + APP WebView)
  let katex: any
  try {
    katex = await loadKatex()
  } catch {
    katex = null
  }

  // 5. KaTeX 不可用时，使用简单渲染 fallback
  if (!katex) {
    result = result.replace(/__MATH_BLOCK_(\d+)__/g, (_m, idx) => {
      const b = mathBlocks[parseInt(idx)]
      return simpleLatexRender(b.formula)
    })
    return result.replace(/\n/g, '<br/>')
  }

  // 6. Render protected math blocks with KaTeX
  result = result.replace(/__MATH_BLOCK_(\d+)__/g, (_m, idx) => {
    const block = mathBlocks[parseInt(idx)]
    try {
      return katex.renderToString(block.formula, { displayMode: block.display, throwOnError: false })
    } catch {
      return `<span style="color:#e74c3c">[公式渲染失败]</span>`
    }
  })

  // 7. Convert newlines to <br/>
  result = result.replace(/\n/g, '<br/>')

  return result
}
