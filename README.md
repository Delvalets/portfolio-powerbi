# Portfólio — Sistemas de Dados para Gestão Pública (Power BI + PostgreSQL + Python)

**Tayná do Vale Tavares Silva** — Analista de Dados

Portfólio técnico com dois estudos de caso extraídos do meu trabalho como Analista de Dados no setor público, produzindo pipelines de dados e dashboards Power BI para programas de assistência social e segurança alimentar da cidade do Recife.

> ⚠️ **Sobre os dados**: todos os dados exibidos nos mockups e capturas de tela deste repositório são **fictícios**, gerados para preservar o sigilo dos dados reais da administração pública. A lógica, estrutura de dados e arquitetura técnica são fiéis ao trabalho real.

---

## Visão geral do sistema

O documento Power BI principal consolida dados de **8 bases PostgreSQL** distintas, cobrindo diferentes programas sociais e de segurança alimentar:

| Base | Programa |
|---|---|
| `ACOLHIMENTO` | Acolhimento institucional |
| `BANCO_ALIMENTOS` | Banco de Alimentos (doações + PAA) |
| `CAT_python` | Centro de Atendimento |
| `CENTROPOP_python` | Centro POP / SEAS |
| `CRAS` | Centro de Referência de Assistência Social |
| `CREAS_python` | Centro de Referência Especializado (PAEFI/SEDISF/MSE) |
| `SEGURANCA_ALIMENTAR` | Segurança Alimentar (alimenta também o monitoramento GGSAN) |
| `inclusao_produtiva` | Inclusão Produtiva |

**Pipeline padrão em todo o sistema:**

```
Google Sheets (múltiplas planilhas)
        │
        ▼
Python (gspread + oauth2client) — extração e inferência de tipos
        │
        ▼
PostgreSQL — carga estruturada + camada de views para modelagem analítica
        │
        ▼
Power BI — dashboards consolidados, execução semanal
```

Usuários finais: gestores responsáveis por cada área do programa, com reuniões de análise reunindo os gestores principais — os dados sustentam a análise de resultados dos serviços de assistência social e segurança alimentar oferecidos à população do Recife.

---

## Estudos de caso

### 📦 [Banco de Alimentos](./case-studies/banco-alimentos.md)
Consolidação de doações e compras PAA numa fonte única de "kg arrecadados", com deduplicação de instituições, fill-down de dados de cabeçalho, e resolução de incompatibilidade de autenticação PostgreSQL ↔ Power BI.

**Destaques técnicos**: `MAX() OVER (PARTITION BY)`, `DISTINCT ON` + hash `md5` para deduplicação, `CROSS JOIN LATERAL` para unpivot de categorias.

### 🥗 [Segurança Alimentar / GGSAN](./case-studies/seguranca-alimentar.md)
Padrão de transformação genérica e reutilizável para planilhas em formato "largo" (uma coluna por data), com padronização de nomenclatura de instituições e unificação de múltiplas fontes de refeição numa única view de fato.

**Destaques técnicos**: unpivot via `jsonb_each_text(to_jsonb(...))`, validação por regex, repivotamento com agregação condicional, padronização de master data via `CASE`.

---

## Stack técnica

- **Extração**: Python (`gspread`, `oauth2client`, `psycopg2`)
- **Banco de dados**: PostgreSQL (views, JSONB, expressões regulares, CTEs recursivas)
- **Visualização**: Power BI (DAX, modelagem dimensional, tabela calendário)
- **Automação**: orquestração de scripts Python com execução agendada

---

## Estrutura do repositório

```
├── case-studies/         → documentação detalhada de cada estudo de caso
├── assets/mockups/        → capturas de tela dos dashboards (dados fictícios)
└── scripts/                → scripts de importação sanitizados (sem credenciais)
```

---

## Contato

Tayná do Vale Tavares Silva — Analista de Dados
