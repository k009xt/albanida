            // ������� �������� �� �������
            window.goHome = function () {
                window.location.href = '/'; // ������� �� ������� ��������
            };

            window.goToCart = function () {
                window.location.href = '/cart'; // ������� � �������
            };

            window.viewOrders = function () {
                window.location.href = '/orders'; // ������� � ������ �������
            };
            let lastScrollTop = 0;
            const mobileNav = document.getElementById('mobileNav');

