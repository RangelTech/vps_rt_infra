# portfolio-feedback

Comments, likes and dislikes for the articles at `https://lucas.rangeltech.net/articles/<slug>/`, served under
`/api/feedback` on the same host as the static site.

- No accounts. A comment takes a name and a text; a vote takes a random voter id the browser keeps.
- Only articles that exist in the published site accept feedback (the site is mounted read only).
- Abuse controls: length limits, a honeypot field, at most two links per comment, six comments and forty votes per IP per ten
  minutes (IPs kept only as salted hashes in memory), a Traefik rate limit, one vote per voter per article.
- Moderation: `curl -X DELETE -H "X-Admin-Token: $TOKEN" https://lucas.rangeltech.net/api/feedback/comments/<id>`.

Deploy on the VPS:

```bash
sudo mkdir -p /opt/portfolio-feedback/{src,data} && sudo chown 10001:10001 /opt/portfolio-feedback/data
# copy this folder to /opt/portfolio-feedback/src; write FEEDBACK_ADMIN_TOKEN=<random> to /opt/portfolio-feedback/.env (chmod 600)
docker compose -f /opt/portfolio-feedback/src/docker-compose.yml up -d --build
```

Backup: the SQLite file in `/opt/portfolio-feedback/data`.
