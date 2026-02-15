/**
 * Mobile Long-Press Context Menu Support
 * Add this to enable long-press context menus on touch devices
 */

(function () {
    let pressTimer = null;
    let currentTarget = null;
    let contextMenuHandlers = {};

    /**
     * Setup long-press detection for an element
     * @param {HTMLElement} element - The element to attach long-press to
     * @param {Function} contextMenuFunction - Function to call on long-press or right-click
     */
    window.setupLongPress = function (element, contextMenuFunction) {
        // Touch events for mobile
        element.addEventListener('touchstart', function (e) {
            pressTimer = setTimeout(() => {
                // Prevent default behavior
                e.preventDefault();

                // Find the closest item with data attribute
                currentTarget = e.target.closest('[data-item-id], [data-vocab-id]');
                if (currentTarget) {
                    const touch = e.touches[0];
                    contextMenuFunction(currentTarget, {
                        pageX: touch.pageX,
                        pageY: touch.pageY,
                        preventDefault: () => e.preventDefault()
                    });
                }
            }, 500); // 500ms = long press
        }, { passive: false });

        element.addEventListener('touchend', function (e) {
            clearTimeout(pressTimer);
        });

        element.addEventListener('touchmove', function (e) {
            clearTimeout(pressTimer);
        });

        // Desktop right-click (keep existing functionality)
        element.addEventListener('contextmenu', function (e) {
            e.preventDefault();
            currentTarget = e.target.closest('[data-item-id], [data-vocab-id]');
            if (currentTarget) {
                contextMenuFunction(currentTarget, e);
            }
        });
    };

    /**
     * Show a context menu at specified position
     * @param {Object} options - Menu options
     */
    window.showContextMenu = function (options) {
        const { event, items, targetElement } = options;

        // Remove existing menu
        const existingMenu = document.getElementById('contextMenu');
        if (existingMenu) {
            existingMenu.remove();
        }

        // Create menu
        const menu = document.createElement('div');
        menu.id = 'contextMenu';
        menu.className = 'context-menu';
        menu.style.position = 'fixed';
        menu.style.display = 'block';

        // Add items
        items.forEach(item => {
            const menuItem = document.createElement('div');
            menuItem.className = 'context-menu-item' + (item.className ? ' ' + item.className : '');
            menuItem.innerHTML = `<span class="menu-icon">${item.icon || ''}</span> ${item.label}`;
            menuItem.onclick = function (e) {
                e.stopPropagation();
                item.action(targetElement);
                menu.style.display = 'none';
                menu.remove();
            };
            menu.appendChild(menuItem);
        });

        document.body.appendChild(menu);

        // Position menu
        const touch = event.touches ? event.touches[0] : event;
        menu.style.top = touch.pageY + 'px';
        menu.style.left = touch.pageX + 'px';

        // Adjust if menu goes off screen
        setTimeout(() => {
            const rect = menu.getBoundingClientRect();
            if (rect.right > window.innerWidth) {
                menu.style.left = (window.innerWidth - rect.width - 10) + 'px';
            }
            if (rect.bottom > window.innerHeight) {
                menu.style.top = (window.innerHeight - rect.height - 10) + 'px';
            }
        }, 10);
    };

    /**
     * Close the context menu
     */
    window.closeContextMenu = function () {
        const menu = document.getElementById('contextMenu');
        if (menu) {
            menu.style.display = 'none';
            menu.remove();
        }
    };

    // Close menu when clicking outside
    document.addEventListener('click', function (e) {
        if (!e.target.closest('.context-menu')) {
            closeContextMenu();
        }
    });

    // Close menu when touching outside
    document.addEventListener('touchstart', function (e) {
        if (!e.target.closest('.context-menu')) {
            closeContextMenu();
        }
    });
})();
