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

@app.get("/debug-methods")
async def debug_methods():
    """Lista todos os métodos disponíveis no SDK"""
    try:
        methods = [method for method in dir(gn) if not method.startswith('_')]
        return {
            "available_methods": methods,
            "credentials_configured": True
        }
    except Exception as e:
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }

@app.get("/debug-charges")
async def debug_charges():
    """Testa diferentes formas de chamar a API"""
    results = {}
    
    # Teste 1: Listar charges básico
    try:
        response = gn.get_charges()
        results['test1_basic'] = {"status": "success", "keys": list(response.keys()) if isinstance(response, dict) else type(response).__name__}
    except Exception as e:
        results['test1_basic'] = {"status": "error", "message": str(e)}
    
    # Teste 2: Com parâmetros
    try:
        params = {'begin_date': '2024-01-01', 'end_date': '2025-12-31'}
        response = gn.get_charges(params=params)
        results['test2_with_params'] = {"status": "success", "keys": list(response.keys()) if isinstance(response, dict) else type(response).__name__}
    except Exception as e:
        results['test2_with_params'] = {"status": "error", "message": str(e)}
    
    # Teste 3: Direto com kwargs
    try:
        response = gn.get_charges(begin_date='2024-01-01', end_date='2025-12-31')
        results['test3_kwargs'] = {"status": "success", "keys": list(response.keys()) if isinstance(response, dict) else type(response).__name__}
    except Exception as e:
        results['test3_kwargs'] = {"status": "error", "message": str(e)}
    
    return results

@app.get("/buscar-boleto/{cpf}")
async def buscar_boleto(cpf: str):
    try:
        # Remove caracteres não numéricos do CPF
        cpf_limpo = ''.join(filter(str.isdigit, cpf))
        
        if len(cpf_limpo) != 11:
            raise HTTPException(status_code=400, detail="CPF inválido")
        
        # Parâmetros para busca
        params = {
            'begin_date': '2024-01-01',
            'end_date': '2025-12-31',
            'cpf': cpf_limpo
        }
        
        # Tenta chamar a API
        response = gn.get_charges(params)
        
        return {
            'raw_response': response,
            'cpf': cpf_limpo
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=f"Erro: {str(e)}\n\nTraceback: {traceback.format_exc()}"
        )

@app.get("/health")
async def health():
    return {"status": "ok", "service": "efi-api"}
