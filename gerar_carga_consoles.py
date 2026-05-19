import requests
import json

# BLOCO 1: Mapeamento Dinâmico e URLs Diretas de Backup
CONSOLES_MAP = {
    13: {"nome": "PlayStation 1", "wiki": "PlayStation (console)"},
    14: {"nome": "PlayStation 2 FAT", "wiki": "PlayStation 2"},
    15: {"nome": "PlayStation 2 Slim", "wiki": "PlayStation 2"},
    16: {"nome": "PlayStation Portable", "wiki": "PlayStation Portable"},
    17: {"nome": "PlayStation Vita (Old)", "wiki": "PlayStation Vita"},
    18: {"nome": "PlayStation Vita (New)", "wiki": "PlayStation Vita"},
    20: {"nome": "Xbox 1", "wiki": "Xbox (console)"},
    24: {"nome": "Super Nintendo", "wiki": "Super Nintendo Entertainment System"},
    25: {"nome": "Nintendo 64", "wiki": "Nintendo 64"},
    
    # SOLUÇÃO DEFINITIVA: Links diretos da imagem oficial da Infobox da Wikipedia para o Xbox 360
    26: {"nome": "Xbox 360 Slim e Super - 120 GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    27: {"nome": "Xbox 360 Slim e Super - 160 GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    28: {"nome": "Xbox 360 Slim e Super - 250 GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    29: {"nome": "Xbox 360 Slim e Super - 500 GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    34: {"nome": "Xbox 360 - 4GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    35: {"nome": "Xbox 360 - 250GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    36: {"nome": "Xbox 360 - 500GB", "url_direta": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Xbox-360-S-Console-wController.png/500px-Xbox-360-S-Console-wController.png"},
    
    41: {"nome": "Nintendo DS Lite", "wiki": "Nintendo DS Lite"},
    42: {"nome": "Nintendo DS XL", "wiki": "Nintendo DSi"},
    43: {"nome": "Nintendo 2DS", "wiki": "Nintendo 2DS"},
    44: {"nome": "Nintendo New 2DS XL", "wiki": "New Nintendo 2DS XL"},
    45: {"nome": "Nintendo 3DS", "wiki": "Nintendo 3DS"},
    46: {"nome": "Nintendo 3DS XL", "wiki": "Nintendo 3DS"},
    47: {"nome": "Nintendo New 3DS XL", "wiki": "New Nintendo 3DS XL"},
    49: {"nome": "PlayStation 4 Fat - 500GB", "wiki": "PlayStation 4"},
    50: {"nome": "PlayStation 4 Fat - 1TB", "wiki": "PlayStation 4"},
    51: {"nome": "PlayStation 4 Slim - 500GB", "wiki": "PlayStation 4"},
    52: {"nome": "PlayStation 4 Slim - 1TB", "wiki": "PlayStation 4"},
    53: {"nome": "PlayStation 4 Pro - 1TB", "wiki": "PlayStation 4"},
    54: {"nome": "PlayStation 4 Pro - Personalizado", "wiki": "PlayStation 4"},
    61: {"nome": "Xbox One Fat - 500GB", "wiki": "Xbox One"},
    62: {"nome": "Xbox One Fat - 1TB", "wiki": "Xbox One"},
    63: {"nome": "Xbox One S - All Digital", "wiki": "Xbox One"},
    64: {"nome": "Xbox One S - 500Gb", "wiki": "Xbox One"},
    65: {"nome": "Xbox One S - 1TB", "wiki": "Xbox One"},
    66: {"nome": "Xbox One X - 1TB", "wiki": "Xbox One"},
    71: {"nome": "Wii", "wiki": "Wii"},
    74: {"nome": "WiiU", "wiki": "Wii U"}
}

# BLOCO 2: Mapeamento Estático
ACESSORIOS_E_LOTES_MAP = {
    21: {"nome": "Jogos (Sony)", "url": "/static/images/catalogo/lote_jogos_sony.png"},
    30: {"nome": "Jogos (Microsoft) - Categoria 1", "url": "/static/images/catalogo/lote_jogos_xbox.png"},
    31: {"nome": "Jogos Esporte", "url": "/static/images/catalogo/lote_jogos_esporte.png"},
    37: {"nome": "Jogos (Microsoft) - Categoria 2", "url": "/static/images/catalogo/lote_jogos_xbox.png"},
    48: {"nome": "Jogos 3DS", "url": "/static/images/catalogo/lote_jogos_nintendo.png"},
    55: {"nome": "Jogos Comuns", "url": "/static/images/catalogo/lote_jogos_comuns.png"},
    56: {"nome": "Jogos Top", "url": "/static/images/catalogo/lote_jogos_top.png"},
    67: {"nome": "Jogos (Nintendo) - Xone S", "url": "/static/images/catalogo/lote_jogos_nintendo.png"},
    72: {"nome": "Jogos (Nintendo) - Wii", "url": "/static/images/catalogo/lote_jogos_nintendo.png"},
    75: {"nome": "Jogos (Nintendo) - WiiU", "url": "/static/images/catalogo/lote_jogos_nintendo.png"},
    22: {"nome": "Controle (Sony)", "url": "/static/images/catalogo/controle_ps4.png"},
    32: {"nome": "Controle (Microsoft) - Categoria 1", "url": "/static/images/catalogo/controle_xbox360.png"},
    39: {"nome": "Controle (Microsoft) - Categoria 2", "url": "/static/images/catalogo/controle_xbox360.png"},
    57: {"nome": "Controle (Nintendo)", "url": "/static/images/catalogo/controle_switch_pro.png"},
    59: {"nome": "Volantes", "url": "/static/images/catalogo/volante_logitech.png"},
    69: {"nome": "Controle (Nintendo) - Xone S", "url": "/static/images/catalogo/controle_xboxone.png"},
    73: {"nome": "Controle (O par) (Nintendo)", "url": "/static/images/catalogo/controles_wiimote.png"},
    76: {"nome": "Controle (Nintendo) - WiiU", "url": "/static/images/catalogo/controle_wiiu_pro.png"},
    38: {"nome": "Kinect Xbox 360", "url": "/static/images/catalogo/kinect_360.png"},
    58: {"nome": "VR1 Óculos PlayStation", "url": "/static/images/catalogo/psvr.png"},
    68: {"nome": "Kinect One", "url": "/static/images/catalogo/kinect_one.png"}
}

def obter_url_imagem_wiki(termo_busca):
    url_api = "https://en.wikipedia.org/w/api.php"
    headers = {
        "User-Agent": "MyGamesBot/1.0 (contato@mygames.com.br) Python-Requests/2.0"
    }
    params = {
        "action": "query",
        "titles": termo_busca,
        "prop": "pageimages",
        "format": "json",
        "pithumbsize": 500,
        "redirects": 1
    }
    try:
        response = requests.get(url_api, params=params, headers=headers, timeout=10)
        data = response.json()
        pages = data.get("query", {}).get("pages", {})
        for page_id, page_info in pages.items():
            if "thumbnail" in page_info:
                return page_info["thumbnail"]["source"]
    except Exception as e:
        print(f"Erro ao buscar {termo_busca}: {e}")
    return None

def gerar_sql_completo():
    print("🎮 Iniciando geração do Script de Carga Híbrido (Wikipedia API + Dados Estáticos)...\n")
    
    linhas_sql = [
        "-- =====================================================================\n",
        "-- SCRIPT DE CARGA GERADO AUTOMATICAMENTE: POPULA_CONSOLES.SQL\n",
        "-- =====================================================================\n\n"
    ]
    
    linhas_sql.append("-- [BLOCO 1] ATUALIZAÇÃO DE CONSOLES REAIS (WIKIPEDIA / URL DIRETA)\n")
    for prod_id, info in CONSOLES_MAP.items():
        # Se o item já tiver uma URL direta de backup, usa ela. Senão, vai na API.
        if "url_direta" in info:
            url_imagem = info["url_direta"]
            print(f"Injetando link direto para: {info['nome']}...")
        else:
            print(f"Buscando arte oficial para: {info['nome']}...")
            url_imagem = obter_url_imagem_wiki(info["wiki"])
        
        if url_imagem:
            url_imagem = url_imagem.replace("'", "''")
            sql = f"UPDATE catalogo_mestre SET foto_oficial_url = '{url_imagem}' WHERE id = {prod_id};\n"
            linhas_sql.append(sql)
            print(f"  ✓ Sucesso: {url_imagem[:65]}...")
        else:
            linhas_sql.append(f"-- ✗ Falha ao obter imagem para ID {prod_id} ({info['nome']})\n")
            print(f"  ✗ Imagem não localizada para {info['nome']}.")
            
    linhas_sql.append("\n")
    
    linhas_sql.append("-- [BLOCO 2] ATUALIZAÇÃO DE ACESSÓRIOS, CONTROLES E LOTES GENÉRICOS (ESTÁTICO LOCAL)\n")
    print("\n📦 Injetando referências locais para acessórios e lotes genéricos...")
    for prod_id, info in ACESSORIOS_E_LOTES_MAP.items():
        sql = f"UPDATE catalogo_mestre SET foto_oficial_url = '{info['url']}' WHERE id = {prod_id};\n"
        linhas_sql.append(sql)
    print(f"  ✓ Sucesso: {len(ACESSORIOS_E_LOTES_MAP)} registros de balcão mapeados.")

    nome_arquivo = "popula_consoles.sql"
    with open(nome_arquivo, "w", encoding="utf-8") as f:
        f.writelines(linhas_sql)
        
    print(f"\n🚀 Pronto! O arquivo '{nome_arquivo}' foi unificado e salvo com sucesso na raiz.")

if __name__ == "__main__":
    gerar_sql_completo()