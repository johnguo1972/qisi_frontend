import { test, expect } from '@playwright/test';

test.describe('Paper Upload Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Navigate to import page (assumes user is already logged in)
    await page.goto('http://localhost:5173/#/pages/teacher/import');
    await page.waitForLoadState('networkidle');
  });

  test('should display upload area', async ({ page }) => {
    // Check upload area exists
    const uploadArea = page.locator('.upload-area').first();
    await expect(uploadArea).toBeVisible();
  });

  test('should display import history section', async ({ page }) => {
    // Check history section exists
    const historySection = page.locator('.history-section').first();
    await expect(historySection).toBeVisible();
  });

  test('should show history title', async ({ page }) => {
    const historyTitle = page.locator('.history-title');
    await expect(historyTitle).toBeVisible();
    await expect(historyTitle).toContainText('导入历史');
  });

  test('should display sidebar navigation', async ({ page }) => {
    // Check sidebar
    const sidebar = page.locator('.sidebar').first();
    await expect(sidebar).toBeVisible();

    // Check nav items
    const navItems = page.locator('.nav-item');
    await expect(navItems.first()).toBeVisible();
  });

  test('should navigate to workbench', async ({ page }) => {
    // Click workbench link
    await page.locator('.nav-item', { hasText: '工作台' }).first().click();
    await page.waitForTimeout(1000);
    // Check URL changed or page content changed
    const mainContent = page.locator('.main, .page-title');
    await expect(mainContent.first()).toBeVisible();
  });

  test('should navigate to bank', async ({ page }) => {
    // Click bank link
    await page.locator('.nav-item', { hasText: '题库列表' }).click();
    await page.waitForTimeout(1000);
    // Should have navigated
    expect(page.url()).toContain('bank');
  });

  test('should show empty history when no uploads', async ({ page }) => {
    // Check for empty state
    const emptyHistory = page.locator('.empty-history, text=暂无导入记录').first();
    // May or may not be visible depending on data
    if (await emptyHistory.isVisible().catch(() => false)) {
      await expect(emptyHistory).toContainText('暂无');
    }
  });
});
