# Bot de Pagamentos via Mercado Pago para Telegram

Este repositório contém o código-fonte de um bot para o Telegram que integra a API do Mercado Pago para processar pagamentos via PIX. Os usuários podem escolher entre diferentes "packs" (ex.: Pack Básico e Pack Premium), gerar um código PIX para pagamento e verificar o status do pagamento.

## Funcionalidades

- **Criação de Pagamento:**  
  O bot gera um pagamento utilizando a API do Mercado Pago e exibe um código PIX para que o usuário realize o pagamento.

- **Verificação de Status:**  
  Após o pagamento, o usuário pode verificar o status do pagamento. Se aprovado, o bot atualiza o status e informa o usuário.

- **Armazenamento Local:**  
  Os dados dos pagamentos são armazenados em um banco de dados SQLite com modo WAL, garantindo maior concorrência.

- **Interface via Telegram:**  
  Utiliza o [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI) para interagir com os usuários através de comandos e callbacks.

## Pré-requisitos

- Python 3.9 ou superior
- [MercadoPago SDK para Python](https://github.com/mercadopago/sdk-python)
- [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)
- [python-dotenv](https://pypi.org/project/python-dotenv/)

## Instalação

1. **Clone o repositório:**

   ```bash
   git clone https://github.com/marcostolosa/TelegramBotBR.git
   cd TelegramBotBR/
   ```

2. **Crie e ative um ambiente virtual (opcional, mas recomendado):**
   
   ```bash
   python3 -m venv envBot
   source envBot/bin/activate  (No Windows use: envBot\Scripts\activate)
   ```

3. **Instale as dependências:**

   ```bash
   python3 -m pip install -r requirements.txt
   ```

   - **Exemplo de requirements.txt:**

   ```yml
   python-dotenv  
   pyTelegramBotAPI  
   mercadopago
   ```

4. **Configure as variáveis de ambiente:**

Crie um arquivo **.env** na raiz do repositório com o seguinte conteúdo:

   ```ini
   MP_ACCESS_TOKEN='seu_token_do_mercadopago'  
   TELEGRAM_BOT_TOKEN='seu_token_do_telegram' 
   ADMIN_IDS=123456789,987654321 ## id dos usuários admins no Telegram
   ```

## Execução

Para executar o bot, basta rodar:

   ```bash
   python3 -m bot
   ```

O bot iniciará em modo polling e estará pronto para interagir com os usuários.

## Estrutura do Código

- **bot.py:**  
  Contém a implementação completa do bot, incluindo:
  - **DatabaseManager:** Gerencia o acesso ao banco SQLite.
  - **PaymentManager:** Gerencia a criação e verificação de pagamentos via Mercado Pago.
  - **TelegramBotHandler:** Gerencia os handlers do bot do Telegram (comandos, callbacks e middleware).

## Contribuição

Contribuições são bem-vindas! Por favor, abra uma issue ou pull request para discutir alterações ou melhorias.

