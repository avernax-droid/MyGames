/* ==============================================================================
  PROJETO: MyGames
  MÓDULO: static/js/main.js
  DATA DE CRIAÇÃO: 28/05/2026
  TÍTULO: Script Global de Interação da UI
  FUNÇÃO: Centraliza comportamentos universais de interface (UX). Responsável 
  pela lógica de upload de arquivos (dropzone) utilizada em diversas etapas da 
  perícia, garantindo um comportamento visual consistente em todo o sistema.
  
  HISTÓRICO DE ALTERAÇÕES:
  - 28/05/2026: Inclusão do cabeçalho padrão de documentação e consolidação 
    da lógica global de upload de arquivos.
  ==============================================================================
*/

document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const fileDropArea = document.getElementById('drop-area');
    const fileMsg = document.getElementById('file-msg');

    if (fileInput && fileDropArea) {
        // Manipulador de mudança de arquivo (seleção via clique)
        fileInput.addEventListener('change', function() {
            const count = this.files.length;
            if (count > 0) {
                fileMsg.innerText = count + (count > 1 ? " arquivos selecionados" : " arquivo selecionado");
                fileMsg.style.color = "var(--neon-green)";
                fileMsg.style.fontWeight = "bold";
            } else {
                fileMsg.innerText = "ou arraste as imagens aqui";
                fileMsg.style.color = "var(--text-dim)";
            }
        });

        // Eventos de Drag and Drop
        ['dragenter', 'dragover'].forEach(eventName => {
            fileDropArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                fileDropArea.style.borderColor = "var(--neon-green)";
                fileDropArea.style.background = "rgba(0, 255, 0, 0.05)";
            });
        });

        ['dragleave', 'drop'].forEach(eventName => {
            fileDropArea.addEventListener(eventName, (e) => {
                e.preventDefault();
                fileDropArea.style.borderColor = "#475569";
                fileDropArea.style.background = "rgba(0,0,0,0.2)";
            });
        });
    }
});