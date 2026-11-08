// Runs before CSS to prevent a light flash on dark-theme page navigation.
(() => {
  let preference;
  try { preference = localStorage.getItem('shag-theme'); } catch (_) { /* Storage may be blocked. */ }
  const theme = ['light', 'dark'].includes(preference)
    ? preference : (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.dataset.theme = theme;
  document.getElementById('theme-color')?.setAttribute('content', theme === 'dark' ? '#101613' : '#f5f7f2');
})();
