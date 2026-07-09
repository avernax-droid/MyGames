# MyGames - Plataforma de Compra e Venda de Jogos

# MyGames - Site Cliente (Buyback)

## Descrição
Aplicação web principal (Front-end) voltada para o cliente final, responsável pela captação de leads, funil de perícia e geração de propostas de venda.

## Como Instalar e Rodar no Servidor

### 1. Clonar o Repositório
```bash
git clone [https://github.com/avernax-droid/MyGames.git](https://github.com/avernax-droid/MyGames.git)
cd MyGames

2. Configuração do Banco de Dados
⚠️ Atenção: Esta aplicação compartilha o mesmo banco de dados do painel administrativo.
Se você já realizou a implantação do MyGames_Admin e rodou os scripts schema.sql e carga_configs.sql no servidor, pode pular esta etapa.

Caso contrário, execute a criação da estrutura e a carga inicial:

   mysql -u mygames_user -p mygames_prod < schema.sql
   mysql -u mygames_user -p mygames_prod < carga_configs.sql

3. Instalação das Dependências (Python)
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt

   