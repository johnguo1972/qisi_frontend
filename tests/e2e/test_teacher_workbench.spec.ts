import { test, expect } from '@playwright/test';

test.describe('Teacher Workbench', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('http://localhost:5173/#/pages/teacher/workbench');
    await page.waitForLoadState('networkidle');
  });

  test('should display workbench page', async ({ page }) => {
    // Check page title
    const title = page.locator('.page-title');
    await expect(title.first()).toBeVisible();
  });

  test('should display sidebar with logo', async ({ page }) => {
    const logo = page.locator('.sidebar-logo');
    await expect(logo.first()).toBeVisible();
    await expect(logo.first()).toContainText('A自习室');
  });

  test('should display teacher role', async ({ page }) => {
    const role = page.locator('.user-role');
    await expect(role.first()).toBeVisible();
    await expect(role.first()).toContainText('教师');
  });

  test('should have navigation items', async ({ page }) => {
    // Check all nav items are visible
    const navItems = page.locator('.nav-item');
    const count = await navItems.count();
    expect(count).toBeGreaterThan(0);
  });

  test('should navigate to import page', async ({ page }) => {
    await page.locator('.nav-item', { hasText: '上传试卷' }).click();
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('import');
  });

  test('should navigate to new question page', async ({ page }) => {
    await page.locator('.nav-item', { hasText: '新增试题' }).click();
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('new-question');
  });

  test('should navigate to mission create', async ({ page }) => {
    await page.locator('.nav-item', { hasText: '创建任务' }).click();
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('mission-create');
  });

  test('should navigate to class management', async ({ page }) => {
    await page.locator('.nav-item', { hasText: '班级管理' }).click();
    await page.waitForTimeout(1000);
    expect(page.url()).toContain('my-classes');
  });

  test('should display mission cards if missions exist', async ({ page }) => {
    const missionCards = page.locator('.mission-card');
    const count = await missionCards.count();
    if (count > 0) {
      // Check first card has content
      const firstCard = missionCards.first();
      await expect(firstCard).toBeVisible();
    }
  });
});
