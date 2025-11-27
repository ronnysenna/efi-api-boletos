from fastapi import FastAPI, HTTPException
import requests
import os
import base64

app = FastAPI(title="API Consulta Boletos Efí")

# Lê o certificado da variável de ambiente
certificate_content = os.getenv('EFI_CERTIFICATE', '')
if not certificate_content:
    raise Exception("Certificado EFI_CERTIFICATE não configurado!")

# Remove espaços e normaliza
certificate_content = certificate_content.strip()

# Encontra as posições dos marcadores
markers = {
    'cert_start': certificate_content.find('-----BEGIN CERTIFICATE-----'),
    'cert_end': certificate_content.find('-----END CERTIFICATE-----'),
    'key_start': max(
        certificate_content.find('-----BEGIN PRIVATE KEY-----'),
        certificate_content.find('-----BEGIN RSA PRIVATE KEY-----')
    ),
    'key_end': max(
        certificate_content.find('-----END PRIVATE KEY-----'),
        certificate_content.find('-----END RSA PRIVATE KEY-----')
    )
}

# Valida
if markers['cert_start'] == -1 or markers['cert_end'] == -1:
    raise Exception(f"Certificado não encontrado. Conteúdo tem {len(certificate_content)} chars")

if markers['key_start'] == -1 or markers['key_end'] == -1:
    raise Exception(f"Chave privada não encontrada. Conteúdo: {certificate_content[markers['cert_end']:markers['cert_end']+100]}")

# Extrai (incluindo os marcadores finais)
cert_end_marker = '-----END CERTIFICATE-----'
key_end_marker = '-----END RSA PRIVATE KEY-----' if 'RSA' in certificate_content else '-----END PRIVATE KEY-----'

cert_content = certificate_content[markers['cert_start']:markers['cert_end'] + len(cert_end_marker)]
key_content = certificate_content[markers['key_start']:markers['key_end'] + len(key_end_marker)]

# Salva em arquivos
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
BASE_URL = 'https://api-h.efipay.com.br' if EFI_SANDBOX else 'https://api.efipay.com.br'

@app.get("/")
async def root():
    return {"message": "API Efí - Consulta de Boletos", "status": "online"}

@app.get("/buscar-boleto/{cpf}")
async def buscar_boleto(cpf: str):
    try:
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido")
        
        # Basic Auth
        auth_string = f"{EFI_CLIENT_ID}:{EFI_CLIENT_SECRET}"
        auth_base64 = base64.b64encode(auth_string.encode()).decode()
        
        headers = {
            'Authorization': f'Basic {auth_base64}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        params = {
            'charge_type': 'carnet',
            'customer_document': cpf_limpo,
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31'
        }
        
        response = requests.get(
            f'{BASE_URL}/v1/charges',
            headers=headers,
            params=params,
            cert=(cert_file, key_file),
            timeout=30
        )
        
        if response.status_code != 200:
            return {
                'cpf': cpf_limpo,
                'erro': f'Status {response.status_code}',
                'mensagem': response.text
            }
        
        data = response.json()
        
        if not data or 'data' not in data:
            return {
                'cpf': cpf_limpo,
                'total_boletos': 0,
                'boletos': [],
                'mensagem': 'Nenhum boleto encontrado'
            }
        
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
        raise HTTPException(status_code=500, detail=f"Erro de conexão: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "efi-api"}
