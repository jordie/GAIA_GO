/**
 * Architect Browser Agent - Content Script
 * DOM interaction and Comet AI sidebar monitoring
 */

console.log('[Architect Content] Loaded on:', window.location.href);

// === Command Handler ===
chrome.runtime.onMessage.addListener((cmd, sender, sendResponse) => {
  console.log('[Architect Content] Received command:', cmd.action);

  handleCommand(cmd)
    .then(result => {
      console.log('[Architect Content] Command result:', result);
      sendResponse(result);
    })
    .catch(err => {
      console.error('[Architect Content] Command failed:', err);
      sendResponse({ success: false, error: err.message });
    });

  return true; // Keep channel open for async response
});

async function handleCommand(cmd) {
  const { action, params = {} } = cmd;

  switch (action) {
    // DOM reading
    case 'READ_DOM':
      return readDOM(params);

    case 'GET_PAGE_TEXT':
      return { text: document.body.innerText };

    case 'GET_PAGE_HTML':
      return { html: document.documentElement.outerHTML };

    case 'EXTRACT_ELEMENTS':
      return extractActionableElements();

    case 'EXTRACT_TABLE':
      return extractTable(params.selector);

    // DOM writing
    case 'WRITE_DOM':
      return writeDOM(params);

    case 'CLICK':
      return clickElement(params.selector);

    case 'TYPE_TEXT':
      return typeText(params);

    case 'SUBMIT_FORM':
      return submitForm(params.selector);

    case 'SELECT_OPTION':
      return selectOption(params);

    // Waiting
    case 'WAIT_ELEMENT':
      return waitForElement(params.selector, params.timeout);

    case 'WAIT_TEXT':
      return waitForText(params.text, params.timeout);

    // Scrolling
    case 'SCROLL':
      return scrollPage(params);

    case 'SCROLL_TO_ELEMENT':
      return scrollToElement(params.selector);

    // Comet AI integration
    case 'READ_COMET':
      return readCometState();

    case 'WRITE_COMET':
      return writeCometInput(params.text);

    case 'SUBMIT_COMET':
      return submitComet();

    case 'SUBSCRIBE_COMET':
      startCometObserver();
      return { subscribed: true };

    // Sidebar query - write and submit to Comet
    case 'SIDEBAR_QUERY': {
      const query = cmd.query || '';
      if (!query) {
        return { success: false, error: 'Query required' };
      }

      // Write to input
      const writeResult = writeCometInput(query);
      if (!writeResult.success) {
        return writeResult;
      }

      // Brief delay for input to register
      await new Promise(r => setTimeout(r, 100));

      // Submit
      const submitResult = submitComet();
      if (!submitResult.success) {
        return submitResult;
      }

      // Return successful submission
      return {
        success: true,
        query: query,
        submitted: true,
        timestamp: Date.now()
      };
    }

    // Utility
    case 'GET_FORMS':
      return getForms();

    case 'GET_LINKS':
      return getLinks();

    case 'GET_BUTTONS':
      return getButtons();

    case 'TAKE_SCREENSHOT':
      return { message: 'Use background SCREENSHOT command instead' };

    default:
      throw new Error(`Unknown action: ${action}`);
  }
}

// === DOM Reading ===
function readDOM({ selector, attr, multiple = false }) {
  const elements = multiple
    ? Array.from(document.querySelectorAll(selector))
    : [document.querySelector(selector)].filter(Boolean);

  return {
    success: elements.length > 0,
    count: elements.length,
    elements: elements.map(el => ({
      text: el.innerText,
      html: el.outerHTML.substring(0, 500),
      tag: el.tagName,
      ...(attr && { [attr]: el.getAttribute(attr) })
    }))
  };
}

function extractActionableElements() {
  const result = {
    pageTitle: document.title,
    url: window.location.href,
    links: [],
    buttons: [],
    forms: [],
    dropdowns: [],
    tables: [],
    headings: [],
    alerts: []
  };

  // Extract links (visible only)
  const links = Array.from(document.querySelectorAll('a[href]'));
  result.links = links
    .filter(el => isVisible(el))
    .slice(0, 50) // Limit to 50
    .map((el, idx) => ({
      index: idx + 1,
      text: el.innerText.trim().substring(0, 100),
      href: el.href,
      selector: getSelector(el)
    }))
    .filter(l => l.text); // Only links with text

  // Extract buttons
  const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'));
  result.buttons = buttons
    .filter(el => isVisible(el))
    .slice(0, 30)
    .map((el, idx) => ({
      index: idx + 1,
      text: el.innerText || el.value || el.getAttribute('aria-label') || '',
      type: el.type,
      id: el.id,
      selector: getSelector(el)
    }))
    .filter(b => b.text);

  // Extract form fields
  const forms = Array.from(document.querySelectorAll('form'));
  result.forms = forms.slice(0, 5).map(form => ({
    id: form.id,
    action: form.action,
    method: form.method,
    fields: Array.from(form.querySelectorAll('input, textarea, select'))
      .filter(el => isVisible(el))
      .map(el => ({
        label: getLabel(el),
        name: el.name,
        type: el.type,
        required: el.required,
        placeholder: el.placeholder,
        value: el.type !== 'password' ? el.value : '[password]',
        selector: getSelector(el)
      }))
  }));

  // Extract dropdowns
  const selects = Array.from(document.querySelectorAll('select'));
  result.dropdowns = selects
    .filter(el => isVisible(el))
    .slice(0, 20)
    .map(el => ({
      label: getLabel(el),
      name: el.name,
      options: Array.from(el.options).map(opt => opt.text),
      selected: el.selectedIndex >= 0 ? el.options[el.selectedIndex].text : null,
      selector: getSelector(el)
    }));

  // Extract tables (summary only)
  const tables = Array.from(document.querySelectorAll('table'));
  result.tables = tables
    .filter(el => isVisible(el))
    .slice(0, 5)
    .map(table => {
      const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
      const rowCount = table.querySelectorAll('tr').length - (headers.length > 0 ? 1 : 0);
      return { headers, rowCount, selector: getSelector(table) };
    });

  // Extract headings
  const headings = Array.from(document.querySelectorAll('h1, h2, h3'));
  result.headings = headings
    .filter(el => isVisible(el))
    .slice(0, 20)
    .map(el => el.innerText.trim())
    .filter(Boolean);

  // Extract alerts/notices
  const alerts = Array.from(document.querySelectorAll('[role="alert"], .alert, .notice, .error, .warning'));
  result.alerts = alerts
    .filter(el => isVisible(el))
    .map(el => el.innerText.trim())
    .filter(Boolean);

  return result;
}

function extractTable(selector) {
  const table = selector ? document.querySelector(selector) : document.querySelector('table');

  if (!table) {
    return { success: false, error: 'Table not found' };
  }

  const headers = Array.from(table.querySelectorAll('th')).map(th => th.innerText.trim());
  const rows = Array.from(table.querySelectorAll('tr')).slice(headers.length > 0 ? 1 : 0);

  return {
    success: true,
    headers,
    rows: rows.map(row => {
      const cells = Array.from(row.querySelectorAll('td, th'));
      return cells.map(cell => cell.innerText.trim());
    })
  };
}

function getForms() {
  const forms = Array.from(document.querySelectorAll('form'));
  return forms.map(form => ({
    id: form.id,
    action: form.action,
    method: form.method,
    fieldCount: form.querySelectorAll('input, textarea, select').length
  }));
}

function getLinks() {
  const links = Array.from(document.querySelectorAll('a[href]'));
  return links
    .filter(isVisible)
    .map(el => ({
      text: el.innerText.trim(),
      href: el.href,
      selector: getSelector(el)
    }))
    .filter(l => l.text);
}

function getButtons() {
  const buttons = Array.from(document.querySelectorAll('button, input[type="button"], input[type="submit"]'));
  return buttons
    .filter(isVisible)
    .map(el => ({
      text: el.innerText || el.value,
      type: el.type,
      selector: getSelector(el)
    }))
    .filter(b => b.text);
}

// === DOM Writing ===
function writeDOM({ selector, content, method = 'replace' }) {
  const el = document.querySelector(selector);
  if (!el) {
    return { success: false, error: 'Element not found' };
  }

  switch (method) {
    case 'append':
      el.innerHTML += content;
      break;
    case 'prepend':
      el.innerHTML = content + el.innerHTML;
      break;
    case 'before':
      el.insertAdjacentHTML('beforebegin', content);
      break;
    case 'after':
      el.insertAdjacentHTML('afterend', content);
      break;
    default:
      el.innerHTML = content;
  }

  return { success: true };
}

function clickElement(selector) {
  const el = document.querySelector(selector);
  if (!el) {
    return { success: false, error: 'Element not found' };
  }

  el.scrollIntoView({ behavior: 'smooth', block: 'center' });
  setTimeout(() => el.click(), 100);

  return { success: true, clicked: selector };
}

function typeText({ selector, text, clear = false }) {
  const el = selector ? document.querySelector(selector) : document.activeElement;

  if (!el) {
    return { success: false, error: 'Element not found' };
  }

  el.focus();

  if (clear) {
    el.value = '';
  }

  // For input/textarea elements
  if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
    el.value = clear ? text : el.value + text;
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
  } else {
    // For contenteditable elements
    if (clear) {
      document.execCommand('selectAll', false, null);
    }
    document.execCommand('insertText', false, text);
  }

  return { success: true, typed: text.substring(0, 50) };
}

function submitForm(selector) {
  const form = selector ? document.querySelector(selector) : document.querySelector('form');

  if (!form) {
    return { success: false, error: 'Form not found' };
  }

  form.submit();
  return { success: true };
}

function selectOption({ selector, value, text, index }) {
  const select = document.querySelector(selector);

  if (!select || select.tagName !== 'SELECT') {
    return { success: false, error: 'Select element not found' };
  }

  if (value) {
    select.value = value;
  } else if (text) {
    const option = Array.from(select.options).find(opt => opt.text === text);
    if (option) {
      select.value = option.value;
    } else {
      return { success: false, error: 'Option not found' };
    }
  } else if (typeof index === 'number') {
    if (index >= 0 && index < select.options.length) {
      select.selectedIndex = index;
    } else {
      return { success: false, error: 'Invalid index' };
    }
  }

  select.dispatchEvent(new Event('change', { bubbles: true }));
  return { success: true, selected: select.options[select.selectedIndex].text };
}

// === Waiting ===
function waitForElement(selector, timeout = 10000) {
  return new Promise((resolve) => {
    if (document.querySelector(selector)) {
      return resolve({ found: true, waited: 0 });
    }

    const startTime = Date.now();
    const observer = new MutationObserver(() => {
      if (document.querySelector(selector)) {
        observer.disconnect();
        resolve({ found: true, waited: Date.now() - startTime });
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true
    });

    setTimeout(() => {
      observer.disconnect();
      resolve({ found: false, waited: timeout });
    }, timeout);
  });
}

function waitForText(text, timeout = 10000) {
  return new Promise((resolve) => {
    if (document.body.innerText.includes(text)) {
      return resolve({ found: true, waited: 0 });
    }

    const startTime = Date.now();
    const observer = new MutationObserver(() => {
      if (document.body.innerText.includes(text)) {
        observer.disconnect();
        resolve({ found: true, waited: Date.now() - startTime });
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
      characterData: true
    });

    setTimeout(() => {
      observer.disconnect();
      resolve({ found: false, waited: timeout });
    }, timeout);
  });
}

// === Scrolling ===
function scrollPage({ direction = 'down', amount = 500 }) {
  const scrollAmount = direction === 'up' ? -amount : amount;
  window.scrollBy({ top: scrollAmount, behavior: 'smooth' });

  return {
    success: true,
    scrollY: window.scrollY,
    maxScroll: document.documentElement.scrollHeight - window.innerHeight
  };
}

function scrollToElement(selector) {
  const el = document.querySelector(selector);

  if (!el) {
    return { success: false, error: 'Element not found' };
  }

  el.scrollIntoView({ behavior: 'smooth', block: 'center' });

  return { success: true, scrolledTo: selector };
}

// === Comet AI Integration ===
let cometObserver = null;
let lastResponseCount = 0;

function readCometState() {
  // Detect if Comet sidebar is present
  const sidebar = document.querySelector('[data-erpsidecar]') || document.getElementById('ask-input');

  if (!sidebar) {
    return { hasComet: false };
  }

  // Read query history
  const queries = Array.from(document.querySelectorAll('.groupquery'))
    .map(q => q.innerText.trim());

  // Read responses
  const responses = Array.from(document.querySelectorAll('[id^="markdown-content-"]'))
    .map(r => ({
      id: r.id,
      text: r.innerText,
      html: r.innerHTML.substring(0, 1000)
    }));

  // Read input field
  const input = document.getElementById('ask-input');
  const inputValue = input ? (input.innerText || input.value || '') : '';

  // Read submit button state
  const submitBtn = document.querySelector('button[aria-label="Submit"]');
  const canSubmit = submitBtn && !submitBtn.disabled;

  return {
    hasComet: true,
    queries,
    responses,
    inputValue,
    canSubmit,
    responseCount: responses.length
  };
}

function writeCometInput(text) {
  const input = document.getElementById('ask-input');

  if (!input) {
    return { success: false, error: 'Comet input not found' };
  }

  input.focus();

  // Clear existing content
  document.execCommand('selectAll', false, null);

  // Insert text
  document.execCommand('insertText', false, text);

  return { success: true, wrote: text.substring(0, 50) };
}

function submitComet() {
  const btn = document.querySelector('button[aria-label="Submit"]');

  if (!btn) {
    return { success: false, error: 'Submit button not found' };
  }

  if (btn.disabled) {
    return { success: false, error: 'Submit button disabled' };
  }

  btn.click();
  return { success: true };
}

function startCometObserver() {
  if (cometObserver) {
    console.log('[Architect Content] Comet observer already running');
    return;
  }

  const target = document.querySelector('.scrollable-container') || document.body;

  cometObserver = new MutationObserver(() => {
    const responses = document.querySelectorAll('[id^="markdown-content-"]');

    if (responses.length > lastResponseCount) {
      lastResponseCount = responses.length;
      const latest = responses[responses.length - 1];

      // Push new response event to background
      chrome.runtime.sendMessage({
        event: 'COMET_RESPONSE',
        data: {
          responseId: latest.id,
          text: latest.innerText,
          html: latest.innerHTML.substring(0, 1000),
          totalResponses: responses.length
        }
      });
    }
  });

  cometObserver.observe(target, {
    childList: true,
    subtree: true,
    characterData: true
  });

  console.log('[Architect Content] Comet observer started');
}

// Auto-start Comet monitoring if sidebar detected
if (document.querySelector('[data-erpsidecar]') || document.getElementById('ask-input')) {
  console.log('[Architect Content] Comet sidebar detected, starting observer');
  setTimeout(startCometObserver, 1000); // Wait for page to fully load
}

// === Helper Functions ===
function isVisible(el) {
  if (!el || !el.offsetParent) return false;

  const style = window.getComputedStyle(el);
  return style.display !== 'none' &&
         style.visibility !== 'hidden' &&
         style.opacity !== '0';
}

function getLabel(el) {
  // Try to find associated label
  if (el.id) {
    const label = document.querySelector(`label[for="${el.id}"]`);
    if (label) return label.innerText.trim();
  }

  // Try parent label
  const parentLabel = el.closest('label');
  if (parentLabel) return parentLabel.innerText.trim();

  // Try aria-label
  if (el.getAttribute('aria-label')) {
    return el.getAttribute('aria-label');
  }

  // Try placeholder
  if (el.placeholder) {
    return el.placeholder;
  }

  return el.name || '';
}

function getSelector(el) {
  // Prefer ID
  if (el.id) {
    return `#${el.id}`;
  }

  // Try name
  if (el.name) {
    return `${el.tagName.toLowerCase()}[name="${el.name}"]`;
  }

  // Generate CSS selector
  const path = [];
  while (el.parentElement) {
    let selector = el.tagName.toLowerCase();
    if (el.className) {
      selector += '.' + el.className.trim().split(/\s+/).join('.');
    }
    path.unshift(selector);
    el = el.parentElement;
    if (path.length > 4) break; // Limit depth
  }

  return path.join(' > ');
}

console.log('[Architect Content] Ready');
