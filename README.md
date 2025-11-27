# API Consulta Boletos Efí

API FastAPI para consultar boletos/carnês da Efí Bank por CPF.

## Endpoints

- `GET /` - Status da API
- `GET /buscar-boleto/{cpf}` - Busca boletos por CPF
- `GET /health` - Health check

## Deploy

1. Configure as variáveis de ambiente no EasyPanel
2. Faça upload do certificado.pem
3. Deploy via GitHub
