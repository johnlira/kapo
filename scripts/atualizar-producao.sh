#!/usr/bin/env bash
set -euo pipefail

if (( $# > 0 )); then
  printf 'Este script atualiza exclusivamente para a branch producao.\n'
  printf 'Uso: bash ./atualizar-producao.sh\n'
  exit 1
fi

branch="producao"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$project_root/repositorios"
updated=0
ignored=0
failed=0
failures=()

for group in "back" "front" "monolito"; do
  group_dir="$root/$group"

  if [[ ! -d "$group_dir" ]]; then
    printf 'Ignorando %s: pasta nao encontrada.\n' "$group"
    ((ignored+=1))
    continue
  fi

  for project_dir in "$group_dir"/*; do
    [[ -d "$project_dir" ]] || continue

    if [[ ! -d "$project_dir/.git" ]]; then
      printf 'Ignorando %s: nao e um repositorio Git.\n' "${project_dir#$root/}"
      ((ignored+=1))
      continue
    fi

    printf 'Sincronizando %s com origin/%s...\n' "${project_dir#$root/}" "$branch"
    if git -C "$project_dir" fetch origin "$branch" \
      && git -C "$project_dir" reset --hard \
      && git -C "$project_dir" clean -fd \
      && git -C "$project_dir" checkout -B "$branch" "origin/$branch" \
      && git -C "$project_dir" reset --hard "origin/$branch" \
      && git -C "$project_dir" clean -fd; then
      ((updated+=1))
    else
      ((failed+=1))
      failures+=("${project_dir#$root/}")
      printf 'Falha ao sincronizar %s. Continuando nos demais repositorios.\n' "${project_dir#$root/}" >&2
    fi
  done
done

printf '\nResumo da sincronizacao:\n'
printf '  Sincronizados com sucesso: %d\n' "$updated"
printf '  Ignorados: %d\n' "$ignored"
printf '  Com falha: %d\n' "$failed"

if (( failed > 0 )); then
  printf '\nRepositorios com falha:\n' >&2
  for failure in "${failures[@]}"; do
    printf '  - %s\n' "$failure" >&2
  done
  exit 1
fi
