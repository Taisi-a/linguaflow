// ===== ОСНОВНОЙ JAVASCRIPT =====

document.addEventListener('DOMContentLoaded', function() {
    // Инициализация приложения
    initApp();

    // Мобильное меню
    initMobileMenu();

    // Обработка форм
    initForms();

    // Интерактивные элементы
    initInteractiveElements();
});

// Инициализация приложения
function initApp() {
    console.log('LinguaFlow запущен 🚀');

    // Проверка авторизации
    checkAuthStatus();

    // Установка текущего года в футере
    const yearElement = document.querySelector('.current-year');
    if (yearElement) {
        yearElement.textContent = new Date().getFullYear();
    }

    // Добавление класса active для текущей страницы
    highlightCurrentPage();
}

// Проверка статуса авторизации
function checkAuthStatus() {
    const authElements = document.querySelectorAll('.auth-only');
    const guestElements = document.querySelectorAll('.guest-only');

    // Это упрощенная проверка, в реальном приложении нужно проверять токен
    const isAuthenticated = document.cookie.includes('session_id');

    if (isAuthenticated) {
        authElements.forEach(el => el.style.display = '');
        guestElements.forEach(el => el.style.display = 'none');
    } else {
        authElements.forEach(el => el.style.display = 'none');
        guestElements.forEach(el => el.style.display = '');
    }
}

// Подсветка текущей страницы
function highlightCurrentPage() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll('.nav-link');

    navLinks.forEach(link => {
        const linkPath = link.getAttribute('href');
        if (linkPath === currentPath ||
            (currentPath === '/' && linkPath === '/') ||
            (currentPath.startsWith('/dashboard') && linkPath === '/dashboard')) {
            link.classList.add('active');
        }
    });
}

// Мобильное меню
function initMobileMenu() {
    const menuBtn = document.querySelector('.mobile-menu-btn');
    const mobileMenu = document.querySelector('.mobile-menu');
    const overlay = document.querySelector('.mobile-menu-overlay');
    const closeBtn = document.querySelector('.mobile-menu-close');

    if (!menuBtn) return;

    // Открытие меню
    menuBtn.addEventListener('click', function() {
        mobileMenu.classList.add('active');
        overlay.classList.add('active');
        document.body.style.overflow = 'hidden';
    });

    // Закрытие меню
    function closeMenu() {
        mobileMenu.classList.remove('active');
        overlay.classList.remove('active');
        document.body.style.overflow = '';
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', closeMenu);
    }

    if (overlay) {
        overlay.addEventListener('click', closeMenu);
    }

    // Закрытие по Esc
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            closeMenu();
        }
    });

    // Копирование навигационных ссылок в мобильное меню
    const navLinks = document.querySelectorAll('.nav-link:not(.nav-btn)');
    const mobileMenuLinks = document.querySelector('.mobile-menu-links');

    if (mobileMenuLinks && navLinks.length > 0) {
        mobileMenuLinks.innerHTML = '';

        navLinks.forEach(link => {
            const clone = link.cloneNode(true);
            clone.classList.add('mobile-menu-link');
            clone.addEventListener('click', closeMenu);
            mobileMenuLinks.appendChild(clone);
        });
    }
}

// Обработка форм
function initForms() {
    // Переключение видимости пароля
    const passwordToggles = document.querySelectorAll('.password-toggle');

    passwordToggles.forEach(toggle => {
        toggle.addEventListener('click', function() {
            const input = this.parentElement.querySelector('input');
            const icon = this.querySelector('i');

            if (input.type === 'password') {
                input.type = 'text';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            } else {
                input.type = 'password';
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            }
        });
    });

    // Валидация форм
    const forms = document.querySelectorAll('form');

    forms.forEach(form => {
        form.addEventListener('submit', function(e) {
            if (!validateForm(this)) {
                e.preventDefault();
            } else {
                // Показ загрузки
                const submitBtn = this.querySelector('button[type="submit"]');
                if (submitBtn) {
                    submitBtn.innerHTML = '<span class="loading"></span> Загрузка...';
                    submitBtn.disabled = true;
                }
            }
        });
    });

    // Подсчет символов в textarea
    const textareas = document.querySelectorAll('textarea[data-maxlength]');

    textareas.forEach(textarea => {
        const maxLength = textarea.getAttribute('data-maxlength');
        const counter = document.createElement('div');
        counter.className = 'char-counter';
        counter.textContent = `0/${maxLength}`;
        textarea.parentElement.appendChild(counter);

        textarea.addEventListener('input', function() {
            const length = this.value.length;
            counter.textContent = `${length}/${maxLength}`;

            if (length > maxLength * 0.9) {
                counter.style.color = '#ef4444';
            } else if (length > maxLength * 0.7) {
                counter.style.color = '#f59e0b';
            } else {
                counter.style.color = '#6b7280';
            }
        });
    });
}

// Валидация формы
function validateForm(form) {
    let isValid = true;
    const inputs = form.querySelectorAll('input[required], textarea[required], select[required]');

    inputs.forEach(input => {
        // Сброс предыдущих ошибок
        input.classList.remove('error');
        const errorMsg = input.parentElement.querySelector('.error-message');
        if (errorMsg) errorMsg.remove();

        // Проверка на пустое значение
        if (!input.value.trim()) {
            showError(input, 'Это поле обязательно для заполнения');
            isValid = false;
        }

        // Проверка email
        if (input.type === 'email' && input.value) {
            const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
            if (!emailRegex.test(input.value)) {
                showError(input, 'Введите корректный email');
                isValid = false;
            }
        }

        // Проверка пароля
        if (input.type === 'password' && input.value) {
            if (input.value.length < 6) {
                showError(input, 'Пароль должен быть не менее 6 символов');
                isValid = false;
            }
        }
    });

    return isValid;
}

// Показать ошибку
function showError(input, message) {
    input.classList.add('error');

    const errorDiv = document.createElement('div');
    errorDiv.className = 'error-message';
    errorDiv.innerHTML = `<i class="fas fa-exclamation-circle"></i> ${message}`;

    input.parentElement.appendChild(errorDiv);
}

// Интерактивные элементы
function initInteractiveElements() {
    // Плавная прокрутка
    const smoothLinks = document.querySelectorAll('a[href^="#"]');

    smoothLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();

            const targetId = this.getAttribute('href');
            if (targetId === '#') return;

            const targetElement = document.querySelector(targetId);
            if (targetElement) {
                window.scrollTo({
                    top: targetElement.offsetTop - 80,
                    behavior: 'smooth'
                });
            }
        });
    });

    // Анимация при скролле
    initScrollAnimations();

    // Подтверждение удаления
    const deleteButtons = document.querySelectorAll('.btn-delete, a[href*="delete"]');

    deleteButtons.forEach(btn => {
        btn.addEventListener('click', function(e) {
            if (!confirm('Вы уверены, что хотите удалить этот элемент?')) {
                e.preventDefault();
            }
        });
    });

    // Копирование в буфер обмена
    const copyButtons = document.querySelectorAll('.btn-copy');

    copyButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            const textToCopy = this.getAttribute('data-copy') ||
                             this.parentElement.querySelector('code').textContent;

            navigator.clipboard.writeText(textToCopy)
                .then(() => {
                    const originalText = this.innerHTML;
                    this.innerHTML = '<i class="fas fa-check"></i> Скопировано!';

                    setTimeout(() => {
                        this.innerHTML = originalText;
                    }, 2000);
                })
                .catch(err => {
                    console.error('Ошибка копирования:', err);
                });
        });
    });

    // Переключение тем
    const themeToggle = document.querySelector('.theme-toggle');

    if (themeToggle) {
        const currentTheme = localStorage.getItem('theme') || 'light';

        if (currentTheme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
            themeToggle.innerHTML = '<i class="fas fa-sun"></i>';
        }

        themeToggle.addEventListener('click', function() {
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

            document.documentElement.setAttribute('data-theme', newTheme);
            localStorage.setItem('theme', newTheme);

            this.innerHTML = newTheme === 'dark' ?
                '<i class="fas fa-sun"></i>' :
                '<i class="fas fa-moon"></i>';
        });
    }
}

// Анимации при скролле
function initScrollAnimations() {
    const observerOptions = {
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px'
    };

    const observer = new IntersectionObserver(function(entries) {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animated');
            }
        });
    }, observerOptions);

    // Наблюдаем за элементами с анимацией
    const animatedElements = document.querySelectorAll('.feature-card, .stat-card, .word-card');
    animatedElements.forEach(el => observer.observe(el));
}

// Уведомления
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${getNotificationIcon(type)}"></i>
        <span>${message}</span>
        <button class="notification-close"><i class="fas fa-times"></i></button>
    `;

    document.body.appendChild(notification);

    // Показываем уведомление
    setTimeout(() => {
        notification.classList.add('show');
    }, 100);

    // Закрытие уведомления
    const closeBtn = notification.querySelector('.notification-close');
    closeBtn.addEventListener('click', () => {
        notification.classList.remove('show');
        setTimeout(() => notification.remove(), 300);
    });

    // Автоматическое закрытие
    setTimeout(() => {
        if (notification.parentElement) {
            notification.classList.remove('show');
            setTimeout(() => notification.remove(), 300);
        }
    }, 5000);
}

function getNotificationIcon(type) {
    const icons = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };
    return icons[type] || 'info-circle';
}

// Стили для уведомлений (можно добавить в CSS)
const notificationStyles = document.createElement('style');
notificationStyles.textContent = `
    .notification {
        position: fixed;
        top: 20px;
        right: 20px;
        background: white;
        border-radius: var(--radius-md);
        padding: var(--space-md) var(--space-lg);
        box-shadow: var(--shadow-xl);
        display: flex;
        align-items: center;
        gap: var(--space-md);
        z-index: 9999;
        transform: translateX(400px);
        transition: transform 0.3s ease;
        max-width: 400px;
    }

    .notification.show {
        transform: translateX(0);
    }

    .notification-success {
        border-left: 4px solid #10b981;
    }

    .notification-error {
        border-left: 4px solid #ef4444;
    }

    .notification-warning {
        border-left: 4px solid #f59e0b;
    }

    .notification-info {
        border-left: 4px solid #3b82f6;
    }

    .notification i:first-child {
        font-size: 1.25rem;
    }

    .notification-success i:first-child {
        color: #10b981;
    }

    .notification-error i:first-child {
        color: #ef4444;
    }

    .notification-warning i:first-child {
        color: #f59e0b;
    }

    .notification-info i:first-child {
        color: #3b82f6;
    }

    .notification-close {
        background: none;
        border: none;
        color: var(--text-light);
        cursor: pointer;
        padding: var(--space-xs);
        margin-left: auto;
    }

    .notification-close:hover {
        color: var(--text-primary);
    }
`;

document.head.appendChild(notificationStyles);

// Экспорт функций для использования в других файлах
window.LinguaFlow = {
    showNotification,
    validateForm
};