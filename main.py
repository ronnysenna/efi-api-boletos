from fastapi import FastAPI, HTTPException
from gerencianet import Gerencianet
import os

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

@app.get("/buscar-boleto/{cpf}")
async def buscar_boleto(cpf: str):
    try:
        # Remove caracteres não numéricos do CPF
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido")
        
        # Parâmetros para busca na API v1
        params = {
            'charge_type': 'carnet',
            'cpf': cpf_limpo,
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31'
        }
        
        # Chama o endpoint correto da API v1
        response = gn.get_charges(params=params)
        
        if not response or 'data' not in response:
            return {
                'cpf': cpf_limpo,
                'total_boletos': 0,
                'boletos': [],
                'mensagem': 'Nenhum boleto encontrado'
            }
        
        # Processa os boletos retornados
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
        raise HTTPException(status_code=500, detail=f"Erro ao consultar: {str(e)}")

@app.get("/health")
async def health():
    return {"status": "ok", "service": "efi-api"}
