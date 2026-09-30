-- Small aggregate views the public dashboards read, so a dashboard never scans millions of rows.
-- Run as pncp_owner after the tables load. Refresh with:  REFRESH MATERIALIZED VIEW bi.<name>;
CREATE SCHEMA IF NOT EXISTS bi;

DROP MATERIALIZED VIEW IF EXISTS bi.pncp_notices_by_month, bi.pncp_by_modality, bi.pncp_by_uf, bi.pncp_by_category,
  bi.pncp_value_by_year, bi.pncp_top_organizations, bi.pncp_by_status CASCADE;

CREATE MATERIALIZED VIEW bi.pncp_notices_by_month AS
  SELECT date_trunc('month', data_publicacao_pncp)::date AS month, count(*) AS notices
  FROM pncp.obt_pncp_editais_semantico WHERE data_publicacao_pncp IS NOT NULL GROUP BY 1 ORDER BY 1;

CREATE MATERIALIZED VIEW bi.pncp_by_modality AS
  SELECT coalesce(modalidade_nome, 'Not informed') AS modality, count(*) AS notices
  FROM pncp.obt_pncp_editais_semantico GROUP BY 1 ORDER BY 2 DESC;

CREATE MATERIALIZED VIEW bi.pncp_by_uf AS
  SELECT sigla_uf AS uf, count(*) AS notices, round(sum(valor_total_estimado)::numeric, 2) AS estimated_value_brl
  FROM pncp.obt_pncp_editais_semantico WHERE sigla_uf IS NOT NULL GROUP BY 1 ORDER BY 2 DESC;

CREATE MATERIALIZED VIEW bi.pncp_by_category AS
  SELECT coalesce(categoria_area, 'Not classified') AS category, count(*) AS notices
  FROM pncp.obt_pncp_editais_semantico GROUP BY 1 ORDER BY 2 DESC;

CREATE MATERIALIZED VIEW bi.pncp_value_by_year AS
  SELECT ano_compra AS year, count(*) AS notices, round(sum(valor_total_estimado)::numeric, 2) AS estimated_value_brl
  FROM pncp.obt_pncp_editais_semantico WHERE ano_compra IS NOT NULL GROUP BY 1 ORDER BY 1;

CREATE MATERIALIZED VIEW bi.pncp_top_organizations AS
  SELECT orgao_razao_social AS organization, count(*) AS notices
  FROM pncp.obt_pncp_editais_semantico WHERE orgao_razao_social IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 25;

CREATE MATERIALIZED VIEW bi.pncp_by_status AS
  SELECT coalesce(situacao_compra_nome, 'Not informed') AS status, count(*) AS notices
  FROM pncp.obt_pncp_editais_semantico GROUP BY 1 ORDER BY 2 DESC;

GRANT USAGE ON SCHEMA bi TO sql_agent, rag_reader, bi_reader, public_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA bi TO sql_agent, bi_reader, public_reader;
