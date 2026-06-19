import requests
import xml.etree.ElementTree as ET
import logging
import uuid

# Configuração de logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - [PORTAL POSTAL SOAP] %(levelname)s - %(message)s')

print("\n--- INICIANDO TESTE DE LOGÍSTICA REVERSA (PORTAL POSTAL - SEM SEQUÊNCIA LÓGICA) ---")

# Credenciais do Portal Postal (Hardcoded para teste temporário)
cod_agencia = 98
login_ws = "trocagames"
senha_ws = "@123456"
url_soap = "http://www.portalpostal.com.br/axis2/services/PrePostagemWS"

# Dados do remetente (Cliente do Buyback simulado)
dados_remetente = {
    "nome": "Leonardo Madruga Teste",
    "cep": "02042010", # Teste com CEP de SP (aciona SEDEX)
    "logradouro": "Avenida Leoncio de Magalhaes",
    "numero": "179",
    "complemento": "Apto 12",
    "bairro": "Jardim Sao Paulo",
    "cidade": "Sao Paulo",
    "uf": "SP"
}

# Limpa o CEP para garantir apenas números
cep_cliente = ''.join(filter(str.isdigit, str(dados_remetente.get('cep', ''))))

# Roteamento Dinâmico de Serviço
servico_correios = "PAC" # Fallback padrão
if cep_cliente and len(cep_cliente) == 8:
    if int(cep_cliente) < 20000000:
        servico_correios = "SEDEX"
        logging.info(f"Regra de CEP: {cep_cliente} -> Classificado como {servico_correios}")
    else:
        logging.info(f"Regra de CEP: {cep_cliente} -> Classificado como {servico_correios}")

# Geração de uma chave de protocolo única para o teste
protocolo_teste = f"TESTE-{uuid.uuid4().hex[:8].upper()}"
logging.info(f"Chave/Protocolo gerado para o teste: {protocolo_teste}")

# Construção do XML interno de postagem (Envelopado em CDATA depois)
xml_dados_postagem = f"""<portalpostal>
    <pre_postagem>
        <chave>{protocolo_teste}</chave>
        <nome>{dados_remetente['nome'][:100]}</nome>
        <cep>{cep_cliente}</cep>
        <endereco>{dados_remetente['logradouro'][:100]}</endereco>
        <numero>{dados_remetente['numero'][:10]}</numero>
        <complemento>{dados_remetente['complemento'][:100]}</complemento>
        <bairro>{dados_remetente['bairro'][:100]}</bairro>
        <cidade>{dados_remetente['cidade'][:100]}</cidade>
        <estado>{dados_remetente['uf'][:2]}</estado>
        <servico>{servico_correios}</servico>
        <conteudo>
            <item>
                <descricao>Console Xbox Series S Usado</descricao>
                <quantidade>1</quantidade>
                <valor>1200.00</valor>
            </item>
        </conteudo>
    </pre_postagem>
</portalpostal>"""

# Construção do Envelope SOAP com CDATA e Namespace corrigido (pos)
soap_payload = f"""<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:pos="http://postagem/xsd">
   <soapenv:Header/>
   <soapenv:Body>
      <pos:PrePostagemXml>
         <pos:xml><![CDATA[{xml_dados_postagem}]]></pos:xml>
         <pos:codAgencia>{cod_agencia}</pos:codAgencia>
         <pos:login>{login_ws}</pos:login>
         <pos:senha>{senha_ws}</pos:senha>
      </pos:PrePostagemXml>
   </soapenv:Body>
</soapenv:Envelope>"""

headers = {
    "Content-Type": "text/xml; charset=utf-8",
    "SOAPAction": "urn:PrePostagemXml"
}

try:
    logging.info(f"Disparando Envelope SOAP para o Portal Postal...")
    resp = requests.post(url_soap, data=soap_payload.encode('utf-8'), headers=headers, timeout=15)
    
    logging.info(f"Status Code: {resp.status_code}")
    
    if resp.status_code == 200:
        root = ET.fromstring(resp.text)
        
        codigo_rastreio = None
        detalhes_erro = None
        
        # A resposta do Portal Postal embute o XML de retorno dentro de uma tag text
        for elem in root.iter():
            if 'PrePostagemXmlReturn' in elem.tag or 'return' in elem.tag:
                retorno_xml_str = elem.text
                if retorno_xml_str:
                    retorno_root = ET.fromstring(retorno_xml_str)
                    
                    for postagem in retorno_root.findall('.//postagem'):
                        codigo_rastreio = postagem.findtext('codigo_rastreio')
                        if codigo_rastreio == 'erro':
                            detalhes_erro = postagem.findtext('detalhes')
                            codigo_rastreio = None
                    
                    for erro in retorno_root.findall('.//erro'):
                        detalhes_erro = erro.text

        if codigo_rastreio:
            print("\n✅ SUCESSO ABSOLUTO (SOAP)!")
            print(f"Código de Rastreio gerado: {codigo_rastreio} via serviço {servico_correios}")
        else:
            print("\n⚠️ A requisição passou, mas houve uma falha de negócio do Portal Postal.")
            print(f"Motivo: {detalhes_erro}")
    else:
        print("\n❌ FALHA NA INTEGRAÇÃO.")
        print(f"Body: {resp.text}")

except ET.ParseError as e:
    print(f"\n❌ Erro ao fazer o parser do XML de retorno: {e}")
    print(f"Resposta bruta: {resp.text}")
except Exception as e:
    print(f"\n❌ Erro interno na requisição HTTP/SOAP: {e}")