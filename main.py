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

# URLs da API Efí (baseado no SDK oficial)
if EFI_SANDBOX:
    BASE_URL = 'https://cobrancas-h.api.efipay.com.br/v1'  # URL correta para sandbox
else:
    BASE_URL = 'https://cobrancas.api.efipay.com.br/v1'    # URL correta para produção

# Configuração do certificado
certificate_content = os.getenv('EFI_CERTIFICATE', '')
if certificate_content and not os.path.exists('/tmp/certificado.pem'):
    # Converte \n literais em quebras de linha reais e salva em arquivo temporário
    cert_content = certificate_content.strip().replace('\\n', '\n')
    with open('/tmp/certificado.pem', 'w') as f:
        f.write(cert_content)
    cert_file = '/tmp/certificado.pem'
elif os.path.exists('/Users/ronnysenna/Projetos/Efi-Certificado/conversor-p12-efi/producao-N8N_new.pem'):
    # Para teste local, usa o certificado já convertido
    cert_file = '/Users/ronnysenna/Projetos/Efi-Certificado/conversor-p12-efi/producao-N8N_new.pem'
else:
    raise Exception("Certificado não encontrado! Configure EFI_CERTIFICATE ou coloque o arquivo .pem no diretório.")

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
    
    # Solicita novo token (endpoint correto do SDK)
    auth_url = f"{BASE_URL}/authorize"  # endpoint correto da API Efí Charges
    
    # Payload correto baseado no SDK
    payload = {"grant_type": "client_credentials"}
    
    try:
        # Autenticação com Basic Auth (como no SDK)
        response = requests.post(
            auth_url,
            auth=(EFI_CLIENT_ID, EFI_CLIENT_SECRET),
            json=payload,  # Usando JSON como no SDK
            timeout=30
        )
        
        print(f"Token request - Status: {response.status_code}")
        print(f"Token request - Headers: {response.headers}")
        print(f"Token request - Content: {response.text[:300]}")
        
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
    except json.JSONDecodeError as e:
        raise Exception(f"Erro ao decodificar JSON do token: {str(e)} - Resposta: {response.text[:200]}")

@app.get("/")
async def root():
    return {"message": "API Efí - Consulta de Boletos", "status": "online"}

@app.get("/debug-token")
async def debug_token():
    """Endpoint para testar obtenção de token"""
    try:
        token = get_access_token()
        return {
            "success": True,
            "token_preview": token[:20] + "..." if token else None,
            "token_cached": token_cache['expires_at'] is not None
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/buscar-boleto/{cpf}")
async def buscar_boleto(cpf: str):
    try:
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido")
        
        # Obtém token de acesso
        token = get_access_token()
        
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        
        # Busca cobrança por documento do cliente
        # Usando o endpoint correto do SDK para listar charges
        params = {
            'charge_type': 'carnet',          # tipo de cobrança
            'customer_document': cpf_limpo,   # documento do cliente
            'begin_date': '2024-11-01',       # último mês para não exceder 1 ano
            'end_date': '2024-11-30',         # data atual
            'limit': 50
        }
        
        response = requests.get(
            f'{BASE_URL}/charges',  # endpoint correto para listar charges
            headers=headers,
            params=params,
            timeout=30
        )
        
        if response.status_code == 401:
            # Token expirado, limpa cache e tenta novamente
            token_cache['token'] = None
            token_cache['expires_at'] = None
            token = get_access_token()
            headers['Authorization'] = f'Bearer {token}'
            
            response = requests.get(
                f'{BASE_URL}/charges',  # endpoint correto
                headers=headers,
                params=params,
                timeout=30
            )
        
        if response.status_code != 200:
            return {
                'cpf': cpf_limpo,
                'erro': f'Status {response.status_code}',
                'mensagem': response.text[:200],  # limita mensagem de erro
                'debug_params': params
            }
        
        try:
            data = response.json()
        except json.JSONDecodeError:
            return {
                'cpf': cpf_limpo,
                'erro': 'Resposta não é JSON válido',
                'content_type': response.headers.get('content-type'),
                'response_preview': response.text[:200]
            }
        
        if not data or 'data' not in data:
            return {
                'cpf': cpf_limpo,
                'total_boletos': 0,
                'boletos': [],
                'mensagem': 'Nenhum boleto encontrado',
                'api_response': data  # debug
            }
        
        # Processa boletos encontrados
        boletos_abertos = []
        for b in data.get('data', []):
            if b.get('status') == 'waiting':
                payment = b.get('payment', {})
                banking_billet = payment.get('banking_billet', {})
                
                boletos_abertos.append({
                    'charge_id': b.get('charge_id'),
                    'valor': f"R$ {b.get('total', 0)/100:.2f}",
                    'vencimento': b.get('expire_at', ''),
                    'status': b.get('status'),
                    'link': banking_billet.get('link', ''),
                    'barcode': banking_billet.get('barcode', ''),
                    'linha_digitavel': banking_billet.get('digitable_line', '')
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

@app.get("/debug-methods")
async def debug_methods():
    """Endpoint para debug - mostra métodos disponíveis"""
    return {
        "endpoints": [
            {"path": "/", "method": "GET", "description": "Status da API"},
            {"path": "/health", "method": "GET", "description": "Health check"},
            {"path": "/debug-token", "method": "GET", "description": "Testa autenticação OAuth2"},
            {"path": "/debug-methods", "method": "GET", "description": "Lista endpoints disponíveis"},
            {"path": "/buscar-boleto/{cpf}", "method": "GET", "description": "Busca boletos por CPF"}
        ],
        "example": {
            "url": "http://localhost:8000/buscar-boleto/12345678901",
            "response": {
                "cpf": "12345678901",
                "total_boletos": 0,
                "boletos": []
            }
        },
        "config": {
            "sandbox": EFI_SANDBOX,
            "base_url": BASE_URL,
            "cert_configured": bool(certificate_content or os.path.exists(cert_file))
        }
    }
