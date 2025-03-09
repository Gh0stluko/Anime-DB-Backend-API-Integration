document.addEventListener('DOMContentLoaded', function() {
    // Додаємо кнопку перемикання теми в хедер
    const header = document.querySelector('#header');
    
    if (header) {
        const userTools = header.querySelector('#user-tools');
        
        // Створюємо кнопку
        const themeToggle = document.createElement('span');
        themeToggle.id = 'theme-toggle';
        themeToggle.style.marginLeft = '15px';
        themeToggle.style.cursor = 'pointer';
        themeToggle.innerHTML = '<span id="theme-icon">☀️</span>';
        themeToggle.title = 'Перемкнути тему';
        
        // Додаємо кнопку в хедер
        if (userTools) {
            userTools.appendChild(themeToggle);
        } else {
            header.appendChild(themeToggle);
        }
        
        // Визначаємо поточну тему
        const darkThemeCss = document.querySelector('link[href*="dark_theme.css"]');
        const isDarkMode = !!darkThemeCss && darkThemeCss.disabled !== true;
        
        // Оновлюємо іконку відповідно до поточної теми
        updateIcon(isDarkMode);
        
        // Додаємо обробник подій
        themeToggle.addEventListener('click', function() {
            if (darkThemeCss) {
                darkThemeCss.disabled = !darkThemeCss.disabled;
                updateIcon(!darkThemeCss.disabled);
                
                // Зберігаємо вибір в localStorage
                localStorage.setItem('darkThemeEnabled', !darkThemeCss.disabled);
            }
        });
        
        // Функція для оновлення іконки
        function updateIcon(isDark) {
            const icon = document.getElementById('theme-icon');
            if (icon) {
                icon.textContent = isDark ? '☀️' : '🌙';
            }
        }
    }
    
    // Перевіряємо localStorage при завантаженні
    function checkPreferredTheme() {
        const darkThemeCss = document.querySelector('link[href*="dark_theme.css"]');
        if (darkThemeCss) {
            const prefersDark = localStorage.getItem('darkThemeEnabled') === 'true';
            darkThemeCss.disabled = !prefersDark;
            const icon = document.getElementById('theme-icon');
            if (icon) {
                icon.textContent = prefersDark ? '☀️' : '🌙';
            }
        }
    }
    
    // Викликаємо перевірку при завантаженні
    checkPreferredTheme();
});
