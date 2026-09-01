import { describe, expect, it } from 'vitest'
import { normalizeAnswerVisibility } from './answer-visibility'

describe('normalizeAnswerVisibility', () => {
  it('converts an uninitialized answer visibility entry to false', () => {
    expect(normalizeAnswerVisibility(undefined)).toBe(false)
  })

  it('keeps explicit boolean visibility values', () => {
    expect(normalizeAnswerVisibility(true)).toBe(true)
    expect(normalizeAnswerVisibility(false)).toBe(false)
  })
})
