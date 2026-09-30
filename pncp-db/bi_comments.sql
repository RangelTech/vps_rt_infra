-- Descriptions the SQL agent reads, so it picks the right table for education-spending questions.
COMMENT ON MATERIALIZED VIEW bi.siope_latest IS 'Education investment per student (SIOPE indicator 57), one row per municipality and year, using the latest reporting period the municipality filed that year. Nominal BRL. Start here for per-student questions.';
COMMENT ON COLUMN bi.siope_latest.codigo_municipio IS 'IBGE 7-digit municipality code (join with ibge.obt_ibge_municipio)';
COMMENT ON COLUMN bi.siope_latest.ano IS 'Year. 2025 is a partial year.';
COMMENT ON COLUMN bi.siope_latest.nome_regiao IS 'Region name (Norte, Nordeste, Sudeste, Sul, Centro-Oeste)';
COMMENT ON COLUMN bi.siope_latest.sigla_uf IS 'State abbreviation';
COMMENT ON COLUMN bi.siope_latest.valor IS 'Education investment per student, nominal BRL';
COMMENT ON MATERIALIZED VIEW bi.siope_invest_year IS 'Median per-student education investment of municipalities, by year (nominal BRL), with the number of municipalities.';
