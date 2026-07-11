// main.js — students will add JavaScript here as features are built

document.addEventListener('DOMContentLoaded', function() {
    const demoBtn = document.getElementById('demo-btn');
    const demoModal = document.getElementById('demo-modal');
    const modalClose = document.querySelector('.modal-close');
    const modalOverlay = document.querySelector('.modal-overlay');
    const demoVideo = document.getElementById('demo-video');

    if (!demoBtn || !demoModal) return;

    const openModal = () => {
        demoModal.classList.add('active');
    };

    const closeModal = () => {
        demoModal.classList.remove('active');
        demoVideo.src = demoVideo.src;
    };

    demoBtn.addEventListener('click', openModal);
    modalClose.addEventListener('click', closeModal);
    modalOverlay.addEventListener('click', closeModal);

    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape' && demoModal.classList.contains('active')) {
            closeModal();
        }
    });
});
