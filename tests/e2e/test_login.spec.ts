import { test, expect } from '@playwright/test';

test.describe('Login Flow', () => {
  test('should display login page', async ({ page }) => {
    await page.goto('http://localhost:5173');
    // Wait for page to load
    await page.waitForLoadState('networkidle');
    // Check login page elements exist
    const pageTitle = await page.title();
    expect(pageTitle).toContain('登录');
  });

  test('should show phone number input', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    // Check for phone number input field
    const phoneInput = page.locator('input[placeholder*="手机号"], input[type="tel"], input').first();
    await expect(phoneInput).toBeVisible();
  });

  test('should show verify code input', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    // Check for verify code input
    const codeInput = page.locator('input[placeholder*="验证码"], input[placeholder*="code"]').first();
    await expect(codeInput).toBeVisible();
  });

  test('should show login button', async ({ page }) => {
    await page.goto('http://localhost:5173');
    await page.waitForLoadState('networkidle');
    // Check for login button
    const loginButton = page.locator('button:has-text("登录"), button:has-text("登 录"), button[type="submit"]').first();
    await expect(loginButton).toBeVisible();
  });
});
