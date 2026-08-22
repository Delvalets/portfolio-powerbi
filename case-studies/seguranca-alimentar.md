# Estudo de Caso: Monitoramento de Segurança Alimentar (GGSAN)

*[Preencher: seu nome / título profissional]*

---

## 1. Contexto e problema

O monitoramento de Segurança Alimentar (GGSAN) acompanha indicadores de diversos programas e equipamentos sociais — refeições servidas em centros POP, hortas comunitárias, cozinhas solidárias, ações de capacitação e educação alimentar, entre outros.

**Desafios identificados antes da solução:**
- Cada programa era registrado em uma planilha própria, com um **layout "largo"**: uma coluna para cada data (ex: `01/01/2025`, `02/01/2025`...), em vez do formato tabular tradicional — um padrão comum em planilhas preenchidas manualmente ao longo do tempo, mas inutilizável diretamente para análise
- Inconsistência de nomenclatura entre fontes: o mesmo equipamento/instituição aparecia grafado de formas diferentes (ex.: "CENTRO POP NEUZA" vs "CENTRO PÓP NEUZA"), o que fragmentaria qualquer análise se não fosse tratado
- Múltiplos programas de refeição (café da manhã, almoço, lanche, jantar, ceia) viviam em tabelas separadas, sem uma visão unificada do total de refeições servidas
- Formato numérico brasileiro (ponto como separador de milhar) incompatível com conversão direta para tipo numérico

*[Preencher: quem eram os usuários finais desse painel — gestores do GGSAN? Quantas pessoas usavam?]*

---

## 2. Arquitetura da solução

**Fluxo de dados:**

```
Google Sheets (uma planilha por programa/indicador)
        │
        ▼
Script Python (gspread + oauth2client)
        │
        ▼
PostgreSQL — banco SEGURANCA_ALIMENTAR (+ schema monitoramento_ggsan)
        │
        ▼  camada de views (unpivot → padronização → pivot/união)
        ▼
Power BI (dashboard consolidado)
```

**Padrão de modelagem aplicado (reutilizado em ~10 views):**

1. **Unpivot (transposição):** cada tabela-fonte, com uma coluna por data, é transformada em formato longo via `CROSS JOIN LATERAL jsonb_each_text(to_jsonb(tabela.*))`, isolando dinamicamente todas as colunas da linha como pares chave/valor
2. **Filtro de colunas de data:** uma expressão regular (`^\d{2}([_/])\d{2}\1\d{4}$`) identifica quais colunas são datas válidas, ignorando colunas de metadado
3. **Tratamento numérico:** valores no formato brasileiro (ponto como separador de milhar) são normalizados via `regexp_replace` antes da conversão para `numeric`
4. **Repivotamento (quando necessário):** views subsequentes reagrupam os dados unpivotados de volta em formato largo, mas agora com um indicador por coluna, via agregação condicional (`SUM(CASE WHEN indicador = '...' THEN valor END)`), entregando ao Power BI uma tabela já pronta para consumo direto
5. **Padronização/unificação:** para indicadores que precisam ser comparados entre si (ex: refeições servidas em diferentes equipamentos), uma camada final usa `CASE` para mapear múltiplas variações de nome (erros de digitação, acentuação, abreviações) em uma categoria única — e, em alguns casos, `UNION ALL` combina várias tabelas-fonte (6 tipos de refeição) numa única view de fato

*[Preencher: com que frequência o pipeline roda — diário? Sob demanda?]*

---

## 3. Meu papel específico

- Identifiquei o padrão recorrente de planilhas em formato largo (data como coluna) entre múltiplos programas e desenhei uma solução de **unpivot genérica e reutilizável** usando `jsonb_each_text(to_jsonb(...))`, evitando escrever uma view manual para cada nova coluna de data que surgisse
- Apliquei validação via expressão regular para isolar dinamicamente apenas colunas de data válidas, tornando as views resilientes a colunas extras ou fora de padrão
- Tratei inconsistências de formatação numérica (padrão brasileiro) com `regexp_replace`, evitando erros de conversão de tipo
- Construí uma camada de **repivotamento** para apresentar os dados já agregados por indicador ao Power BI, reduzindo a complexidade do modelo no relatório
- Projetei a **padronização de nomenclatura** de instituições/equipamentos com múltiplas variações de escrita (acentuação, abreviação, erro de digitação), consolidando-as em categorias únicas via `CASE`
- Construí a view `vw_refeicoes_unificado`, unindo 6 tabelas-fonte distintas (café da manhã, lanche da manhã, almoço, lanche da tarde, jantar, ceia) em uma única view de fato, com classificação padronizada de equipamento/grupo
- Resolvi (na camada de banco separada do GGSAN) um relacionamento many-to-many de calendário no Power BI através de uma tabela ponte (`DimMes`)

---

## 4. O resultado

> ⚠️ *Print(s) do dashboard aqui — recriado com dados fictícios/sintéticos, mantendo a mesma estrutura visual e os mesmos KPIs do painel real.*

**KPIs principais do painel:**
- Total de refeições servidas por tipo (café da manhã, almoço, lanche, jantar, ceia) e por equipamento
- Indicadores de programas específicos: hortas comunitárias, capacitações/ações socioeducativas, padaria artesanal, Recife Nutre
- *[Preencher: outros KPIs reais do painel — por período? por região/RPA?]*

**Exemplo de insight que o painel permite gerar (genérico, sem dados reais):**
- "É possível comparar a evolução mensal de refeições servidas entre diferentes equipamentos e identificar sazonalidades por tipo de refeição."

---

## 5. Impacto

*[Preencher com termos qualitativos/relativos, sem números sigilosos — ex: "eliminou a necessidade de tratar manualmente colunas de data em cada nova planilha", "unificou X fontes de refeição em uma única visão", "reduziu inconsistências de nomenclatura que antes fragmentavam relatórios"]*

---

## 6. Aprendizados

- Um padrão de transformação bem desenhado (unpivot genérico via JSON) evita reescrever lógica repetidamente conforme novas planilhas/colunas surgem — investir tempo em generalizar a solução compensa a longo prazo
- Padronização de nomenclatura (master data) é frequentemente subestimada, mas é o que garante que análises comparativas façam sentido
- *[Preencher: mais algum aprendizado pessoal seu sobre esse projeto]*

---

**Stack utilizada:** Python (gspread, oauth2client, pg8000), PostgreSQL (JSONB, expressões regulares), Power BI
