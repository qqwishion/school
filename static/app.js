const toggle = document.querySelector('.mobile-filter');
toggle?.addEventListener('click', () => {
  const open = toggle.getAttribute('aria-expanded') !== 'true';
  toggle.setAttribute('aria-expanded', String(open));
  document.getElementById('filter-fields').classList.toggle('is-open', open);
});

const themeButton = document.querySelector('.theme-toggle');
const systemTheme = window.matchMedia('(prefers-color-scheme: dark)');
let themeTimer;
function syncThemeButton() {
  const dark = document.documentElement.dataset.theme === 'dark';
  themeButton?.setAttribute('aria-pressed', String(dark));
  themeButton?.setAttribute('aria-label', dark ? 'Включить светлую тему' : 'Включить тёмную тему');
  if (themeButton) themeButton.title = dark ? 'Светлая тема' : 'Тёмная тема';
  document.getElementById('theme-color')?.setAttribute('content', dark ? '#101613' : '#f5f7f2');
}
function setTheme(theme, animate = true) {
  if (animate) document.documentElement.classList.add('theme-changing');
  document.documentElement.dataset.theme = theme;
  syncThemeButton();
  clearTimeout(themeTimer);
  themeTimer = setTimeout(() => document.documentElement.classList.remove('theme-changing'), 300);
}
if (themeButton) {
  themeButton.hidden = false;
  syncThemeButton();
  themeButton.addEventListener('click', () => {
    const theme = document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark';
    setTheme(theme);
    try { localStorage.setItem('shag-theme', theme); } catch (_) { /* Current-page toggle still works. */ }
  });
}
systemTheme.addEventListener('change', event => {
  let preference;
  try { preference = localStorage.getItem('shag-theme'); } catch (_) {}
  if (!['light', 'dark'].includes(preference)) setTheme(event.matches ? 'dark' : 'light');
});
window.addEventListener('storage', event => {
  if (event.key === 'shag-theme') setTheme(['light', 'dark'].includes(event.newValue)
    ? event.newValue : (systemTheme.matches ? 'dark' : 'light'));
});

document.querySelector('#id_sort')?.addEventListener('change', (event) => event.target.form.requestSubmit());
document.querySelectorAll('.print-button').forEach(button => button.addEventListener('click', () => window.print()));
document.querySelectorAll('form').forEach(form => form.addEventListener('submit', () => {
  form.setAttribute('aria-busy', 'true');
  const button = form.querySelector('button[type="submit"]');
  if (button) {
    button.dataset.label = button.textContent;
    button.textContent = 'Подождите…';
    button.disabled = true;
  }
}));
window.addEventListener('pageshow', () => document.querySelectorAll('form[aria-busy]').forEach(form => {
  form.removeAttribute('aria-busy');
  form.querySelectorAll('button[data-label]').forEach(button => { button.disabled = false; button.textContent = button.dataset.label; });
}));
