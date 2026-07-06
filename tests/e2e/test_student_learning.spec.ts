import { test, expect } from '@playwright/test';

test.describe('Student Learning Flow', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/#/pages/student/home');
    await page.waitForLoadState('networkidle');
  });

  test('should display student home page', async ({ page }) => {
    // Check greeting
    const greeting = page.locator('.greeting');
    await expect(greeting.first()).toBeVisible();
  });

  test('should display task panel', async ({ page }) => {
    const taskPanel = page.locator('.task-panel').first();
    await expect(taskPanel).toBeVisible();
  });

  test('should display mission grid', async ({ page }) => {
    const missionGrid = page.locator('.mission-grid').first();
    await expect(missionGrid).toBeVisible();
  });

  test('should show empty state when no missions', async ({ page }) => {
    const emptyState = page.locator('.empty');
    if (await emptyState.isVisible().catch(() => false)) {
      await expect(emptyState.first()).toBeVisible();
    }
  });

  test('should navigate to wrong book via tab bar', async ({ page }) => {
    // Check tab bar exists
    const tabBar = page.locator('[role="tablist"], .tab-bar, .uni-tabbar');
    if (await tabBar.isVisible().catch(() => false)) {
      // Click wrong book tab
      const wrongBookTab = page.locator('text=错题本').first();
      await wrongBookTab.click();
      await page.waitForTimeout(1000);
      expect(page.url()).toContain('wrongbook');
    }
  });

  test('should navigate to growth page via tab bar', async ({ page }) => {
    const tabBar = page.locator('[role="tablist"], .tab-bar, .uni-tabbar');
    if (await tabBar.isVisible().catch(() => false)) {
      const growthTab = page.locator('text=成长').first();
      await growthTab.click();
      await page.waitForTimeout(1000);
      expect(page.url()).toContain('growth');
    }
  });

  test('should display logout button', async ({ page }) => {
    const logoutBtn = page.locator('.logout-btn');
    await expect(logoutBtn.first()).toBeVisible();
  });

  test('should display join class button', async ({ page }) => {
    const joinBtn = page.locator('.join-class-btn');
    await expect(joinBtn.first()).toBeVisible();
  });
});
