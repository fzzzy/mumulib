import { test, expect } from '@playwright/test';

test.describe('Mumulib Dialog Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure we have a clean state before each test
    await page.goto('about:blank');
  });

  test('should handle dialog interactions', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_dialog/');
    
    await page.waitForSelector('dialog[id="my_dialog"]');
    await page.fill('input[name="name"]', 'askdjhfajks');
    await page.fill('input[name="age"]', '123');
    await page.click('button');

    await page.waitForSelector('div[class="output"]');
    const output = await page.$eval('div[class="output"]', el => el.textContent);
    
    expect(output).toBe('my_method was called askdjhfajks 123');
  });
});
