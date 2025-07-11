import { test, expect } from '@playwright/test';

test.describe('Mumulib PatSlot Tests', () => {
  test.beforeEach(async ({ page }) => {
    // Ensure we have a clean state before each test
    await page.goto('about:blank');
  });

  test('should handle basic pattern slots', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_patslot/');
    
    await page.waitForSelector('dl[data-pat="person"]');
    
    // Check first person
    const firstPerson = await page.$eval('dl[data-pat="person"]:first-child', el => ({
      name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
      age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
    }));

    expect(firstPerson.name).toBe('John Smith');
    expect(firstPerson.age).toBe('42');

    // Check second person
    const secondPerson = await page.$eval('dl[data-pat="person"]:nth-child(2)', el => ({
      name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
      age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
      style: el.getAttribute('style')
    }));

    expect(secondPerson.name).toBe('Jane Smith');
    expect(secondPerson.age).toBe('12');
    expect(secondPerson.style).toContain('color: blue');
  });

  test('should handle pattern slot filling', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_patslot_fill/');
    
    await page.waitForSelector('dl[data-attr="style=color"]');
    
    const personData = await page.$eval('dl', el => ({
      style: el.getAttribute('style'),
      name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
      age: el.querySelector('[data-slot="age"]')?.textContent?.trim()
    }));

    expect(personData.name).toBe('Jane Smith');
    expect(personData.age).toBe('12');
    expect(personData.style).toContain('color: blue');

    await page.waitForTimeout(3000);

    const fillContent = await page.$eval('#fill-element [data-slot="fill_me"]', el => el.textContent?.trim());
    
    expect(fillContent).toBe('now been filled.');
  });

  test('should handle pattern slot templates', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_patslot_template/');
    
    await page.waitForSelector('dl[data-pat="person"]');
    
    const personData: {[key: string]: string} = await page.$eval('dl[data-pat="person"]', el => ({
      style: el.getAttribute('style')?.toString() || '',
      name: el.querySelector('[data-slot="name"]')?.textContent?.trim() || '',
      age: el.querySelector('[data-slot="age"]')?.textContent?.trim() || '',
      pattern: el.getAttribute('data-pat') || '',
      attrs: el.getAttribute('data-attr') || ''
    }));

    const expected = {
      style: 'color: blue',
      name: 'Jane Smith',
      age: '12',
      pattern: 'person',
      attrs: 'style=color'
    };

    for (const [key, value] of Object.entries(expected)) {
      expect(personData[key]).toBe(value);
    }
  });

  test('should handle nested pattern slots', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_patslot_nested/');
    
    await page.waitForSelector('ol[data-slot="towns"]');
    
    // Check first town
    const firstTown = await page.$eval('li[data-pat="town"]:first-child', el => ({
      name: el.querySelector('[data-slot="town_name"]')?.textContent?.trim(),
      firstPerson: {
        name: el.querySelector('dl[data-pat="person"]:first-child [data-slot="name"]')?.textContent?.trim(),
        age: el.querySelector('dl[data-pat="person"]:first-child [data-slot="age"]')?.textContent?.trim()
      }
    }));

    expect(firstTown.name).toBe('Los Angeles');
    expect(firstTown.firstPerson.name).toBe('Joe Smith');
    expect(firstTown.firstPerson.age).toBe('67');

    // Check footer
    const footer = await page.$eval('[data-slot="footer"]', el => el.textContent?.trim());
    expect(footer).toBe('This is the footer.');
  });

  test('should handle nodes that are both patterns and slots', async ({ page }) => {
    await page.goto('http://localhost:8000/examples/use_patslot_pattern_and_slot_node/');

    await page.waitForTimeout(1000);

    // Check that we have two span elements with the expected text
    const spans = await page.$$eval('span[data-slot="hello"]', elements => 
      elements.map(el => el.textContent?.trim())
    );

    expect(spans).toHaveLength(2);
    expect(spans[0]).toBe('Hello World');
    expect(spans[1]).toBe('Bonjour Monde');

  });
});
