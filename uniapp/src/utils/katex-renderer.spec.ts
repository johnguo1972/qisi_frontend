import { afterEach, describe, expect, it, vi } from 'vitest'
import { renderWithKatex } from './katex-renderer'

describe('renderWithKatex CDN fallback', () => {
  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders roman option labels and underline blanks without exposing LaTeX commands', async () => {
    vi.spyOn(document.head, 'appendChild').mockImplementation((node: Node) => {
      const element = node as HTMLElement
      element.onerror?.(new Event('error'))
      return node
    })

    const html = await renderWithKatex(
      '选项 $\\mathrm{A}$. $100$ 张；填空 $\\underline{\\hspace{2cm}}$。',
    )

    expect(html).toContain('A')
    expect(html).toContain('100')
    expect(html).toContain('border-bottom')
    expect(html).not.toContain('mathrm{')
    expect(html).not.toContain('underline{')
    expect(html).not.toContain('hspace{')
  })
})
