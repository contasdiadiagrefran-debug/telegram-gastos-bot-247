import time
import requests
import json
import os
import re
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Servidor HTTP simples para o Health Check do Render Web Service (Free Tier)
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK - Bot Gastos 24/7 Ativo")

    def log_message(self, format, *args):
        return

def start_health_server():
    try:
        port = int(os.environ.get("PORT", 10000))
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        server.serve_forever()
    except Exception as e:
        print(f"[WARN HEALTH SERVER]: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

TELEGRAM_TOKEN = "8598409500:AAFQrj1Igkm1c5VwvFi3qvHeKqwTqu5w3io"
SHEETS_URL = "https://script.google.com/macros/s/AKfycbx_1MVLegN4fwaxS4bBLVq0u50DkF-BoFRC1qFB-uKyVJA4Df76H1sAvV6tJPlcd0KP/exec"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
GASTOS_FILE = os.path.join(BASE_DIR, "gastos_247.json")

PROCESSED_UPDATES = set()
RECENT_MESSAGES_CACHE = {}

CATEGORIA_KEYWORDS = {
    "Alimentação": ["almoço", "almoco", "jantar", "lanche", "restaurante", "mercado", "supermercado", "padaria", "comida", "ifood", "rappi", "pizza", "hamburguer", "açaí", "acai", "feira", "açougue", "acougue", "hortifruti", "mcdonalds", "outback", "sorvete", "doce", "cafe", "café", "pao", "pão", "churrasco"],
    "Transporte": ["uber", "99", "taxi", "gasolina", "combustivel", "combustível", "estacionamento", "pedagio", "pedágio", "mecanico", "mecânico", "lavagem", "postocombustivel", "metrô", "metro", "ônibus", "onibus", "abastecimento", "abastecer", "posto", "etanol", "diesel", "gnv", "troca de oleo", "troca de óleo", "pneu", "alinhamento", "balanceamento"],
    "Saúde & Farmácia": ["farmacia", "farmácia", "remedio", "remédio", "drogaria", "consulta", "exame", "dentista", "hospital", "psicologo", "laboratorio", "medico", "médico", "drogasil", "drogaraia", "pague menos"],
    "Lazer & Pessoal": ["cinema", "bar", "cerveja", "chope", "chopp", "shopping", "roupa", "calcado", "calçado", "salao", "salão", "barbeiro", "cabeleireiro", "perfume", "ingresso", "festa", "presente", "jogo", "viagem", "hotel"],
    "Moradia & Casa": ["casa", "reparo", "ferragem", "decoração", "decoracao", "limpeza", "utensilio", "utensílio", "jardim", "moveis", "móveis", "leroy", "material construcao"],
    "Serviços & Assinaturas": ["netflix", "spotify", "prime", "amazon", "youtube", "cursinho", "internet", "recarga", "celular", "plano", "anuidade", "ipva", "iptu", "seguro"]
}

CATEGORIA_EMOJIS = {
    "Alimentação": "🍔",
    "Transporte": "🚗",
    "Saúde & Farmácia": "💊",
    "Lazer & Pessoal": "🎉",
    "Moradia & Casa": "🏠",
    "Serviços & Assinaturas": "📱",
    "Outros / Diversos": "📌"
}

def load_gastos():
    if os.path.exists(GASTOS_FILE):
        try:
            with open(GASTOS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_gasto_local(expense):
    gastos = load_gastos()
    for g in gastos:
        if g.get("id") == expense.get("id"):
            return
    gastos.append(expense)
    try:
        with open(GASTOS_FILE, "w", encoding="utf-8") as f:
            json.dump(gastos, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[ERRO SALVAR JSON LOCAL]: {e}")

def parse_expense(text, message_id=None):
    if not text or not text.strip():
        return None

    clean_text = text.strip()
    match_val = re.search(r'(?:R\$\s*)?(\d+(?:[.,]\d{1,2})?)', clean_text, re.IGNORECASE)
    if not match_val:
        return None

    val_str = match_val.group(1).replace(',', '.')
    try:
        valor = float(val_str)
    except ValueError:
        return None

    descricao = clean_text.replace(match_val.group(0), '').strip()
    descricao = re.sub(r'^\s*[-:]\s*', '', descricao).strip()
    if not descricao:
        descricao = "Gasto Diversos"

    desc_lower = descricao.lower()
    categoria = "Outros / Diversos"
    for cat, keywords in CATEGORIA_KEYWORDS.items():
        for kw in keywords:
            if kw in desc_lower:
                categoria = cat
                break
        if categoria != "Outros / Diversos":
            break

    agora = datetime.datetime.now()
    exp_id = message_id if message_id else int(agora.timestamp() * 1000)
    
    return {
        "id": exp_id,
        "data_hora": agora.strftime("%d/%m/%Y %H:%M:%S"),
        "data_curta": agora.strftime("%d/%m/%Y"),
        "hora_curta": agora.strftime("%H:%M"),
        "mes_ref": agora.strftime("%Y-%m"),
        "descricao": descricao.capitalize(),
        "categoria": categoria,
        "valor": valor,
        "canal": "Telegram Nuvem 24/7"
    }

def post_to_google_sheets(expense):
    try:
        r = requests.post(SHEETS_URL, json=expense, timeout=10, allow_redirects=False)
        return r.status_code in [200, 302]
    except Exception as e:
        print(f"[ERRO GOOGLE SHEETS]: {e}")
        return False

def send_telegram(token, chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        requests.post(url, json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}, timeout=5)
    except Exception as e:
        print(f"[ERRO TELEGRAM SEND]: {e}")

def format_valor(val):
    return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def gerar_resumo_do_dia():
    hoje_str = datetime.datetime.now().strftime("%d/%m/%Y")
    gastos = load_gastos()
    gastos_hoje = [g for g in gastos if g.get("data_curta") == hoje_str]
    
    if not gastos_hoje:
        return (
            f"📊 *RESUMO DE GASTOS DO DIA ({hoje_str})*\n\n"
            "Nenhum gasto foi registrado hoje ainda!\n\n"
            "💡 *Para registrar um gasto, envie por exemplo:*\n"
            "• `35 almoço`\n"
            "• `70 gasolina`\n"
            "• `18.50 uber`"
        )
    
    total_dia = sum(g["valor"] for g in gastos_hoje)
    por_categoria = {}
    for g in gastos_hoje:
        cat = g.get("categoria", "Outros / Diversos")
        por_categoria[cat] = por_categoria.get(cat, 0.0) + g["valor"]
    
    msg_lines = [
        f"📊 *RESUMO DE GASTOS DO DIA ({hoje_str})*",
        "",
        f"📋 *Lançamentos de Hoje ({len(gastos_hoje)} itens):*"
    ]
    
    for g in gastos_hoje:
        hora = g.get("hora_curta", "")
        desc = g.get("descricao", "Gasto")
        val = format_valor(g["valor"])
        cat = g.get("categoria", "Outros")
        emoji = CATEGORIA_EMOJIS.get(cat, "📌")
        msg_lines.append(f"• `{hora}` {emoji} *{desc}*: {val} _({cat})_")
        
    msg_lines.append("")
    msg_lines.append("🏷️ *Total por Categoria:*")
    for cat, val in por_categoria.items():
        emoji = CATEGORIA_EMOJIS.get(cat, "📌")
        msg_lines.append(f"• {emoji} *{cat}*: {format_valor(val)}")
        
    msg_lines.append("")
    msg_lines.append(f"💰 *TOTAL GERAL DO DIA:* *{format_valor(total_dia)}*")
    
    return "\n".join(msg_lines)

def run_bot():
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
    
    print("==================================================")
    print("   ROBÔ TELEGRAM NUVEM 24/7 (GASTOS E PLANILHA)  ")
    print("==================================================")
    
    try:
        requests.get(f"{telegram_url}/deleteWebhook?drop_pending_updates=True", timeout=5)
    except Exception:
        pass

    offset = None
    try:
        r = requests.get(f"{telegram_url}/getUpdates?offset=-1", timeout=5)
        if r.status_code == 200 and r.json().get("ok"):
            res = r.json().get("result", [])
            if res:
                offset = res[-1]["update_id"] + 1
    except Exception:
        pass

    while True:
        try:
            url = f"{telegram_url}/getUpdates?timeout=10"
            if offset:
                url += f"&offset={offset}"

            resp = requests.get(url, timeout=15)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    for update in data.get("result", []):
                        update_id = update["update_id"]
                        offset = update_id + 1

                        if update_id in PROCESSED_UPDATES:
                            continue
                        PROCESSED_UPDATES.add(update_id)

                        msg = update.get("message") or update.get("edited_message")
                        if not msg:
                            continue

                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "").strip()
                        sender = msg.get("from", {}).get("first_name", "Usuário")
                        msg_id = msg.get("message_id")

                        if not text:
                            continue

                        now_ts = time.time()
                        cache_key = (chat_id, text)
                        if cache_key in RECENT_MESSAGES_CACHE:
                            if now_ts - RECENT_MESSAGES_CACHE[cache_key] < 5:
                                print(f"[IGNORADO DUPLICADO POR TEMPO]: '{text}' de {sender}")
                                continue
                        RECENT_MESSAGES_CACHE[cache_key] = now_ts

                        text_lower = text.lower()

                        if text_lower in ["/start", "/help", "ajuda", "inicio", "início"]:
                            send_telegram(
                                TELEGRAM_TOKEN,
                                chat_id,
                                f"👋 Olá, *{sender}*!\n\n"
                                "Eu sou o seu **Assistente de Gastos Diários 24/7 (Nuvem)**!\n\n"
                                "💬 **Como enviar gastos:**\n"
                                "Basta digitar o valor e o item:\n"
                                "• `35 almoço`\n"
                                "• `70 gasolina`\n"
                                "• `18.50 uber`\n"
                                "• `120 farmácia`\n\n"
                                "📊 **Comandos de Resumo:**\n"
                                "Digite `/resumo` ou `resumo` a qualquer momento para ver o relatório de hoje!"
                            )
                            continue

                        if text_lower in ["/resumo", "resumo", "resumo do dia", "resumo dia", "relatorio", "relatório"]:
                            resumo_msg = gerar_resumo_do_dia()
                            send_telegram(TELEGRAM_TOKEN, chat_id, resumo_msg)
                            continue

                        print(f"[NOVO GASTO {msg_id} DE {sender}]: '{text}'")
                        expense = parse_expense(text, message_id=msg_id)
                        if expense:
                            save_gasto_local(expense)
                            synced = post_to_google_sheets(expense)
                            val_fmt = format_valor(expense['valor'])
                            
                            reply_msg = (
                                f"✅ *Gasto Anotado com Sucesso! (24/7 Nuvem)*\n\n"
                                f"📌 **Item:** {expense['descricao']}\n"
                                f"🏷️ **Categoria:** {expense['categoria']}\n"
                                f"💵 **Valor:** {val_fmt}\n"
                                f"📅 **Data:** {expense['data_hora']}\n"
                            )
                            if synced:
                                reply_msg += "\n☁️ *Sincronizado na nova planilha do Google Sheets!*"
                            else:
                                reply_msg += "\n⚠️ *(Salvo localmente)*"

                            send_telegram(TELEGRAM_TOKEN, chat_id, reply_msg)
                        else:
                            send_telegram(
                                TELEGRAM_TOKEN,
                                chat_id,
                                "💡 Não consegui entender o valor. Envie no formato: `35 almoço` ou `70.50 gasolina`.\n\n"
                                "Ou envie `resumo` para ver os gastos de hoje!"
                            )
        except Exception as err:
            print(f"[ERRO POLLING]: {err}")

        time.sleep(1)

if __name__ == "__main__":
    run_bot()
