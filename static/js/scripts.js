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

            window.addEventListener('scroll', function () {
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                if (scrollTop > lastScrollTop) {
                    // Прокрутка вниз — скрыть навигацию
                    mobileNav.classList.add('hidden');
                } else {
                    // Прокрутка вверх — показать навигацию
                    mobileNav.classList.remove('hidden');
                }
                lastScrollTop = scrollTop <= 0 ? 0 : scrollTop; // Для предотвращения отрицательных значений
            });
