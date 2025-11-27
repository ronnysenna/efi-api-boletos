from fastapi import FastAPI, HTTPException
import requests
import os
import base64
import re

app = FastAPI(title="API Consulta Boletos Efí")

# Lê o certificado da variável de ambiente
certificate_content = os.getenv('EFI_CERTIFICATE')
if not certificate_content:
    raise Exception("Certificado EFI_CERTIFICATE não configurado!")

# Remove espaços extras e normaliza
certificate_content = certificate_content.strip()

# Se o certificado estiver em uma linha só, reconstrua as quebras
if '\n' not in certificate_content:
    # Adiciona quebras de linha nos delimitadores
    certificate_content = certificate_content.replace('-----END CERTIFICATE-----', '-----END CERTIFICATE-----\n')
    certificate_content = certificate_content.replace('-----BEGIN PRIVATE KEY-----', '\n-----BEGIN PRIVATE KEY-----\n')
    certificate_content = certificate_content.replace('-----END PRIVATE KEY-----', '-----END PRIVATE KEY-----\n')

# Extrai o certificado
cert_start = certificate_content.find('-----BEGIN CERTIFICATE-----')
cert_end = certificate_content.find('-----END CERTIFICATE-----') + len('-----END CERTIFICATE-----')

# Extrai a chave privada
key_start = certificate_content.find('-----BEGIN PRIVATE KEY-----')
if key_start == -1:
    key_start = certificate_content.find('-----BEGIN RSA PRIVATE KEY-----')
key_end = certificate_content.find('-----END PRIVATE KEY-----')
if key_end == -1:
    key_end = certificate_content.find('-----END RSA PRIVATE KEY-----')
if key_end != -1:
    key_end += len('-----END PRIVATE KEY-----')

if cert_start == -1 or cert_end == -1:
    raise Exception(f"Certificado não encontrado no formato correto")
if key_start == -1 or key_end == -1:
    raise Exception(f"Chave privada não encontrada no formato correto")

cert_content = certificate_content[cert_start:cert_end]
key_content = certificate_content[key_start:key_end]

# Salva em arquivos separados
cert_file = '/tmp/cert.pem'
key_file = '/tmp/key.pem'

with open(cert_file, 'w') as f:
    f.write(cert_content)

with open(key_file, 'w') as f:
    f.write(key_content)

# Configurações
EFI_CLIENT_ID = os.getenv('EFI_CLIENT_ID')
EFI_CLIENT_SECRET = os.getenv('EFI_CLIENT_SECRET')
EFI_SANDBOX = os.getenv('EFI_SANDBOX', 'False') == 'True'

# URL base da API
BASE_URL = 'https://api-h.efipay.com.br' if EFI_SANDBOX else 'https://api.efipay.com.br'

@app.get("/")
async def root():
    return {"message": "API Efí - Consulta de Boletos", "status": "online"}

@app.get("/buscar-boleto/{cpf}")
async def buscar_boleto(cpf: str):
    try:
        # Remove caracteres não numéricos do CPF
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido")
        
        # Monta Basic Auth
        auth_string = f"{EFI_CLIENT_ID}:{EFI_CLIENT_SECRET}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        # Headers
        headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Parâmetros
        params = {
            'charge_type': 'carnet',
            'customer_document': cpf_limpo,
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31'
        }
        
        # Faz requisição com certificado
        response = requests.get(
            f'{BASE_URL}/v1/charges',
            headers=headers,
            params=params,
            cert=(cert_file, key_file),
            timeout=30
        )
        
        # Verifica status
        if response.status_code != 200:
            return {
                'cpf': cpf_limpo,
                'erro': f'API retornou status {response.status_code}',
                'mensagem': response.text
            }
        
        data = response.json()
        
        # Processa resposta
        if not data or 'data' not in data:
            return {
                'cpf': cpf_limpo,
                'total_boletos': 0,
                'boletos': [],
                'mensagem': 'Nenhum boleto encontrado'
            }
        
        # Filtra boletos em aberto
        boletos_abertos = []
        for b in data.get('data', []):
            if b.get('status') == 'waiting':
                payment = b.get('payment', {})
                banking_billet = payment.get('banking_billet', {})
                pix_info = payment.get('pix', {})
                
                boletos_abertos.append({
                    'charge_id': b.get('charge_id'),
                    'valor': f"R$ {b.get('total', 0)/100:.2f}",
                    'vencimento': b.get('expire_at', ''),
                    'status': b.get('status'),
                    'link': banking_billet.get('link', ''),
                    'barcode': banking_billet.get('barcode', ''),
                    'pix_copia_cola': pix_info.get('qrcode', '')
                })
        
        return {
            'cpf': cpf_limpo,
            'total_boletos': len(boletos_abertos),
            'boletos': boletos_abertos
        }
        
    except requests.exceptions.RequestException as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro de conexão: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro: {str(e)}"
        )

@app.get("/health")
async def health():
    return {"status": "ok", "service": "efi-api"}
