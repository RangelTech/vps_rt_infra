#!/usr/bin/env bash
# Governanca dos repositorios no GitHub (idempotente). Roda LOCAL com `gh` autenticado como admin. Nao toca a VPS.
#  - protecao da branch main: sem force-push, sem delecao, status check obrigatorio onde existe, PR NAO obrigatorio;
#  - Environment production (vps_rt_infra): so deploya a partir da main;
#  - Actions: allowed_actions=selected, GITHUB_TOKEN somente leitura, aprovacao de colaboradores externos.
set -euo pipefail
export MSYS_NO_PATHCONV=1
ORG=RangelTech
# repo:check (vazio = sem status check obrigatorio). vps_rt_infra fica sem check: o release-intake (bot) faz push direto dos locks. Nomes sao os JOBS do ci.yml de cada repo.
REPOS=("vps_rt_infra:" "kernel-harness:test")
# acoes de terceiros usadas nos workflows (alem das do proprio GitHub)
ALLOWED_PATTERNS=("docker/login-action@*" "hashicorp/setup-terraform@*")

for entry in "${REPOS[@]}"; do
  repo="${entry%%:*}"; check="${entry#*:}"; full="$ORG/$repo"
  echo "==> $full"

  if [ -n "$check" ]; then
    checks="{\"strict\":false,\"contexts\":[\"$check\"]}"
  else
    checks=null
  fi
  gh api -X PUT "repos/$full/branches/main/protection" --input - >/dev/null <<JSON
{"required_status_checks":$checks,"enforce_admins":false,"required_pull_request_reviews":null,"restrictions":null,
 "allow_force_pushes":false,"allow_deletions":false,"required_linear_history":false,"required_conversation_resolution":false}
JSON
  echo "    main: force-push/delecao bloqueados, check=${check:-nenhum}"

  gh api -X PUT "repos/$full/actions/permissions" -F enabled=true -f allowed_actions=selected >/dev/null
  patterns="$(printf '"%s",' "${ALLOWED_PATTERNS[@]}")"; patterns="[${patterns%,}]"
  gh api -X PUT "repos/$full/actions/permissions/selected-actions" --input - >/dev/null <<JSON
{"github_owned_allowed":true,"verified_allowed":false,"patterns_allowed":$patterns}
JSON
  gh api -X PUT "repos/$full/actions/permissions/workflow" -f default_workflow_permissions=read -F can_approve_pull_request_reviews=false >/dev/null
  if gh api -X PUT "repos/$full/actions/permissions/fork-pr-contributor-approval" -f approval_policy=all_external_contributors >/dev/null 2>&1; then
    echo "    actions: selected + token read + aprovacao de externos (all_external_contributors)"
  else
    echo "    actions: selected + token read (endpoint de aprovacao de externos indisponivel)"
  fi
done

# Environment production: somente a main pode implantar
full="$ORG/vps_rt_infra"
gh api -X PUT "repos/$full/environments/production" --input - >/dev/null <<'JSON'
{"deployment_branch_policy":{"protected_branches":false,"custom_branch_policies":true}}
JSON
existing="$(gh api "repos/$full/environments/production/deployment-branch-policies" --jq '.branch_policies[].name')"
for b in $existing; do
  [ "$b" = "main" ] && continue
  id="$(gh api "repos/$full/environments/production/deployment-branch-policies" --jq ".branch_policies[]|select(.name==\"$b\")|.id")"
  gh api -X DELETE "repos/$full/environments/production/deployment-branch-policies/$id" >/dev/null
done
if ! grep -qx main <<<"$existing"; then
  gh api -X POST "repos/$full/environments/production/deployment-branch-policies" -f name=main -f type=branch >/dev/null
fi
echo "==> production: deploy restrito a main"
