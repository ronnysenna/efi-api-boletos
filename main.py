from fastapi import FastAPI, HTTPException
from efipay import EfiPay
import os

app = FastAPI(title="API Consulta Boletos Efí")

# Configuração das credenciais
credentials = {
    'client_id': os.getenv('EFI_CLIENT_ID'),
    'client_secret': os.getenv('EFI_CLIENT_SECRET'),
    'sandbox': os.getenv('EFI_SANDBOX', 'False') == 'True',
    'certificate': '/app/certificado.pem'
}

efi = EfiPay(credentials)

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
        
        # Parâmetros para busca
        params = {
            'charge_type': 'carnet',
            'customer_document': cpf_limpo,
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31'
        }
        
        response = efi.get_charges(params=params)
        
        if not response or 'data' not in response:
            return {
                'cpf': cpf_limpo,
                'total_boletos': 0,
                'boletos': [],
                'mensagem': 'Nenhum boleto encontrado'
            }
        
        # Filtra apenas boletos em aberto
        boletos_abertos = [
            {
                'charge_id': b['charge_id'],
                'valor': f"R$ {b['total']/100:.2f}",
                'vencimento': b['expire_at'],
                'status': b['status'],
                'link': b['payment']['banking_billet']['link'],
                'barcode': b['payment']['banking_billet']['barcode'],
                'pix_copia_cola': b['payment'].get('pix', {}).get('qrcode', '')
            }
            for b in response['data']
            if b['status'] == 'waiting'
        ]
        
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