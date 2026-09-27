#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
root="$project_root/repositorios"
projects_file="$project_root/scripts/projetos.tsv"

if [[ ! -f "$projects_file" ]]; then
  printf 'Arquivo de projetos nao encontrado: %s\n' "$projects_file" >&2
  exit 1
fi

cloned=0
ignored=0
failed=0
failures=()

while IFS=$'\t' read -r group project url; do
  [[ "$group" == "grupo" ]] && continue
  [[ -z "$group" || -z "$project" || -z "$url" ]] && continue

  group_dir="$root/$group"
  project_dir="$group_dir/$project"

  mkdir -p "$group_dir"

  if [[ -d "$project_dir/.git" ]]; then
    printf 'Ignorando %s/%s: pasta ja existe.\n' "$group" "$project"
    ((ignored+=1))
    continue
  fi

  # Um clone interrompido pode deixar uma pasta vazia no destino.
  if [[ -e "$project_dir" ]]; then
    if ! rmdir "$project_dir" 2>/dev/null; then
      printf 'Falha ao clonar %s/%s: destino ja existe e nao e um repositorio Git.\n' "$group" "$project" >&2
      ((failed+=1))
      failures+=("$group/$project")
      continue
    fi
  fi

  printf 'Clonando %s/%s...\n' "$group" "$project"
  if git clone "$url" "$project_dir"; then
    ((cloned+=1))
  else
    ((failed+=1))
    failures+=("$group/$project")
    printf 'Falha ao clonar %s/%s. Continuando nos demais repositorios.\n' "$group" "$project" >&2
  fi
done < "$projects_file"

printf '\nResumo da clonagem:\n'
printf '  Clonados com sucesso: %d\n' "$cloned"
printf '  Ignorados: %d\n' "$ignored"
printf '  Com falha: %d\n' "$failed"

if (( failed > 0 )); then
  printf '\nRepositorios com falha:\n' >&2
  for failure in "${failures[@]}"; do
    printf '  - %s\n' "$failure" >&2
  done
  exit 1
fi
