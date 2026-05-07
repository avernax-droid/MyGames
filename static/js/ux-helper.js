/**
 * MyGames - UX Helper (V1.9)
 * Responsável por Máscaras, Autocomplete e Integração ViaCEP
 */

// --- FUNÇÃO GLOBAL: BUSCA DE CEP (Acessível pelo onblur do HTML) ---
function buscarCEP(cep) {
    const valor = cep.replace(/\D/g, '');

    if (valor !== "" && valor.length === 8) {
        // Feedback visual de carregamento
        if(document.getElementById('endereco')) document.getElementById('endereco').value = "...";
        if(document.getElementById('bairro')) document.getElementById('bairro').value = "...";

        fetch(`https://viacep.com.br/ws/${valor}/json/`)
            .then(response => response.json())
            .then(dados => {
                if (!("erro" in dados)) {
                    // Preenchimento automático dos campos
                    document.getElementById('endereco').value = dados.logradouro;
                    document.getElementById('bairro').value = dados.bairro;
                    // Foca no número para agilizar a digitação
                    document.getElementById('numero').focus();
                } else {
                    alert("CEP não encontrado.");
                    document.getElementById('endereco').value = "";
                    document.getElementById('bairro').value = "";
                }
            })
            .catch(() => {
                alert("Erro ao consultar serviço de CEP.");
            });
    }
}

document.addEventListener('DOMContentLoaded', () => {
    const inputPhone = document.getElementById('whatsapp');
    const inputCidade = document.getElementById('cidade');
    const inputEstadoNome = document.getElementById('estado_nome');
    const inputEstadoUF = document.getElementById('estado_uf');
    const sugestoesCidades = document.getElementById('sugestoes-cidades');
    
    // Campos da Etapa 5 (Cadastro Complementar)
    const inputCPF = document.getElementById('cpf');
    const inputCEP = document.getElementById('cep');

    // --- 1. MÁSCARA DE TELEFONE ---
    if (inputPhone) {
        inputPhone.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, '');
            let formatted = "";
            if (value.length > 0) {
                formatted = "(" + value.substring(0, 2);
                if (value.length > 2) formatted += ") " + value.substring(2, 7);
                if (value.length > 7) formatted += "-" + value.substring(7, 11);
            }
            e.target.value = formatted;
        });
    }

    // --- 2. MÁSCARA DE CPF ---
    if (inputCPF) {
        inputCPF.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, '');
            let formatted = value.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
            if (value.length <= 11) {
                e.target.value = value.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4")
                                     .substring(0, 14);
            }
        });
    }

    // --- 3. MÁSCARA DE CEP ---
    if (inputCEP) {
        inputCEP.addEventListener('input', (e) => {
            let value = e.target.value.replace(/\D/g, '');
            if (value.length <= 8) {
                e.target.value = value.replace(/(\d{5})(\d{3})/, "$1-$2");
            }
        });
    }

    // --- 4. AUTOCOMPLETE CIDADES (API IBGE) ---
    if (inputCidade) {
        inputCidade.addEventListener('input', async (e) => {
            const termo = e.target.value;
            if (termo.length < 3) {
                if (sugestoesCidades) sugestoesCidades.innerHTML = '';
                return;
            }

            try {
                const response = await fetch(`https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome`);
                const cidades = await response.json();
                const filtradas = cidades
                    .filter(c => c.nome.toLowerCase().startsWith(termo.toLowerCase()))
                    .slice(0, 5);

                exibirSugestoes(filtradas);
            } catch (error) {
                console.error("Erro ao buscar cidades:", error);
            }
        });
    }

    function exibirSugestoes(lista) {
        if (!sugestoesCidades) return;
        sugestoesCidades.innerHTML = '';
        lista.forEach(cidade => {
            const div = document.createElement('div');
            div.classList.add('sugestao-item');
            div.innerText = `${cidade.nome} - ${cidade.microrregiao.mesorregiao.UF.sigla}`;
            
            div.addEventListener('click', () => {
                inputCidade.value = cidade.nome;
                if (inputEstadoNome) inputEstadoNome.value = cidade.microrregiao.mesorregiao.UF.nome;
                if (inputEstadoUF) inputEstadoUF.value = cidade.microrregiao.mesorregiao.UF.sigla;
                sugestoesCidades.innerHTML = '';
            });
            sugestoesCidades.appendChild(div);
        });
    }

    document.addEventListener('click', (e) => {
        if (sugestoesCidades && e.target !== inputCidade) {
            sugestoesCidades.innerHTML = '';
        }
    });
});