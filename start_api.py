#!/usr/bin/env python3

import os
from dotenv import load_dotenv

# Carrega variáveis do .env
load_dotenv()

# Importa e executa o app
import uvicorn
from main import app

if __name__ == "__main__":
    print("🚀 Iniciando API Efí Bank - Consulta de Boletos")
    print("💳 Client ID:", os.getenv('EFI_CLIENT_ID')[:20] + "..." if os.getenv('EFI_CLIENT_ID') else "❌ Não configurado")
    print("🏖️  Sandbox:", os.getenv('EFI_SANDBOX', 'False'))
    print("📋 Certificado:", "✅ Configurado" if os.getenv('EFI_CERTIFICATE') else "❌ Não configurado")
    
    uvicorn.run(
        "main:app", 
        host="127.0.0.1", 
        port=8000, 
        reload=True,
        log_level="info"
    )
