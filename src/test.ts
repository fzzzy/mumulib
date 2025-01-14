


import { webkit, Page } from '@playwright/test';


async function testStateValues(page: Page) {
    console.log('Starting testStateValues...');

    console.log('Navigating to use_state example...');
    await page.goto('http://localhost:8000/examples/use_state/');
    
    console.log('Waiting for div selector...');
    await page.waitForSelector('div');
    
    console.log('Evaluating div contents...');
    const divContents = await page.$$eval('div', (divs: HTMLDivElement[]) => 
        divs.map(div => div.textContent)
    );
    console.log('Found div contents:', divContents);

    console.log('Starting state verification...');
    const expectedStates = [
        'Got state {"hello":"world"}',
        'Got state {"hello":"everybody"}',
        'Got state {"hello":"everybody"}'
    ];

    console.log('Checking each state value...');
    for (const [index, expected] of expectedStates.entries()) {
        console.log(`Checking div ${index}...`);
        if (divContents[index] !== expected) {
            console.error(`Verification failed for div ${index}`);
            throw new Error(`Div ${index} content doesn't match. Expected: ${expected}, Got: ${divContents[index]}`);
        }
    }
    console.log('All state values verified successfully');
}

async function testStateInputValues(page: Page) {
    console.log('Starting testStateInputValues...');
    console.log('Navigating to use_state_input example...');
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
        if (divContents[index] !== expected) {
            throw new Error(`State ${index} doesn't match. Expected: ${expected}, Got: ${divContents[index]}`);
        }
    }
    console.log('All input state values verified successfully');

}

async function testStateSelectTextarea(page: Page) {
    console.log('Starting testStateSelectTextarea...');
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
        if (divContents[index] !== expected) {
            throw new Error(`State ${index} doesn't match. Expected: ${expected}, Got: ${divContents[index]}`);
        }
    }
    console.log('All select/textarea state values verified successfully');
}


async function testStateSelected(page: Page) {
    console.log('Starting testStateSelected...');
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
        if (divContents[index] !== expected) {
            throw new Error(`State ${index} doesn't match. Expected: ${expected}, Got: ${divContents[index]}`);
        }
    }
    console.log('All selected state values verified successfully');
}

async function testStateUpdate(page: Page) {
    console.log('Starting testStateUpdate...');
    await page.goto('http://127.0.0.1:8000/examples/use_state_update/');
    
    await page.waitForSelector('input[name="this.number"]');
    
    // Wait for a few seconds to let the numbers increment
    await page.waitForTimeout(3000);
    
    const divContents: string[] = await page.$$eval(
        'div[class="output"]', (divs: HTMLDivElement[]) => 
        divs.map(div => div.textContent || '')
    );

    // Verify at least 5 outputs exist and they're incrementing
    if (divContents.length < 5) {
        throw new Error(`Expected at least 5 outputs, but got ${divContents.length}`);
    }

    for (let i = 1; i < divContents.length; i++) {
        const current = JSON.parse(divContents[i].replace('Got state ', ''));
        const previous = JSON.parse(divContents[i-1].replace('Got state ', ''));
        
        if (current.number !== previous.number + 1 && !(i === 1 && current.number === previous.number)) {
            throw new Error(`Numbers not incrementing correctly at index ${i}. Previous: ${previous.number}, Current: ${current.number}`);
        }
    }

    console.log('State update values verified successfully');
}


async function testStateSelectedUpdate(page: Page) {
    console.log('Starting testStateSelectedUpdate...');
    await page.goto('http://localhost:8000/examples/use_state_selected_update/');

    await page.waitForSelector('input[value="person1"]');
    await page.click('input[value="person1"]');
    
    await page.waitForTimeout(3000);
    
    const divContents: string[] = await page.$$eval('div[class="output"]', (divs: HTMLDivElement[]) => 
        divs.map(div => div.textContent || '')
    );

    if (divContents.length < 5) {
        throw new Error(`Expected at least 5 outputs, but got ${divContents.length}`);
    }

    for (let i = 2; i < divContents.length; i++) {
        const current = JSON.parse(divContents[i].replace('Got state ', ''));
        const previous = JSON.parse(divContents[i-1].replace('Got state ', ''));
        
        if (current.person1.number !== previous.person1.number + 1) {
            throw new Error(`Numbers not incrementing correctly at index ${i}. Previous: ${previous.person1.number}, Current: ${current.person1.number}`);
        }
    }

    console.log('State selected update values verified successfully');
}


async function testPatSlot(page: Page) {
    console.log('Starting testPatSlot...');
    await page.goto('http://localhost:8000/examples/use_patslot/');
    
    await page.waitForSelector('dl[data-pat="person"]');
    
    // Check first person
    const firstPerson = await page.$eval('dl[data-pat="person"]:first-child', el => ({
        name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
        age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
    }));

    if (firstPerson.name !== 'John Smith' || firstPerson.age !== '42') {
        throw new Error(`First person data mismatch. Got name: ${firstPerson.name}, age: ${firstPerson.age}`);
    }

    // Check second person
    const secondPerson = await page.$eval('dl[data-pat="person"]:nth-child(2)', el => ({
        name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
        age: el.querySelector('[data-slot="age"]')?.textContent?.trim(),
        style: el.getAttribute('style')
    }));

    if (secondPerson.name !== 'Jane Smith' || 
        secondPerson.age !== '12' || 
        !secondPerson.style?.includes('color: blue')) {
        throw new Error(`Second person data mismatch. Got name: ${secondPerson.name}, age: ${secondPerson.age}, style: ${secondPerson.style}`);
    }   
    console.log('Pattern slot content verified successfully');
}


async function testPatSlotFill(page: Page) {
    console.log('Starting testPatSlotFill...');
    await page.goto('http://localhost:8000/examples/use_patslot_fill/');
    
    await page.waitForSelector('dl[data-attr="style=color"]');
    
    const personData = await page.$eval('dl', el => ({
        style: el.getAttribute('style'),
        name: el.querySelector('[data-slot="name"]')?.textContent?.trim(),
        age: el.querySelector('[data-slot="age"]')?.textContent?.trim()
    }));

    if (personData.name !== 'Jane Smith' || 
        personData.age !== '12' || 
        !personData.style?.includes('color: blue')) {
        throw new Error(`Person data mismatch. Got name: ${personData.name}, age: ${personData.age}, style: ${personData.style}`);
    }

    await page.waitForTimeout(3000);

    const fillContent = await page.$eval('#fill-element [data-slot="fill_me"]', el => el.textContent?.trim());
    
    if (fillContent !== 'now been filled.') {
        throw new Error(`Fill content mismatch. Expected "now been filled." but got "${fillContent}"`);
    }

    console.log('Pattern slot fill content verified successfully');
}

async function testPatSlotTemplate(page: Page) {
    console.log('Starting testPatSlotTemplate...');
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
        if (personData[key] !== value) {
            throw new Error(`${key} mismatch. Expected "${value}" but got "${personData[key]}"`);
        }
    }

    console.log('Pattern slot template content verified successfully');
}


async function testPatSlotNested(page: Page) {
    console.log('Starting testPatSlotNested...');
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

    if (firstTown.name !== 'Los Angeles' || 
        firstTown.firstPerson.name !== 'Joe Smith' || 
        firstTown.firstPerson.age !== '67') {
        throw new Error(`First town data mismatch: ${JSON.stringify(firstTown)}`);
    }

    // Check footer
    const footer = await page.$eval('[data-slot="footer"]', el => el.textContent?.trim());
    if (footer !== 'This is the footer.') {
        throw new Error(`Footer mismatch. Expected "This is the footer." but got "${footer}"`);
    }

    console.log('Pattern slot nested content verified successfully');
}


async function testDialog(page: Page) {
    console.log('Starting testDialog...');
    await page.goto('http://localhost:8000/examples/use_dialog/');
    
    await page.waitForSelector('dialog[id="my_dialog"]');
    await page.fill('input[name="name"]', 'askdjhfajks');
    await page.fill('input[name="age"]', '123');
    await page.click('button');

    await page.waitForSelector('div[class="output"]');
    const output = await page.$eval('div[class="output"]', el => el.textContent);
    
    if (output !== 'my_method was called askdjhfajks 123') {
        throw new Error(`Dialog output mismatch. Expected "my_method was called askdjhfajks 123" but got "${output}"`);
    }

    console.log('Dialog test completed successfully');
}



async function openLocalhost() {
    console.log('Launching browser...');
    const browser = await webkit.launch({ headless: false });
    console.log('Creating new page...');
    const page = await browser.newPage();
    
    try {
        console.log('Navigating to localhost:8000...');
        await page.goto('http://localhost:8000');

        await testStateValues(page);
        await testStateInputValues(page);
        await testStateSelectTextarea(page);
        await testStateSelected(page);
        await testStateUpdate(page);
        await testStateSelectedUpdate(page);
        await testPatSlot(page);
        await testPatSlotFill(page);
        await testPatSlotTemplate(page);
        await testPatSlotNested(page);
        await testDialog(page);

        console.log('Waiting for 1 hour...');
        await page.waitForTimeout(60 * 60 * 1000);
    } catch (error) {
        console.error('Error:', error);
    } finally {
        console.log('Closing browser...');
        await browser.close();
    }
}


// Execute the function
openLocalhost();
process.stdin.resume();
console.log("Press Ctrl+C to exit.");
