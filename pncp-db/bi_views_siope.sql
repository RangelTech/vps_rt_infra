-- Aggregates for the SIOPE dashboard. Indicator 57 is "Investimento educacional por aluno" (nominal BRL per student).
-- The table holds one row per municipality, year and reporting period; each view keeps the latest period a municipality
-- reported in that year, so a municipality counts once per year.
CREATE SCHEMA IF NOT EXISTS bi;
DROP MATERIALIZED VIEW IF EXISTS bi.siope_invest_year, bi.siope_invest_region_2024, bi.siope_invest_uf_2024, bi.siope_reporting_year, bi.siope_latest CASCADE;

CREATE MATERIALIZED VIEW bi.siope_latest AS
  SELECT DISTINCT ON (codigo_municipio, ano) codigo_municipio, ano, nome_regiao, sigla_uf, valor
  FROM siope.obt_fnde_siope_indicador_municipio_ano
  WHERE codigo_indicador = '57' AND esfera = 'Municipal' AND valor > 0
  ORDER BY codigo_municipio, ano, num_periodo DESC;

CREATE MATERIALIZED VIEW bi.siope_invest_year AS
  SELECT ano::text AS year, round((percentile_cont(0.5) WITHIN GROUP (ORDER BY valor))::numeric, 2) AS median_brl_per_student,
         count(*) AS municipalities
  FROM bi.siope_latest GROUP BY ano ORDER BY ano;

CREATE MATERIALIZED VIEW bi.siope_invest_region_2024 AS
  SELECT nome_regiao AS region, round((percentile_cont(0.5) WITHIN GROUP (ORDER BY valor))::numeric, 2) AS median_brl_per_student
  FROM bi.siope_latest WHERE ano = 2024 GROUP BY nome_regiao ORDER BY 2 DESC;

CREATE MATERIALIZED VIEW bi.siope_invest_uf_2024 AS
  SELECT sigla_uf AS uf, round((percentile_cont(0.5) WITHIN GROUP (ORDER BY valor))::numeric, 2) AS median_brl_per_student
  FROM bi.siope_latest WHERE ano = 2024 GROUP BY sigla_uf ORDER BY 2 DESC;

CREATE MATERIALIZED VIEW bi.siope_reporting_year AS
  SELECT ano::text AS year, count(DISTINCT codigo_municipio) AS municipalities_reporting
  FROM siope.obt_fnde_siope_indicador_municipio_ano WHERE esfera = 'Municipal' GROUP BY ano ORDER BY ano;

GRANT USAGE ON SCHEMA bi TO sql_agent, rag_reader, bi_reader, public_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA bi TO sql_agent, bi_reader, public_reader;
