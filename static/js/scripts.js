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

            window.addEventListener('scroll', function () {
                const scrollTop = window.pageYOffset || document.documentElement.scrollTop;
                if (scrollTop > lastScrollTop) {
                    // ��������� ���� � ������ ���������
                    mobileNav.classList.add('hidden');
                } else {
                    // ��������� ����� � �������� ���������
                    mobileNav.classList.remove('hidden');
                }
                lastScrollTop = scrollTop <= 0 ? 0 : scrollTop; // ��� �������������� ������������� ��������
            });
