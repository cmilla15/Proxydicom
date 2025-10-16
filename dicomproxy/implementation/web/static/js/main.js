document.addEventListener('DOMContentLoaded', () => {
    let sessionIntervalId = null;
    function startSessionTimer() {
        const timerElement = document.getElementById('session-timer');
        if (!timerElement) return;
        if (sessionIntervalId) clearInterval(sessionIntervalId);
        let timeLeft = 15 * 60;
        sessionIntervalId = setInterval(() => {
            timeLeft--;
            const minutes = Math.floor(timeLeft / 60).toString().padStart(2, '0');
            const seconds = (timeLeft % 60).toString().padStart(2, '0');
            if (timerElement) { timerElement.textContent = `${minutes}:${seconds}`; }
            if (timeLeft <= 0) {
                clearInterval(sessionIntervalId);
                alert('La sesión ha expirado.');
                window.location.href = '/admin';
            }
        }, 1000);
    }
    startSessionTimer();
});
