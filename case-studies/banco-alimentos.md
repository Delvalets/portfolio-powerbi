# Estudo de Caso: Dashboard de Gestão — Banco de Alimentos

**Tayná do Vale Tavares Silva** — Analista de Dados

---

## 1. Contexto e problema

O Banco de Alimentos é um programa que recebe doações e realiza compras via PAA (Programa de Aquisição de Alimentos), com dados registrados originalmente em planilhas do Google Sheets alimentadas por diferentes equipes.

**Desafios identificados antes da solução:**
- Dados de doações e de compras PAA viviam em fontes separadas, sem uma visão consolidada de quanto (em kg) havia sido arrecadado no total
- Falta de uma fonte única "confiável" — havia múltiplas tabelas candidatas a serem a fonte autoritativa de determinados dados, exigindo investigação para identificar qual usar
- Atualização manual e sujeita a erro humano, sem automação

Os usuários finais são os gestores responsáveis pela área, com reuniões de análise reunindo cerca de 5 pessoas (gestores principais).

---

## 2. Arquitetura da solução

**Fluxo de dados:**

```
Google Sheets (doações + compras PAA)
        │
        ▼
Script Python (gspread + oauth2client)
        │
        ▼
PostgreSQL — banco BANCO_ALIMENTOS
        │
        ▼
Power BI (dashboard consolidado)
```

**Componentes técnicos principais:**
- Extração automatizada das planilhas via `gspread`, autenticação via `credenciais.json` e `oauth2client`
- Carga estruturada no PostgreSQL, com investigação em pgAdmin para mapear e validar as tabelas-fonte corretas antes de consolidar
- Camada de views SQL responsável por toda a modelagem analítica consumida pelo Power BI, incluindo:

| View | Função |
|---|---|
| `d_data` | Dimensão de data gerada via CTE recursiva (calendário completo 2025–2035), usada para relacionamentos de tempo consistentes no modelo estrela do Power BI |
| `dados_ba_entrada_detalhada` | Transforma uma tabela larga (uma coluna por categoria de alimento) em formato longo via `CROSS JOIN LATERAL`, permitindo análises por categoria sem duplicar lógica no Power BI |
| `todas_instituicoes` | Consolida instituições vindas de duas fontes distintas (cozinhas solidárias e instituições OSC), normalizando texto (espaços, caracteres invisíveis) e deduplicando via `DISTINCT ON` com hash `md5` como chave única |
| `vw_kg_arrecadados` | Unifica doações e compras PAA numa única fonte de "kg arrecadados", com fill-down via `MAX() OVER (PARTITION BY)` para propagar dados de cabeçalho (data, município, responsável) a registros relacionados incompletos |
| `vw_total_enviadas` | Unifica doações enviadas (BA e PAA) em uma única view, tratando inconsistência de formato numérico (vírgula decimal → ponto) antes de somar |

O pipeline é executado semanalmente.

---

## 3. Meu papel específico

- Investiguei o banco de dados em pgAdmin para identificar, entre múltiplas tabelas candidatas, quais eram efetivamente as fontes autoritativas dos dados
- Projetei e implementei uma dimensão de data (`d_data`) via CTE recursiva, garantindo relacionamentos de calendário consistentes e evitando o problema clássico de relacionamento many-to-many entre datas no Power BI
- Modelei uma view de **unpivot** (`dados_ba_entrada_detalhada`) para transformar colunas de categorias de alimento em linhas, tornando o modelo mais flexível para análises por categoria sem lógica adicional no relatório
- Construí uma lógica de **deduplicação e normalização de texto** (`todas_instituicoes`) para consolidar instituições vindas de duas fontes diferentes, tratando inconsistências como espaços duplicados e caracteres invisíveis, e gerando uma chave única via hash `md5`
- Projetei e implementei a view `vw_kg_arrecadados`, que combina doações e compras PAA usando lógica de **fill-down** com `MAX() OVER (PARTITION BY ...)` para propagar valores de cabeçalho a registros relacionados incompletos, além de tratar variações de nome de município (ex: grafias diferentes do mesmo local)
- Construí a view `vw_total_enviadas`, unificando doações enviadas de duas fontes com formatos numéricos inconsistentes (vírgula como separador decimal), tratando isso via `regexp_replace` antes da conversão para numérico
- Resolvi um problema de incompatibilidade de autenticação entre PostgreSQL e Power BI: o banco usava SCRAM-SHA-256, que não era suportado pelo conector do Power BI na configuração existente — a solução foi ajustar o método de autenticação para `md5` no `pg_hba.conf`
- Construí o dashboard final no Power BI a partir dessa base consolidada e modelada

---

## 4. O resultado

![Mockup Banco de Alimentos](../assets/mockups/layout_fundo_banco_alimentos_centralizado.png)

📊 [Baixar o arquivo .pbix](../powerbi/banco_alimentos.pbix)
🐍 [Ver script de importação](../scripts/import_banco_alimentos_sanitized.py)

**KPIs principais do painel:**
- Total de kg arrecadados (doação + PAA), com quebra por período
- *[Preencher: outros KPIs reais do painel — por instituição? por tipo de alimento? por região?]*

**Exemplo de insight que o painel permite gerar (genérico, sem dados reais):**
- "É possível identificar em quais meses a arrecadação via doação supera a via PAA, e vice-versa, apoiando decisões de planejamento de compras."

---

## 5. Impacto

Embora o painel seja usado diretamente por um grupo pequeno de gestores (~5 pessoas), seu impacto é maior do que o número sugere: ele sustenta a análise de resultados dos serviços de assistência social e segurança alimentar oferecidos à população da cidade do Recife, servindo de base para decisões de gestão pública.
---

## 6. Aprendizados

- Identificar a "fonte da verdade" em ambientes com múltiplas tabelas candidatas é um passo tão importante quanto a modelagem em si
- Problemas de infraestrutura (como incompatibilidade de autenticação) fazem parte do trabalho de um pipeline de dados de ponta a ponta, não só a modelagem e o dashboard

---

**Stack utilizada:** Python (gspread, oauth2client, pg8000), PostgreSQL, Power BI
