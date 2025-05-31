import { test, expect } from '@playwright/test';

test.describe('Mumulib State Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure we have a clean state before each test
    await page.goto('about:blank');
  });

  test('should handle basic state values', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_state/');
    await page.waitForSelector('div');
    
    const divContents = await page.$$eval('div', (divs: HTMLDivElement[]) => 
      divs.map(div => div.textContent)
    );

    const expectedStates = [
      'Got state {"hello":"world"}',
      'Got state {"hello":"everybody"}',
      'Got state {"hello":"everybody"}'
    ];

    for (const [index, expected] of expectedStates.entries()) {
      expect(divContents[index]).toBe(expected);
    }
  });

  test('should handle input state changes', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_state_input/');
    
    await page.waitForSelector('input[name="this.name"]');
    await page.fill('input[name="this.name"]', 'sdfgfggh');
    
    await page.waitForSelector('input[name="this.age"]');
    await page.fill('input[name="this.age"]', '21');
    
    await page.waitForSelector('input[name="this.color"]');
    await page.fill('input[name="this.color"]', '#a96800');
    await page.click('body');

    const divContents = await page.$$eval('div[class="output"]', (divs: HTMLDivElement[]) => 
      divs.map(div => div.textContent)
    );

    const expectedStates = [
      'Got state {}',
      'Got state {"name":"sdfgfggh"}',
      'Got state {"name":"sdfgfggh","age":"21"}',
      'Got state {"name":"sdfgfggh","age":"21","color":"#a96800"}'
    ];

    for (const [index, expected] of expectedStates.entries()) {
      expect(divContents[index]).toBe(expected);
    }
  });

  test('should handle select and textarea state changes', async ({ page }) => {
    await page.goto('http://127.0.0.1:8000/examples/use_state_select_textarea/');
    
    await page.waitForSelector('select[name="this.option"]');
    await page.selectOption('select[name="this.option"]', 'hello');
    
    await page.waitForSelector('textarea[name="this.comment"]');
    await page.fill('textarea[name="this.comment"]', 'ghjkghkjghjk');
    
    await page.waitForSelector('input[name="this.color"]');
    await page.fill('input[name="this.color"]', '#ffaa00');
    await page.click('body');

    const divContents = await page.$$eval('div[class="output"]', (divs: HTMLDivElement[]) => 
      divs.map(div => div.textContent)
    );

    const expectedStates = [
      'Got state {}',
      'Got state {"option":"hello"}',
      'Got state {"option":"hello","comment":"ghjkghkjghjk"}',
      'Got state {"option":"hello","comment":"ghjkghkjghjk","color":"#ffaa00"}'
    ];

    for (const [index, expected] of expectedStates.entries()) {
      expect(divContents[index]).toBe(expected);
    }
  });

  test('should handle selected state updates', async ({ page }) => {
    await page.goto('http://127.0.0.1:8000/examples/use_state_selected/');

    await page.waitForSelector('input[value="person1"]');
    await page.click('input[value="person1"]');
    await page.mouse.click(50, 50);
    await page.fill('input[name="selected.name"]', 'fgjfgfgjky');
    await page.fill('input[name="selected.age"]', '23');
    await page.mouse.click(50, 50);

    const divContents = await page.$$eval('div[class="output"]', (divs: HTMLDivElement[]) => 
      divs.map(div => div.textContent)
    );

    const expectedStates = [
      'Got state {"person1":{},"person2":{}}',
      'Got state {"person1":{},"person2":{}}',
      'Got state {"person1":{},"person2":{},"selected":"person1"}',
      'Got state {"person1":{"name":"fgjfgfgjky"},"person2":{},"selected":"person1"}',
      'Got state {"person1":{"name":"fgjfgfgjky","age":"23"},"person2":{},"selected":"person1"}'
    ];
    
    for (const [index, expected] of expectedStates.entries()) {
      expect(divContents[index]).toBe(expected);
    }
  });

  test('should handle automatic state updates', async ({ page }) => {
    await page.goto('http://127.0.0.1:8000/examples/use_state_update/');
    
    await page.waitForSelector('input[name="this.number"]');
    
    // Wait for a few seconds to let the numbers increment
    await page.waitForTimeout(3000);
    
    const divContents: string[] = await page.$$eval(
      'div[class="output"]', (divs: HTMLDivElement[]) => 
      divs.map(div => div.textContent || '')
    );

    // Verify at least 5 outputs exist and they're incrementing
    expect(divContents.length).toBeGreaterThanOrEqual(5);

    for (let i = 1; i < divContents.length; i++) {
      const current = JSON.parse(divContents[i].replace('Got state ', ''));
      const previous = JSON.parse(divContents[i-1].replace('Got state ', ''));
      
      if (current.number !== previous.number + 1 && !(i === 1 && current.number === previous.number)) {
        throw new Error(`Numbers not incrementing correctly at index ${i}. Previous: ${previous.number}, Current: ${current.number}`);
      }
    }
  });

  test('should handle selected state with automatic updates', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_state_selected_update/');

    await page.waitForSelector('input[value="person1"]');
    await page.click('input[value="person1"]');
    
    await page.waitForTimeout(3000);
    
    const divContents: string[] = await page.$$eval('div[class="output"]', (divs: HTMLDivElement[]) => 
      divs.map(div => div.textContent || '')
    );

    expect(divContents.length).toBeGreaterThanOrEqual(5);

    for (let i = 2; i < divContents.length; i++) {
      const current = JSON.parse(divContents[i].replace('Got state ', ''));
      const previous = JSON.parse(divContents[i-1].replace('Got state ', ''));
      
      expect(current.person1.number).toBe(previous.person1.number + 1);
    }
  });
});
