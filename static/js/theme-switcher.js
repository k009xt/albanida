document.addEventListener('DOMContentLoaded', function () {
    const savedTheme = localStorage.getItem('theme') || 'light';

    // Применяем сохраненную тему на всех страницах
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        document.body.classList.remove('light-mode');
        document.getElementById('themeToggleSwitch').checked = true; // Включаем переключатель
    } else {
        document.body.classList.add('light-mode');
        document.body.classList.remove('dark-mode');
        document.getElementById('themeToggleSwitch').checked = false; // Выключаем переключатель
    }

    // Работа с переключателем
    const themeToggleSwitch = document.getElementById('themeToggleSwitch');
    if (themeToggleSwitch) {
        themeToggleSwitch.addEventListener('change', function () {
            const isDarkMode = themeToggleSwitch.checked;
            document.body.classList.toggle('dark-mode', isDarkMode);
            document.body.classList.toggle('light-mode', !isDarkMode);

            // Сохраняем выбранную тему в localStorage
            localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
        });
    }
});
