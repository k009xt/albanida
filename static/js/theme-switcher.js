document.addEventListener('DOMContentLoaded', function () {
    const savedTheme = localStorage.getItem('theme') || 'light';

    // ��������� ����������� ���� �� ���� ���������
    if (savedTheme === 'dark') {
        document.body.classList.add('dark-mode');
        document.body.classList.remove('light-mode');
    } else {
        document.body.classList.add('light-mode');
        document.body.classList.remove('dark-mode');
    }

    // �������� ������� ������������� �� ��������
    const themeToggleSwitch = document.getElementById('themeToggleSwitch');
    if (themeToggleSwitch) {
        // ������������� ��������� ������������� �� ������ ����������� ����
        themeToggleSwitch.checked = savedTheme === 'dark';

        themeToggleSwitch.addEventListener('change', function () {
            const isDarkMode = themeToggleSwitch.checked;
            document.body.classList.toggle('dark-mode', isDarkMode);
            document.body.classList.toggle('light-mode', !isDarkMode);

            // ��������� ��������� ���� � localStorage
            localStorage.setItem('theme', isDarkMode ? 'dark' : 'light');
        });
    }
});
