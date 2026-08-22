"""
Script de importação: Google Sheets -> PostgreSQL (Banco de Alimentos)

Lê múltiplas abas de uma planilha do Google Sheets, infere o tipo de dado
de cada coluna (TEXT / NUMERIC / DATE), cria ou atualiza a tabela
correspondente no PostgreSQL, e recarrega os dados.

Credenciais e senhas são lidas de variáveis de ambiente / arquivo de
credenciais, nunca hardcoded.
"""

import gspread
import psycopg2
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime
import re
import time
import os

# === CONFIGURAÇÕES ===
credenciais_arquivo = "credenciais.json"  # credenciais de service account do Google

# Conexão PostgreSQL (credenciais via variáveis de ambiente)
conn = psycopg2.connect(
    dbname=os.environ["PGDATABASE"],
    user=os.environ["PGUSER"],
    password=os.environ["PGPASSWORD"],
    host=os.environ.get("PGHOST", "localhost"),
    port=os.environ.get("PGPORT", "5432"),
)
cur = conn.cursor()

# Autorização com Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name(credenciais_arquivo, scope)
client = gspread.authorize(creds)

# Planilhas e abas a importar
planilhas = {
    "DOACOES_RECEBIDAS_ENVIADAS": [
        "BA_ENTRADA_DETALHADA",
        "BA_ENTRADA",
        "BA_DOACOES_ENVIADAS",
        "BA_INSTITUICOES",
        "COZINHAS_SOLIDARIAS",
        "PAA_DOACOES_ENVIADAS",
        "PAA_ENTRADA",
    ]
}

# --------- Regras de tipos por NOME de coluna (normalizado) ----------
FORCE_TEXT = {
    # identificadores/códigos/strings que podem ter dígitos mas NÃO são números
    "cnpj", "cpf", "cep", "telefone", "inscricao_estadual",
    "instituicao", "origem", "municipio", "publico", "area_atuacao",
    "perfil_institucional", "rpa", "lista_itens",
    "n_compra_municipio", "n_compra", "responsavel_entrega",
    # campos livres/observações/status
    "obs", "observacao", "observacoes", "comentario", "comentarios",
    "descricao", "detalhe", "detalhes", "anotacao", "anotacoes", "status",
}
FORCE_DATE = {"data", "data_inicio", "data_fim", "data_envio"}
FORCE_NUMERIC_SUFFIXES = ("_kg", "_qtd", "_quantidade")
FORCE_NUMERIC_EXACT = {
    "usuarios_atendidos", "quantitativo_recebido_kg",
    "quantitativo_descartado_kg", "nao_pereciveis_kg",
    "pereciveis_kg", "kg", "total_entrega_kg", "descarte_interno",
}

# ============================
# HELPERS
# ============================
def limpar_nome(nome: str) -> str:
    """Normaliza nomes para identificadores SQL: minusculo, _, alfanumérico."""
    s = str(nome).strip().lower()
    s = re.sub(r"\s+", "_", s)
    s = re.sub(r"[^\w]", "_", s)
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"^_|_$", "", s)
    s = re.sub(r"[^a-z0-9_]", "", s)
    if s == "":
        s = "coluna"
    return s

def parse_num_br(x):
    """Converte entrada pt-BR para string numérica com ponto decimal (ou None).
       Exemplos: '290,7'->'290.7' | '1.234,56'->'1234.56' | '1 020'->'1020' | '1.020'->'1020'
                 '93%'->'0.93' | '93,5%'->'0.935' | '---'->None | '(1.234,56)'->'-1234.56'
    """
    if x is None:
        return None
    raw = str(x).strip()
    if raw == "":
        return None

    is_percent = "%" in raw

    s = raw.replace("\xa0", "")   # NBSP
    s = s.replace(" ", "")        # espaço como milhar
    s = re.sub(r"[^0-9,.\-\(\)]", "", s)

    if not re.search(r"\d", s):
        return None

    neg = False
    if "(" in s and ")" in s:
        neg = True
        s = s.replace("(", "").replace(")", "")

    if "," in s:
        s = s.replace(".", "")    # ponto milhar
        s = s.replace(",", ".")   # vírgula decimal
    else:
        # padrão milhar 1.234 ou 12.345.678 => remove pontos
        if re.fullmatch(r"-?\d{1,3}(?:\.\d{3})+", s):
            s = s.replace(".", "")

    s = re.sub(r"-+", "-", s)
    if s in {"-", ".", "-.", "-,"}:
        return None

    if is_percent:
        from decimal import Decimal, InvalidOperation
        try:
            s = str(Decimal(s) / Decimal(100))
        except InvalidOperation:
            return None

    return ("-" + s.lstrip("-")) if neg else s

_date_rx = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{4}\s*$")
def eh_data(s):
    if s is None:
        return False
    t = str(s).strip()
    if not _date_rx.match(t):
        return False
    try:
        datetime.strptime(t, "%d/%m/%Y")
        return True
    except Exception:
        return False

def eh_numero(s):
    return parse_num_br(s) is not None

def preferencia_tipo_por_nome(nome_norm: str):
    """Preferência de tipo baseada no nome normalizado da coluna."""
    if nome_norm in FORCE_TEXT:
        return "TEXT"
    if nome_norm in FORCE_DATE or nome_norm.startswith("data_") or nome_norm == "data":
        return "DATE"
    if (nome_norm in FORCE_NUMERIC_EXACT
        or any(nome_norm.endswith(suf) for suf in FORCE_NUMERIC_SUFFIXES)):
        return "NUMERIC"
    return None  # sem preferência

def inferir_tipo_col(amostra_valores, preferencia=None, frac_min=0.6):
    """Infere DATE/NUMERIC/TEXT a partir de uma amostra de valores não vazios."""
    if preferencia:
        return preferencia
    vals = [v for v in amostra_valores if str(v).strip() != ""]
    if not vals:
        return "TEXT"
    n = len(vals)
    d = sum(1 for v in vals if eh_data(v))
    if d / n >= frac_min:
        return "DATE"
    num = sum(1 for v in vals if eh_numero(v))
    if num / n >= frac_min:
        return "NUMERIC"
    return "TEXT"

def tornar_unicos(nomes):
    """Garante unicidade (anexa _2, _3...)."""
    usados = {}
    res = []
    for n in nomes:
        base = n
        k = 1
        out = n
        while out in usados:
            k += 1
            out = f"{base}_{k}"
        usados[out] = True
        res.append(out)
    return res

def escolher_linha_cabecalho(matriz, max_scan=20):
    """Detecta a linha de cabeçalho: primeira com >=2 células não vazias e algum texto (não só números)."""
    limite = min(max_scan, len(matriz))
    for i in range(limite):
        row = matriz[i]
        nonempty = sum(1 for c in row if str(c).strip() != "")
        if nonempty >= 2 and any(re.search(r"[A-Za-zÀ-ÿ]", str(c)) for c in row):
            return i
    # fallback: primeira linha
    return 0

def ler_registros_sheet(aba):
    """Lê toda a planilha, detecta cabeçalho, retorna (dados:list[dict], colunas_norm:list[str])."""
    vals = aba.get_all_values()  # lista de linhas
    if not vals:
        return [], []

    hdr_idx = escolher_linha_cabecalho(vals)
    header_raw = vals[hdr_idx]

    # completa cabeçalhos vazios
    header_raw = [h if str(h).strip() != "" else f"coluna_{i+1}" for i, h in enumerate(header_raw)]
    colunas_norm = tornar_unicos([limpar_nome(h) for h in header_raw])

    data_rows = vals[hdr_idx + 1 :]
    registros = []
    for linha in data_rows:
        # pula linhas totalmente vazias
        if not any(str(c).strip() != "" for c in linha):
            continue
        # pad/truncate para o tamanho do header
        if len(linha) < len(colunas_norm):
            linha = linha + [""] * (len(colunas_norm) - len(linha))
        elif len(linha) > len(colunas_norm):
            linha = linha[: len(colunas_norm)]
        registros.append(dict(zip(colunas_norm, linha)))

    return registros, colunas_norm

# ============================
# LOOP PRINCIPAL
# ============================
for nome_planilha, abas in planilhas.items():
    spreadsheet = client.open(nome_planilha)
    for aba_nome in abas:
        print(f"Importando: {nome_planilha} > {aba_nome}")
        aba = spreadsheet.worksheet(aba_nome)
        time.sleep(1.5)

        dados, colunas_norm = ler_registros_sheet(aba)
        if not dados:
            continue

        # inferência de tipos (considera preferência por nome)
        limite = min(200, len(dados))
        tipos_inferidos = []
        for c_norm in colunas_norm:
            pref = preferencia_tipo_por_nome(c_norm)
            amostra = [dados[i].get(c_norm) for i in range(limite)]
            tipos_inferidos.append(inferir_tipo_col(amostra, pref))

        nome_tabela = limpar_nome(aba_nome)

        # Verificar se a tabela existe
        cur.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema='public' AND table_name = %s
            )
        """, (nome_tabela,))
        existe = cur.fetchone()[0]

        if existe:
            print(f"Tabela {nome_tabela} já existe. Atualizando estrutura e limpando dados...")

            # Colunas existentes
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
            """, (nome_tabela,))
            existentes = {r[0].lower(): r[1].lower() for r in cur.fetchall()}

            # Adicionar colunas faltantes já com o tipo correto
            for col, tipo in zip(colunas_norm, tipos_inferidos):
                if col not in existentes:
                    cur.execute(f'ALTER TABLE "{nome_tabela}" ADD COLUMN "{col}" {tipo}')

            # Limpa a tabela para permitir mudanças de tipo seguras
            cur.execute(f'TRUNCATE TABLE "{nome_tabela}"')

            # Recarrega metadados
            cur.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_schema='public' AND table_name=%s
            """, (nome_tabela,))
            existentes = {r[0].lower(): r[1].lower() for r in cur.fetchall()}

            # Ajusta tipos divergentes (TEXT <-> NUMERIC/DATE e vice-versa)
            for col, tipo in zip(colunas_norm, tipos_inferidos):
                atual = existentes.get(col)
                if atual != tipo.lower():
                    if tipo == "TEXT":
                        cur.execute(
                            f'ALTER TABLE "{nome_tabela}" ALTER COLUMN "{col}" TYPE TEXT USING "{col}"::text'
                        )
                    elif tipo == "NUMERIC":
                        cur.execute(
                            f'ALTER TABLE "{nome_tabela}" ALTER COLUMN "{col}" TYPE NUMERIC USING NULLIF("{col}", \'\')::numeric'
                        )
                    elif tipo == "DATE":
                        cur.execute(f'''
                            ALTER TABLE "{nome_tabela}"
                            ALTER COLUMN "{col}" TYPE DATE
                            USING CASE
                                    WHEN "{col}" ~ '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}}$'
                                      THEN to_date("{col}", 'DD/MM/YYYY')
                                    ELSE NULL
                                  END
                        ''')
        else:
            print(f"Tabela {nome_tabela} não existe. Criando...")
            campos = ", ".join(f'"{col}" {tipo}' for col, tipo in zip(colunas_norm, tipos_inferidos))
            cur.execute(f'CREATE TABLE "{nome_tabela}" ({campos})')

        # Inserir dados
        cols_insert = ", ".join(f'"{c}"' for c in colunas_norm)
        placeholders = ", ".join(["%s"] * len(colunas_norm))

        for linha in dados:
            valores = []
            for c_norm, c_tipo in zip(colunas_norm, tipos_inferidos):
                v = linha.get(c_norm)
                if v == "":
                    v = None
                if v is not None:
                    if c_tipo == "DATE":
                        v = datetime.strptime(str(v).strip(), "%d/%m/%Y").date() if eh_data(v) else None
                    elif c_tipo == "NUMERIC":
                        v = parse_num_br(v)  # string numérica; psycopg2 converte para NUMERIC
                    else:
                        v = str(v)           # TEXT
                valores.append(v)

            cur.execute(
                f'INSERT INTO "{nome_tabela}" ({cols_insert}) VALUES ({placeholders})',
                valores
            )

        conn.commit()

# finalize
cur.close()
conn.close()
print("✅ Todas as planilhas foram importadas com sucesso.")
