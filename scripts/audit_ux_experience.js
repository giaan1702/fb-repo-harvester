const path = require('path');
let playwright;
try {
  playwright = require('playwright');
} catch (e) {
  try {
    playwright = require('C:/Users/Administrator/AppData/Roaming/npm/node_modules/playwright');
  } catch (e2) {
    playwright = require('C:/Users/Administrator/AppData/Roaming/npm/node_modules/@playwright/mcp/node_modules/playwright');
  }
}

const { chromium } = playwright;

(async () => {
  const browser = await chromium.launch();
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 }
  });
  const page = await context.newPage();

  const auditLog = [];
  function log(category, title, status, observation) {
    auditLog.push({ category, title, status, observation });
    console.log(`[${status}] ${category.toUpperCase()} | ${title}: ${observation}`);
  }

  // 1. Initial Page Load & Visual Metrics
  const t0 = Date.now();
  await page.goto('http://127.0.0.1:7860', { waitUntil: 'networkidle' });
  const loadTime = Date.now() - t0;
  log('Performance', 'Initial Load Time', loadTime < 1000 ? 'GOOD' : 'WARNING', `${loadTime}ms`);

  // Count initial cards
  const initialCardsCount = await page.locator('.bento-card').count();
  log('UX', 'Initial Grid Count', initialCardsCount > 0 ? 'GOOD' : 'FAIL', `${initialCardsCount} items loaded`);

  // 2. Search Experience Test (Ctrl+K and Typo/Prefix)
  await page.keyboard.press('Control+KeyK');
  const isSearchFocused = await page.evaluate(() => document.activeElement.id === 'search-input');
  log('Usability', 'Keyboard Shortcut (Ctrl+K)', isSearchFocused ? 'GOOD' : 'FAIL', isSearchFocused ? 'Focuses input immediately' : 'Failed to focus');

  // Type search query
  await page.fill('#search-input', 'crawl4ai');
  await page.waitForTimeout(350); // wait debounce
  const filteredSearchCards = await page.locator('.bento-card').count();
  log('Search', 'FTS5 Filter Behavior', filteredSearchCards === 1 ? 'GOOD' : 'WARNING', `Expected 1 card for crawl4ai, got ${filteredSearchCards}`);
  await page.screenshot({ path: 'd:/PROJECT/REPOCraw/ui_inspections/ux_audit_search.png' });

  // Clear search
  await page.fill('#search-input', '');
  await page.waitForTimeout(350);

  // 3. Category Filter Experience
  const llmInfraPill = page.locator('.cat-pill[data-cat="LLM-Infra"]');
  await llmInfraPill.click();
  await page.waitForTimeout(300);
  const llmCardsCount = await page.locator('.bento-card').count();
  log('Filters', 'Category Pill Filter', llmCardsCount === 3 ? 'GOOD' : 'WARNING', `Found ${llmCardsCount} cards for LLM-Infra`);

  // Reset category
  await page.locator('.cat-pill[data-cat=""]').click();
  await page.waitForTimeout(300);

  // 4. Star Toggle on Card (Event Propagation & UI Feedback)
  const firstCardStarBtn = page.locator('.bento-card:first-child .star-btn');
  const wasStarredBefore = await firstCardStarBtn.evaluate(el => el.classList.contains('active'));
  await firstCardStarBtn.click();
  await page.waitForTimeout(400);
  const isStarredAfter = await firstCardStarBtn.evaluate(el => el.classList.contains('active'));
  log('UX Interaction', 'Card Star Toggle', wasStarredBefore !== isStarredAfter ? 'GOOD' : 'FAIL', `Toggle state from ${wasStarredBefore} to ${isStarredAfter}`);

  // Check if toast appeared
  const toastVisible = await page.locator('.toast.show').isVisible();
  log('Feedback', 'Toast Notification on Star', toastVisible ? 'GOOD' : 'WARNING', toastVisible ? 'Toast appeared cleanly' : 'No visible toast');
  await page.screenshot({ path: 'd:/PROJECT/REPOCraw/ui_inspections/ux_audit_toast.png' });

  // 5. Drawer Reading Experience & ScrollSpy
  await page.click('.bento-card:first-child');
  await page.waitForTimeout(500);

  const drawerVisible = await page.locator('#reader-drawer').isVisible();
  log('Drawer', 'Slide-over Drawer Open', drawerVisible ? 'GOOD' : 'FAIL', 'Drawer slide-in complete');

  // Test TOC item click navigation
  const firstTocLink = page.locator('.toc-link').first();
  const tocExists = await firstTocLink.count() > 0;
  if (tocExists) {
    const tocText = await firstTocLink.innerText();
    await firstTocLink.click();
    await page.waitForTimeout(300);
    log('Drawer', 'TOC Navigation', 'GOOD', `Clicked TOC item "${tocText.trim()}"`);
  } else {
    log('Drawer', 'TOC Navigation', 'WARNING', 'No TOC items found');
  }

  // Test Code Block Copy Experience
  const copyBtn = page.locator('.copy-code-btn').first();
  const copyBtnExists = await copyBtn.count() > 0;
  if (copyBtnExists) {
    await copyBtn.click();
    await page.waitForTimeout(200);
    const copyText = await copyBtn.innerText();
    log('Code Block', '1-Click Copy Button', copyText === 'COPIED!' ? 'GOOD' : 'WARNING', `Button text changed to "${copyText}"`);
  } else {
    log('Code Block', '1-Click Copy Button', 'INFO', 'No pre code blocks on this card to test copy');
  }

  // Test Tabs Switching
  await page.click('.drawer-tab[data-tab="reader"]');
  await page.waitForTimeout(400);
  const readerHasContent = await page.evaluate(() => {
    const el = document.getElementById('deep-research-content');
    return el && el.innerText.length > 200;
  });
  log('Smart Reader', 'Original Text Tab (Phần II)', readerHasContent ? 'GOOD' : 'FAIL', 'Original text with annotations loaded');

  // Test Close Drawer via Esc key
  await page.keyboard.press('Escape');
  await page.waitForTimeout(400);
  const drawerClosed = await page.evaluate(() => document.getElementById('reader-drawer').classList.contains('hidden'));
  log('Usability', 'Escape Key Closes Drawer', drawerClosed ? 'GOOD' : 'FAIL', drawerClosed ? 'Drawer hidden successfully' : 'Drawer still visible');

  // 6. Ingest Modal Flow & Error Handling
  await page.click('#btn-open-ingest');
  await page.waitForTimeout(300);
  const modalVisible = await page.locator('#ingest-modal').isVisible();
  log('Modal', 'Ingest Modal Open', modalVisible ? 'GOOD' : 'FAIL', 'Modal rendered with backdrop');

  // Submit with empty URL
  await page.click('#btn-submit-ingest');
  await page.waitForTimeout(300);
  const stillOpen = await page.locator('#ingest-modal').isVisible();
  log('Validation', 'Empty URL Submission', stillOpen ? 'GOOD' : 'WARNING', 'Modal stays open when empty');

  // Close modal via Esc
  await page.keyboard.press('Escape');
  await page.waitForTimeout(300);
  const modalClosed = await page.evaluate(() => document.getElementById('ingest-modal').classList.contains('hidden'));
  log('Usability', 'Escape Key Closes Modal', modalClosed ? 'GOOD' : 'FAIL', 'Modal dismissed via Esc');

  // 7. Visual Hierarchy & Polish Analysis
  const fontSizes = await page.evaluate(() => {
    const cardTitle = window.getComputedStyle(document.querySelector('.card-title'));
    const body = window.getComputedStyle(document.body);
    return { titleFont: cardTitle.fontFamily, bodyFont: body.fontFamily };
  });
  log('Typography', 'Font Family Hierarchy', 'GOOD', `Body: ${fontSizes.bodyFont.split(',')[0]} | Title: ${fontSizes.titleFont.split(',')[0]}`);

  // Write full evaluation JSON
  const fs = require('fs');
  fs.writeFileSync('d:/PROJECT/REPOCraw/ui_inspections/ux_experience_audit.json', JSON.stringify(auditLog, null, 2), 'utf-8');
  console.log('\nAudit complete. Log written to ui_inspections/ux_experience_audit.json');

  await browser.close();
})();
