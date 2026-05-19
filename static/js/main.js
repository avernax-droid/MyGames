// static/js/main.js

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.querySelector('.file-input');
    const fileDropArea = document.querySelector('.file-drop-area');

    if (fileInput) {
        fileInput.addEventListener('change', function(e) {
            const files = e.target.files;
            if (files.length > 0) {
                // Muda o texto da dropzone para mostrar a contagem
                const msg = document.querySelector('.file-msg');
                msg.innerText = `${files.length} foto(s) selecionada(s)`;
                fileDropArea.style.borderColor = '#00ff00';
            }
        });
    }
});
