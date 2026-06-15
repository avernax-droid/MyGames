import os
import requests
import xml.etree.ElementTree as ET
from dotenv import load_dotenv
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CORREIOS SOAP] %(levelname)s - %(message)s')

# Força a recarga do .env ignorando qualquer cache
load_dotenv(override=True)

usuario = os.getenv('CORREIOS_USER')
senha = os.getenv('CORREIOS_PASS')
cartao = os.getenv('CORREIOS_CARTAO_POSTAGEM')
contrato = os.getenv('CORREIOS_CONTRATO')

# Dados do remetente (Cliente do Buyback simulado)
dados_remetente = {
    "nome": "Leonardo Madruga Teste",
    "cep": "02042010", # Teste com CEP de SP (aciona SEDEX: 04679)
    # "cep": "20000000", # Mude para um CEP do RJ ou outro estado para testar o PAC (04677)
    "logradouro": "Avenida Leoncio de Magalhaes",
    "numero": "179",
    "complemento": "Apto 12",
    "bairro": "Jardim Sao Paulo",
    "cidade": "Sao Paulo",
    "uf": "SP",
    "ddd": "11",
    "telefone": "999999999"
}

print("\n--- INICIANDO TESTE DE LOGÍSTICA REVERSA DINÂMICA (VIA SOAP/XML) ---")

# Limpa o CEP para garantir apenas números
cep_cliente = ''.join(filter(str.isdigit, str(dados_remetente.get('cep', ''))))

CODIGO_SEDEX_REVERSO = "04679"
CODIGO_PAC_REVERSO = "04677"

codigo_servico = CODIGO_PAC_REVERSO

# Lógica de roteamento dinâmico
if cep_cliente and len(cep_cliente) == 8:
    if int(cep_cliente) < 20000000:
        codigo_servico = CODIGO_SEDEX_REVERSO
        logging.info(f"Regra de CEP: {cep_cliente} -> Classificado como SEDEX REVERSO ({codigo_servico})")
    else:
        codigo_servico = CODIGO_PAC_REVERSO
        logging.info(f"Regra de CEP: {cep_cliente} -> Classificado como PAC REVERSO ({codigo_servico})")

url_soap = "https://cws.correios.com.br/logisticaReversaWS/logisticaReversaService/logisticaReversaWS"

# Construção do Envelope XML dinâmico
xml_payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ser="http://service.logisticareversa.correios.com.br/">
   <soapenv:Header/>
   <soapenv:Body>
      <ser:solicitarPostagemReversa>
         <codAdministrativo>{contrato}</codAdministrativo>
         <codigo_servico>{codigo_servico}</codigo_servico>
         <cartao>{cartao}</cartao>
         <destinatario>
            <nome>MyGames - Laboratorio de Pericia</nome>
            <logradouro>Av Leoncio de Magalhaes</logradouro>
            <numero>179</numero>
            <complemento>Galpao</complemento>
            <bairro>Jardim Sao Paulo</bairro>
            <referencia></referencia>
            <cidade>Sao Paulo</cidade>
            <uf>SP</uf>
            <cep>02042010</cep>
            <telefone>11999999999</telefone>
            <email>contato@mygames.com.br</email>
         </destinatario>
         <coletas_solicitadas>
            <tipo>A</tipo>
            <numero></numero>
            <ag></ag>
            <remetente>
               <nome>{dados_remetente['nome'][:50]}</nome>
               <logradouro>{dados_remetente['logradouro'][:50]}</logradouro>
               <numero>{dados_remetente['numero'][:10]}</numero>
               <complemento>{dados_remetente['complemento'][:30]}</complemento>
               <bairro>{dados_remetente['bairro'][:50]}</bairro>
               <referencia></referencia>
               <cidade>{dados_remetente['cidade'][:50]}</cidade>
               <uf>{dados_remetente['uf'][:2]}</uf>
               <cep>{dados_remetente['cep'][:8]}</cep>
               <ddd>{dados_remetente['ddd'][:2]}</ddd>
               <telefone>{dados_remetente['telefone'][:9]}</telefone>
               <email></email>
            </remetente>
            <obj_col>
               <item>1</item>
               <desc>Produtos Buyback MyGames</desc>
               <entrega></entrega>
               <num></num>
               <id></id>
            </obj_col>
         </coletas_solicitadas>
      </ser:solicitarPostagemReversa>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": ""
}

auth_http = (usuario, senha)

try:
    logging.info(f"Disparando Envelope SOAP para os Correios (Serviço: {codigo_servico})...")
    resp = requests.post(url_soap, data=xml_payload.encode('utf-8'), headers=headers, auth=auth_http, timeout=15)
    
    logging.info(f"Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        root = ET.fromstring(resp.text)
        
        e_ticket = None
        msg_erro = None
        
        for elem in root.iter():
            if 'numero_pedido' in elem.tag:
                e_ticket = elem.text
            if 'msg_erro' in elem.tag and elem.text:
                msg_erro = elem.text
        
        if e_ticket:
            print("\n✅ SUCESSO ABSOLUTO (SOAP)!")
            print(f"E-Ticket gerado: {e_ticket} via serviço {codigo_servico}")
        else:
            print("\n⚠️ A requisição passou, mas houve uma recusa de negócio dos Correios.")
            print(f"Motivo: {msg_erro}")
    else:
        print("\n❌ FALHA NA INTEGRAÇÃO.")
        print(f"Body: {resp.text}")

except Exception as e:
    print(f"Erro interno na requisição SOAP: {e}")