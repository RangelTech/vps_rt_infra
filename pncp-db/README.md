# PNCP public database (private infrastructure)

One Postgres for the public PNCP tables. RAG Chat searches it (full-text), Metabase charts it, and `public_reader` lets visitors query it read-only through pgAdmin. Roles: `rag_reader`, `bi_reader`, `public_reader` (SELECT only, statement timeouts, connection limits). Data comes from the verified Parquet files of the Kaggle catalogue; very large raw tables stay in Kaggle only.
