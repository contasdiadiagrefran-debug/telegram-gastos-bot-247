import time
import requests
import json
import os
import re
import datetime
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# Servidor HTTP simples para o Health Check do Render Web Service
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
        print(f"[HEALTH CHECK SERVER] Rodando na porta {port}")
        server.serve_forever()
    except Exception as e:
        print(f"[WARN HEALTH SERVER]: {e}")

threading.Thread(target=start_health_server, daemon=True).start()

TELEGRAM_TOKEN = "8598409500:AAFQrj1Igkm1c5VwvFi3qvHeKqwTqu5w3io"
SHEETS_URL = "https://script.google.com/macros/s/AKfycbx_1MVLegN4fwaxS4bBLVq0u50DkF-BoFRC1qFB-uKyVJA4Df76H1sAvV6tJPlcd0KP/exec"

# Armazenamento em memória (Ultra-Rápido e 100% Estável no Render)
GASTOS_MEMORIA = []
PROCESSED_UPDATES = set()
PROCESSED_MESSAGES = set()

def get_now_br():
    tz_br = datetime.timezone(datetime.timedelta(hours=-3))
    return datetime.datetime.now(tz=tz_br)

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

    agora = get_now_br()
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

def post_to_google_sheets_async(expense):
    def _worker():
        try:
            requests.post(SHEETS_URL, json=expense, timeout=10, allow_redirects=False)
            print(f"[OK ASYNC SHEETS]: {expense['descricao']}")
        except Exception as e:
            print(f"[ERRO SHEETS ASYNC]: {e}")
            
    threading.Thread(target=_worker, daemon=True).start()

def send_telegram(token, chat_id, text, parse_mode="HTML"):
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text}
        if parse_mode:
            payload["parse_mode"] = parse_mode
        requests.post(url, json=payload, timeout=8)
    except Exception as e:
        print(f"[ERRO TELEGRAM SEND]: {e}")

def format_valor(val):
    return f"R$ {val:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def gerar_resumo_do_dia():
    hoje_str = get_now_br().strftime("%d/%m/%Y")
    gastos_hoje = [g for g in GASTOS_MEMORIA if g.get("data_curta") == hoje_str]
    
    if not gastos_hoje:
        return (
            f"📊 <b>RESUMO DE GASTOS DO DIA ({hoje_str})</b>\n\n"
            "Nenhum gasto foi registrado hoje ainda nesta sessão!\n\n"
            "💡 <b>Para registrar um gasto, envie por exemplo:</b>\n"
            "• <code>35 almoço</code>\n"
            "• <code>70 gasolina</code>\n"
            "• <code>18.50 uber</code>"
        )
    
    total_dia = sum(g["valor"] for g in gastos_hoje)
    por_categoria = {}
    for g in gastos_hoje:
        cat = g.get("categoria", "Outros / Diversos")
        por_categoria[cat] = por_categoria.get(cat, 0.0) + g["valor"]
    
    msg_lines = [
        f"📊 <b>RESUMO DE GASTOS DO DIA ({hoje_str})</b>",
        "",
        f"📋 <b>Lançamentos de Hoje ({len(gastos_hoje)} itens):</b>"
    ]
    
    for g in gastos_hoje:
        hora = g.get("hora_curta", "")
        desc = g.get("descricao", "Gasto")
        val = format_valor(g["valor"])
        cat = g.get("categoria", "Outros")
        emoji = CATEGORIA_EMOJIS.get(cat, "📌")
        msg_lines.append(f"• <code>{hora}</code> {emoji} <b>{desc}</b>: {val} <i>({cat})</i>")
        
    msg_lines.append("")
    msg_lines.append("🏷️ <b>Total por Categoria:</b>")
    for cat, val in por_categoria.items():
        emoji = CATEGORIA_EMOJIS.get(cat, "📌")
        msg_lines.append(f"• {emoji} <b>{cat}</b>: {format_valor(val)}")
        
    msg_lines.append("")
    msg_lines.append(f"💰 <b>TOTAL GERAL DO DIA:</b> <b>{format_valor(total_dia)}</b>")
    
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

    while True:
        try:
            url = f"{telegram_url}/getUpdates?timeout=20"
            if offset:
                url += f"&offset={offset}"

            resp = requests.get(url, timeout=25)
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

                        msg_id = msg.get("message_id")
                        if msg_id in PROCESSED_MESSAGES:
                            continue
                        PROCESSED_MESSAGES.add(msg_id)

                        chat_id = msg["chat"]["id"]
                        text = msg.get("text", "").strip()
                        sender = msg.get("from", {}).get("first_name", "Usuário")

                        if not text:
                            continue

                        text_lower = text.lower()

                        if text_lower in ["/start", "/help", "ajuda", "inicio", "início"]:
                            send_telegram(
                                TELEGRAM_TOKEN,
                                chat_id,
                                f"👋 Olá, <b>{sender}</b>!\n\n"
                                "Eu sou o seu <b>Assistente de Gastos Diários 24/7 (Nuvem)</b>!\n\n"
                                "💬 <b>Como enviar gastos:</b>\n"
                                "Basta digitar o valor e o item:\n"
                                "• <code>35 almoço</code>\n"
                                "• <code>70 gasolina</code>\n"
                                "• <code>18.50 uber</code>\n"
                                "• <code>120 farmácia</code>\n\n"
                                "📊 <b>Comandos de Resumo:</b>\n"
                                "Digite <code>/resumo</code> ou <code>resumo</code> a qualquer momento para ver o relatório de hoje!"
                            )
                            continue

                        if text_lower in ["/resumo", "resumo", "resumo do dia", "resumo dia", "relatorio", "relatório"]:
                            resumo_msg = gerar_resumo_do_dia()
                            send_telegram(TELEGRAM_TOKEN, chat_id, resumo_msg)
                            continue

                        print(f"[NOVO GASTO {msg_id} DE {sender}]: '{text}'")
                        expense = parse_expense(text, message_id=msg_id)
                        if expense:
                            GASTOS_MEMORIA.append(expense)
                            post_to_google_sheets_async(expense)
                            
                            val_fmt = format_valor(expense['valor'])
                            reply_msg = (
                                f"✅ <b>Gasto Anotado com Sucesso! (24/7 Nuvem)</b>\n\n"
                                f"📌 <b>Item:</b> {expense['descricao']}\n"
                                f"🏷️ <b>Categoria:</b> {expense['categoria']}\n"
                                f"💵 <b>Valor:</b> {val_fmt}\n"
                                f"📅 <b>Data:</b> {expense['data_hora']}\n\n"
                                f"☁️ <i>Sincronizando no Google Sheets...</i>"
                            )

                            send_telegram(TELEGRAM_TOKEN, chat_id, reply_msg)
                        else:
                            send_telegram(
                                TELEGRAM_TOKEN,
                                chat_id,
                                "💡 Não consegui entender o valor. Envie no formato: <code>35 almoço</code> ou <code>70.50 gasolina</code>.\n\n"
                                "Ou envie <code>resumo</code> para ver os gastos de hoje!"
                            )
            elif resp.status_code == 409:
                print("[WARN] Conflito de Polling. Aguardando 5s...")
                time.sleep(5)
        except Exception as err:
            print(f"[ERRO POLLING]: {err}")
            time.sleep(2)

        time.sleep(0.5)

if __name__ == "__main__":
    run_bot()
