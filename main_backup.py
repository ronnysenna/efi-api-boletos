from fastapi import FastAPI, HTTPException
import requests
import os
import json
from datetime import datetime, timedelta

app = FastAPI(title="API Consulta Boletos Efí")

# Configurações
EFI_CLIENT_ID = os.getenv('EFI_CLIENT_ID')
EFI_CLIENT_SECRET = os.getenv('EFI_CLIENT_SECRET')
EFI_SANDBOX = os.getenv('EFI_SANDBOX', 'False') == 'True'

# URLs da API Efí
if EFI_SANDBOX:
    BASE_URL = 'https://api-h.efipay.com.br'
else:
    BASE_URL = 'https://api.efipay.com.br'

# Para teste local, usa o certificado já convertido
cert_file = '/Users/ronnysenna/Projetos/Efi-Certificado/conversor-p12-efi/producao-N8N_new.pem'

# Cache do token OAuth2
token_cache = {
    'token': None,
    'expires_at': None
}

def get_access_token():
    """Obtém token de acesso OAuth2 da API Efí"""
    current_time = datetime.now()
    
    # Verifica se o token ainda é válido
    if (token_cache['token'] and 
        token_cache['expires_at'] and 
        current_time < token_cache['expires_at']):
        return token_cache['token']
    
    # Solicita novo token
    auth_url = f"{BASE_URL}/oauth/token"
    
    auth_data = {
        'grant_type': 'client_credentials'
    }
    
    try:
        response = requests.post(
            auth_url,
            auth=(EFI_CLIENT_ID, EFI_CLIENT_SECRET),
            data=auth_data,
            cert=cert_file,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data['access_token']
            expires_in = data.get('expires_in', 3600)  # padrão 1 hora
            
            # Atualiza cache
            token_cache['token'] = token
            token_cache['expires_at'] = current_time + timedelta(seconds=expires_in - 60)  # 60s de margem
            
            return token
        else:
            raise Exception(f"Erro ao obter token: {response.status_code} - {response.text}")
            
    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro de conexão ao obter token: {str(e)}")

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
            f'{BASE_URL}/v1/carnet',
            headers=headers,
            params={'begin_date': '2024-01-01', 'end_date': '2025-12-31'},
            cert=cert_file,
            timeout=30
        )
        
        if response.status_code != 200:
            return {
                'cpf': cpf_limpo,
                'erro': f'Status {response.status_code}',
                'mensagem': response.text[:500]
            }
        
        try:
            data = response.json()
        except ValueError:
            return {
                'cpf': cpf_limpo,
                'erro': 'Resposta não é JSON válido',
                'mensagem': response.text[:500]
            }
        
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
