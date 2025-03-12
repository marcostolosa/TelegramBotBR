# 📦 Bot de Pagamentos Mercado Pago para Telegram

## Descrição
Bot desenvolvido em Python para automatizar pagamentos via PIX usando Mercado Pago integrado ao Telegram. Inclui interface web administrativa feita com Streamlit.

## Estrutura do Projeto
```
projeto/
├── bot.py                    # Principal lógica do bot Telegram
├── database_manager.py       # Gerenciamento de banco com SQLAlchemy (novo)
├── payment_manager.py        # Comunicação com API Mercado Pago (melhorias segurança)
├── streamlit_app.py          # Dashboard administrativo (novo)
├── tests/
│   └── test_payments.py      # Testes automatizados com pytest (novo)
├── .env                      # Variáveis sensíveis
├── requirements.txt          # Dependências atualizadas
└── payments.db               # Banco de dados SQLite
```

## Como Rodar o Projeto

### Instalação das Dependências
```bash
pip install -r requirements.txt
```

### Configuração
- Crie o arquivo `.env` com:
```env
MP_ACCESS_TOKEN='seu_token_mercado_pago'
TELEGRAM_BOT_TOKEN='seu_token_telegram'
ADMIN_IDS=123456789
```

### Executar o Bot Telegram
```bash
python bot.py
```

### Executar a Interface Streamlit
```bash
streamlit run streamlit_app.py
```

## Rodar Testes
```bash
pytest tests/
```

## Autor
Criado por [Marcos Tolosa](https://github.com/marcostolosa) - Ethical Hacker, Prompt Engineer e Desenvolvedor Python.
