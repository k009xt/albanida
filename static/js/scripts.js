            // Функции перехода по кнопкам
            window.goHome = function () {
                window.location.href = '/'; // Переход на главную страницу
            };

            window.goToCart = function () {
                window.location.href = '/cart'; // Переход в корзину
            };

            window.viewOrders = function () {
                window.location.href = '/orders'; // Переход в раздел заказов
            };
            let lastScrollTop = 0;
            const mobileNav = document.getElementById('mobileNav');

