# RAG Chat deployment (private infrastructure)

Runs the public `rag-chat` repository at `https://rag.rangeltech.net` as its own Compose project (`rag-chat`).

- Source: `/opt/rag-chat/src` (clone of the public repo, pinned by commit in `deploy.sh`).
- Index: `/opt/rag-chat/data/index.db`, built from the pinned semantic Parquet files of the PNCP Kaggle release.
- Secrets: `/opt/rag-chat/.env` (model upstream URL and key). Never committed. The browser never sees it.
- Ingress: only the `web` container joins the `public` network; the backend sits on an internal network with it reaches the internet only through the `egress` network for the model upstream.
- The model upstream stays optional: without `QWEN_BASE_URL`, the backend answers in cited extractive mode.
