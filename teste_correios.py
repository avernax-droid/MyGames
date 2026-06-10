from engine import gerar_logistica_reversa

# Simulando os dados exatos que a API dos Correios exige do remetente (cliente)
dados_cliente_mock = {
    "nome": "Desenvolvedor Teste",
    "ddd": "11",
    "telefone": "988887777",
    "email": "dev@mygames.com.br",
    "cep": "01001000",
    "logradouro": "Praça da Sé",
    "numero": "1",
    "bairro": "Sé",
    "cidade": "São Paulo",
    "uf": "SP"
}

print("--- INICIANDO TESTE DE COMUNICAÇÃO COM CORREIOS ---")
resultado = gerar_logistica_reversa(dados_cliente_mock)

print("\n--- RESULTADO FINAL DO TESTE ---")
print(f"Valores retornados pela função: {resultado}")