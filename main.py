from fastapi import FastAPI, HTTPException
from gerencianet import Gerencianet
import os
import traceback

app = FastAPI(title="API Consulta Boletos Efí")

# Lê o certificado da variável de ambiente e salva em arquivo temporário
certificate_content = os.getenv('EFI_CERTIFICATE')
if not certificate_content:
    raise Exception("Certificado EFI_CERTIFICATE não configurado!")

# Cria arquivo temporário com o certificado
cert_path = '/tmp/certificado.pem'
with open(cert_path, 'w') as f:
    f.write(certificate_content)

# Configura as credenciais
credentials = {
    'client_id': os.getenv('EFI_CLIENT_ID'),
    'client_secret': os.getenv('EFI_CLIENT_SECRET'),
    'sandbox': os.getenv('EFI_SANDBOX', 'False') == 'True',
    'certificate': cert_path
}

gn = Gerencianet(credentials)

@app.get("/")
async def root():
    return {"message": "API Efí - Consulta de Boletos", "status": "online"}

@app.get("/debug-endpoints")
async def debug_endpoints():
    """Mostra os endpoints disponíveis no SDK"""
    try:
        # Acessa os endpoints internos do SDK
        endpoints = gn.endpoints if hasattr(gn, 'endpoints') else {}
        return {
            "available_endpoints": list(endpoints.keys()) if endpoints else "Não foi possível acessar",
            "credentials_ok": True
        }
    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/test-direct-call")
async def test_direct_call():
    """Testa chamada direta via request"""
    try:
        # Monta o endpoint manualmente
        params = {
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31'
        }
        
        # Tenta fazer requisição direta
        response = gn.request(
            endpoint='get_charges',
            params=params,
            method='GET'
        )
        
        return {
            "status": "success",
            "response": response
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/buscar-boleto/{cpf}")
async def buscar_boleto(cpf: str):
    try:
        # Remove caracteres não numéricos do CPF
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido")
        
        # Monta os parâmetros da query string
        params = {
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31',
            'cpf': cpf_limpo
        }
        
        # Chama o endpoint usando o método request
        response = gn.request(
            endpoint='get_charges',
            params=params,
            method='GET'
        )
        
        # Processa a resposta
        if not response or 'data' not in response:
            return {
                'cpf': cpf_limpo,
                'total_boletos': 0,
                'boletos': [],
                'mensagem': 'Nenhum boleto encontrado'
            }
        
        # Filtra boletos em aberto
        boletos_abertos = []
        for b in response.get('data', []):
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
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Erro: {str(e)}\n\nTraceback: {traceback.format_exc()}"
        )

@app.get("/health")
async def health():
    return {"status": "ok", "service": "efi-api"}
