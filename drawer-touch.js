/**
 * Qub Hunter — Gestion tactile du Drawer
 */
'use strict';

document.addEventListener('DOMContentLoaded', () => {
    const drawer = document.querySelector('.drawer');
    const handle = document.querySelector('.drawer-handle');

    let startY = 0;
    let currentY = 0;
    let isDragging = false;
    const closedOffset = 80; // Correspond au CSS calc(100% - 80px)

    // Fonction pour le retour haptique (vibration légère)
    const triggerHaptic = () => {
        if (navigator.vibrate) {
            navigator.vibrate(15); // Une impulsion très courte de 15ms
        }
    };

    if (!drawer || !handle) return;

    handle.addEventListener('touchstart', (e) => {
        startY = e.touches[0].clientY;
        isDragging = true;
        drawer.style.transition = 'none'; // Désactive l'anim pendant le drag
    }, { passive: true });

    document.addEventListener('touchmove', (e) => {
        if (!isDragging) return;

        currentY = e.touches[0].clientY;
        const deltaY = currentY - startY;

        // Permet au drawer de suivre le doigt en temps réel
        if (!drawer.classList.contains('is-open') && deltaY < 0) {
            // Glissement vers le haut (ouverture)
            drawer.style.transform = `translateY(calc(100% - ${closedOffset}px - env(safe-area-inset-bottom) + ${deltaY}px))`;
        } else if (drawer.classList.contains('is-open') && deltaY > 0) {
            // Glissement vers le bas (fermeture)
            drawer.style.transform = `translateY(${deltaY}px)`;
        }
    }, { passive: true });

    handle.addEventListener('touchend', (e) => {
        isDragging = false;
        drawer.style.transition = '';
        drawer.style.transform = ''; // Libère le style inline pour laisser les classes CSS agir

        const endY = e.changedTouches[0].clientY;
        const diff = startY - endY;

        // Seuil de 50px pour déclencher l'action
        if (diff > 50) {
            if (!drawer.classList.contains('is-open')) triggerHaptic();
            drawer.classList.add('is-open');
        } else if (diff < -50) {
            if (drawer.classList.contains('is-open')) triggerHaptic();
            drawer.classList.remove('is-open');
        }
    });

    // Toggle au clic simple sur la poignée
    handle.addEventListener('click', () => {
        triggerHaptic();
        drawer.classList.toggle('is-open');
    });
});