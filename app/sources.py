"""Busca funcionalidades e consulta os repositórios locais."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re
import unicodedata


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORIES_ROOT = (PROJECT_ROOT / "repositorios").resolve()
CATALOG_PATH = (PROJECT_ROOT / "scripts/projetos.tsv").resolve()
FUNCTIONALITY_CATALOG_PATH = PROJECT_ROOT / "data/funcionalidades.json"

SKIP_DIRECTORIES = {
    ".git",
    ".github",
    ".secrets",
    ".ssh",
    ".venv",
    ".gradle",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
PRIVATE_FILE_NAMES = {
    ".env", ".npmrc", ".pypirc", ".netrc", ".gitconfig",
    "credentials", "credentials.json", "secrets.json", "service-account.json",
    "id_rsa", "id_ed25519", "authorized_keys",
}
PRIVATE_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".jks", ".keystore", ".sqlite", ".db"}
STACK_MARKERS = {
    "package.json": "Node.js",
    "build.gradle": "Gradle/JVM",
    "build.gradle.kts": "Gradle/Kotlin DSL",
    "pom.xml": "Maven/JVM",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
}
MAX_SEARCH_RESULTS = 10
MAX_SEARCH_RESULT_BYTES = 24_000
MAX_READ_FILES = 5
MAX_READ_FILE_BYTES = 12_000
MAX_READ_TOTAL_BYTES = 32_000
SEARCH_STOPWORDS = {
    "a", "as", "o", "os", "de", "do", "da", "dos", "das", "no", "na", "nos",
    "nas", "em", "para", "por", "e", "ou", "pre", "pago",
}

def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _allowed_source(path: Path, project: Path) -> bool:
    """Evita enviar credenciais e dados locais ao modelo por ferramentas de busca/leitura."""
    if path.is_symlink() or not _within(path, project) or not _within(path, REPOSITORIES_ROOT):
        return False
    relative = path.relative_to(project)
    if any(part.casefold() in SKIP_DIRECTORIES for part in relative.parts[:-1]):
        return False
    name = path.name.casefold()
    return not (
        name in PRIVATE_FILE_NAMES
        or name.startswith(".env.")
        or name.startswith("id_rsa")
        or name.startswith("id_ed25519")
        or path.suffix.casefold() in PRIVATE_SUFFIXES
    )


def _safe_directories(root: Path, *, depth: int | None = None):
    """Percorre diretórios locais sem seguir links simbólicos."""
    if root.is_symlink() or not root.is_dir():
        return
    for directory, subdirectories, filenames in os.walk(root, followlinks=False):
        current = Path(directory)
        if current.is_symlink() or not _within(current, root):
            subdirectories.clear()
            continue
        subdirectories[:] = [
            name
            for name in subdirectories
            if not Path(directory, name).is_symlink()
            and _within(Path(directory, name), root)
        ]
        if depth is not None and len(current.relative_to(root).parts) >= depth:
            subdirectories.clear()
        yield current, subdirectories, filenames


def _project_directories() -> dict[str, Path]:
    projects: dict[str, Path] = {}
    if REPOSITORIES_ROOT.is_symlink() or not REPOSITORIES_ROOT.is_dir():
        return projects
    for category in REPOSITORIES_ROOT.iterdir():
        if category.is_symlink() or not category.is_dir() or not _within(category, REPOSITORIES_ROOT):
            continue
        for project in category.iterdir():
            if project.is_dir() and not project.is_symlink() and _within(project, REPOSITORIES_ROOT):
                projects[f"{category.name}/{project.name}"] = project
    return projects


def _project_path(project_name: str) -> Path | None:
    """Resolve nome de clone sem seguir links para fora da árvore permitida."""
    available = _project_directories()
    if "/" in project_name or "\\" in project_name:
        return available.get(project_name)
    matches = [path for path in available.values() if path.name == project_name]
    return matches[0] if len(matches) == 1 else None


def _project_options(project_name: str) -> list[str]:
    if "/" in project_name or "\\" in project_name:
        return []
    matches = sorted(name for name in _project_directories() if name.endswith(f"/{project_name}"))
    return matches if len(matches) > 1 else []


def _missing_project(project_name: str, **fields) -> str:
    options = _project_options(project_name)
    return json.dumps(
        {"projeto": project_name,
         "estado": "nome ambíguo; informe grupo/projeto" if options else "ausente localmente ou nome não encontrado",
         **fields, "opcoes": options},
        ensure_ascii=False,
    )


def _stack(project: Path) -> str:
    found: list[str] = []
    for directory, subdirectories, filenames in _safe_directories(project):
        subdirectories[:] = [
            name
            for name in subdirectories
            if name not in SKIP_DIRECTORIES
        ]
        for marker, stack in STACK_MARKERS.items():
            if marker in filenames and stack not in found:
                found.append(stack)
        if "settings.gradle" in filenames and "Gradle multi-project" not in found:
            found.append("Gradle multi-project")
        if "settings.gradle.kts" in filenames and "Gradle Kotlin multi-project" not in found:
            found.append("Gradle Kotlin multi-project")
        if "grails-app" in subdirectories and "Grails" not in found:
            found.append("Grails")
    return ", ".join(found) if found else "stack não identificado"


def _catalog() -> list[dict[str, str]]:
    if not CATALOG_PATH.is_file() or not _within(CATALOG_PATH, PROJECT_ROOT):
        return []
    with CATALOG_PATH.open(encoding="utf-8", newline="") as catalog_file:
        return list(csv.DictReader(catalog_file, delimiter="\t"))


def catalog_repositories() -> str:
    """Lista o catálogo operacional e confere existência/stack nos clones locais."""
    available = _project_directories()
    rows = []
    catalog_rows = _catalog()
    catalog_names: set[str] = set()
    for entry in catalog_rows:
        name = entry.get("nome", "")
        key = f"{entry.get('grupo', '')}/{name}"
        catalog_names.add(key)
        project = available.get(key)
        rows.append(
            {
                "grupo_catalogado": entry.get("grupo", ""),
                "projeto": name,
                "clone": "disponível" if project else "ausente localmente",
                "diretorio_real": (
                    project.relative_to(PROJECT_ROOT).as_posix() if project else None
                ),
                "stack_detectada": _stack(project) if project else None,
            }
        )
    for key, project in sorted(available.items()):
        if key not in catalog_names:
            rows.append(
                {
                    "grupo_catalogado": project.parent.name,
                    "projeto": project.name,
                    "clone": "disponível, não catalogado",
                    "diretorio_real": project.relative_to(PROJECT_ROOT).as_posix(),
                    "stack_detectada": _stack(project),
                }
            )
    return json.dumps(
        {"total_catalogados": len(catalog_rows), "total_clones_locais": len(available), "projetos": rows},
        ensure_ascii=False,
        indent=2,
    )


def search_repository_files(project_name: str, terms: str) -> str:
    """Busca termos em nomes/conteúdo e retorna trechos para validar pertinência."""
    project = _project_path(project_name)
    if project is None:
        return _missing_project(project_name, resultados=[])

    phrases = (
        [phrase.strip().casefold() for phrase in terms.split("|") if phrase.strip()]
        if "|" in terms
        else []
    )
    hyphenated = (
        []
        if phrases
        else list(dict.fromkeys(
            match.group() for match in re.finditer(r"\b[a-z0-9]+(?:-[a-z0-9]+)+\b", _unaccent(terms))
        ))
    )
    keywords = list(dict.fromkeys(_search_tokens(terms)))
    if not keywords and not hyphenated:
        return json.dumps(
            {"projeto": project_name, "estado": "nenhum termo de busca útil", "resultados": []},
            ensure_ascii=False,
        )

    candidates = []
    files_checked = 0
    files_with_matches = 0
    files_ignored = 0
    files_unchecked = 0
    max_files_checked = 5000
    for directory, subdirectories, filenames in _safe_directories(project):
        subdirectories[:] = [name for name in subdirectories if name not in SKIP_DIRECTORIES]
        for filename in filenames:
            path = directory / filename
            if not _allowed_source(path, project):
                files_ignored += 1
                continue
            if path.suffix.casefold() in {".class", ".jar", ".png", ".jpg", ".jpeg", ".pdf", ".zip"}:
                files_ignored += 1
                continue
            try:
                if path.stat().st_size > 512_000:
                    files_ignored += 1
                    continue
                if files_checked >= max_files_checked:
                    files_unchecked += 1
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                files_ignored += 1
                continue
            files_checked += 1
            relative_path = path.relative_to(project).as_posix()
            normalized_path = _unaccent(relative_path)
            path_matches = (
                [phrase for phrase in phrases if phrase in relative_path.casefold()]
                if phrases
                else sorted(set(keywords) & set(_search_tokens(relative_path)))
            )
            path_matches.extend(phrase for phrase in hyphenated if phrase in normalized_path)
            matching_lines = []
            for number, line in enumerate(content.splitlines(), start=1):
                exact = [phrase for phrase in phrases if phrase in line.casefold()]
                matches = exact if phrases else sorted(set(keywords) & set(_search_tokens(line)))
                matches.extend(phrase for phrase in hyphenated if phrase in _unaccent(line))
                if matches:
                    matching_lines.append(
                        {"linha": number, "trecho": line.strip()[:240], "correspondencias": matches}
                    )
            if matching_lines or path_matches:
                matched_phrases = [phrase for phrase in phrases if phrase in content.casefold()]
                matched_phrases.extend(phrase for phrase in hyphenated if phrase in _unaccent(content))
                if phrases and not matched_phrases and not path_matches:
                    continue
                files_with_matches += 1
                matching_lines.sort(key=lambda match: len(match["correspondencias"]), reverse=True)
                relevance = len(path_matches) * 3 + sum(
                    len(match["correspondencias"]) for match in matching_lines[:3]
                )
                candidates.append(
                    {
                        "caminho": relative_path,
                        "caminho_verificado": True,
                        "relevancia": relevance,
                        "correspondencias_no_caminho": path_matches,
                        "correspondencias": matching_lines[:8],
                        "frases_exatas_encontradas": matched_phrases,
                    }
                )

    candidates.sort(key=lambda result: result["relevancia"], reverse=True)
    results = candidates[:MAX_SEARCH_RESULTS]
    while results and len(json.dumps(results, ensure_ascii=False).encode("utf-8")) > MAX_SEARCH_RESULT_BYTES:
        results.pop()
    scan_complete = files_unchecked == 0 and files_ignored == 0
    results_truncated = len(candidates) > len(results)
    return json.dumps(
        {
            "projeto": project_name,
            "estado": "busca local concluída",
            "termos": keywords,
            "frases_exatas": phrases,
            "arquivos_verificados": files_checked,
            "arquivos_ignorados": files_ignored,
            "arquivos_nao_verificados_por_limite": files_unchecked,
            "arquivos_com_correspondencia": files_with_matches,
            "resultados": results,
            "limite_resultados": MAX_SEARCH_RESULTS,
            "limite_arquivos_verificados": max_files_checked,
            "busca_completa": scan_complete and not results_truncated,
            "varredura_completa": scan_complete,
            "resultados_truncados": results_truncated,
            "limite_bytes_resultados": MAX_SEARCH_RESULT_BYTES,
        },
        ensure_ascii=False,
        indent=2,
    )


def _matched_terms(line: str, keywords: list[str], phrases: list[str]) -> list[str]:
    normalized = line.casefold()
    matched = [phrase for phrase in phrases if phrase in normalized]
    matched.extend(
        keyword
        for keyword in keywords
        if re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", normalized)
    )
    return list(dict.fromkeys(matched))


def _search_tokens(value: str) -> list[str]:
    """Tokeniza sem acentos, descarta termos genéricos e normaliza plurais simples."""
    unaccented = _unaccent(value)
    tokens = []
    for token in re.findall(r"[a-z0-9_]+", unaccented):
        if len(token) < 3 or token in SEARCH_STOPWORDS:
            continue
        if token.endswith("s") and len(token) > 4:
            token = token[:-1]
        tokens.append(token)
    return tokens


def _unaccent(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    return "".join(character for character in normalized if not unicodedata.combining(character))


def project_inventory(project_name: str) -> str:
    """Confere a presença e stack de um projeto citado, sem navegar seu conteúdo."""
    project = _project_path(project_name)
    if project is None:
        return _missing_project(project_name)
    return json.dumps(
        {
            "projeto": project_name,
            "estado": "clone disponível",
            "diretorio_real": project.relative_to(PROJECT_ROOT).as_posix(),
            "stack_detectada": _stack(project),
        },
        ensure_ascii=False,
    )


def _validate_functionality_catalog(catalog: object) -> list[str]:
    """Confere o formato usado pela busca e referências a projetos catalogados."""
    errors = []
    if not isinstance(catalog, dict):
        return ["catálogo deve ser um objeto"]
    fields = ("records", "module_notes", "projects", "module_prefix_map", "confirmed_locations")
    for field in fields:
        if not isinstance(catalog.get(field), list) or not all(isinstance(item, dict) for item in catalog[field]):
            errors.append(f"{field} deve ser uma lista de objetos")
    if errors:
        return errors
    names = set()
    for index, project in enumerate(catalog["projects"]):
        group, name = project.get("group"), project.get("name")
        if not isinstance(group, str) or not group or not isinstance(name, str) or not name:
            errors.append(f"projects[{index}]: grupo/projeto inválido")
        else:
            names.add((group, name))
        repository = project.get("repository")
        if repository is not None and (
            not isinstance(repository, dict)
            or (repository.get("repository_group"), repository.get("project")) != (group, name)
        ):
            errors.append(f"projects[{index}]: referência de repositório inválida")
    for field in ("module_prefix_map", "confirmed_locations"):
        for index, item in enumerate(catalog[field]):
            for key in ("frontend_projects", "backend_projects", "complementary_projects"):
                if key not in item:
                    continue
                references = item[key]
                if not isinstance(references, list):
                    errors.append(f"{field}[{index}].{key}: lista inválida")
                    continue
                for reference in references:
                    if not isinstance(reference, dict) or (
                        reference.get("repository_group"), reference.get("project")
                    ) not in names:
                        errors.append(f"{field}[{index}].{key}: projeto inexistente: {reference}")
    for index, record in enumerate(catalog["records"]):
        if not all(isinstance(record.get(key), str) for key in ("code", "module", "functionality")):
            errors.append(f"records[{index}]: identificação inválida")
        for key in ("search_terms", "navigation_path", "analysis_files", "ui_routes"):
            value = record.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"records[{index}].{key}: lista inválida")
        sections = record.get("clinic_configuration_sections", [])
        if not isinstance(sections, list) or not all(
            isinstance(section, dict) and isinstance(section.get("settings", []), list) and all(
                isinstance(setting, dict) for setting in section.get("settings", [])
            ) for section in sections
        ):
            errors.append(f"records[{index}]: seções inválidas")
    for index, note in enumerate(catalog["module_notes"]):
        if not isinstance(note.get("settings", []), list) or not all(
            isinstance(setting, dict) for setting in note.get("settings", [])
        ):
            errors.append(f"module_notes[{index}]: configurações inválidas")
    return errors


def search_functionality_catalog(terms: str) -> str:
    """Busca funcionalidades, configurações e pistas no catálogo JSON local."""
    if (
        not FUNCTIONALITY_CATALOG_PATH.is_file()
        or FUNCTIONALITY_CATALOG_PATH.is_symlink()
        or not _within(FUNCTIONALITY_CATALOG_PATH, PROJECT_ROOT)
    ):
        return json.dumps(
            {"estado": "catálogo de funcionalidades ausente ou não permitido", "resultados": []},
            ensure_ascii=False,
        )

    try:
        catalog = json.loads(FUNCTIONALITY_CATALOG_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        return json.dumps(
            {"estado": "não foi possível ler o catálogo", "detalhe": str(error), "resultados": []},
            ensure_ascii=False,
        )
    errors = _validate_functionality_catalog(catalog)
    if errors:
        return json.dumps(
            {"estado": "catálogo de funcionalidades inválido", "detalhes": errors[:10], "resultados": []},
            ensure_ascii=False,
        )

    query_phrases = [phrase.strip() for phrase in terms.split("|") if phrase.strip()]
    query_tokens = _catalog_tokens(" ".join(query_phrases))
    if not query_tokens:
        return json.dumps(
            {"estado": "nenhum termo útil para busca", "resultados": []},
            ensure_ascii=False,
        )

    results: list[dict] = []

    def add_candidate(candidate: dict, labels: list[str], search_terms: list[str]) -> None:
        relevant_terms = []
        score = 0
        for search_term in dict.fromkeys([*labels, *search_terms]):
            if not isinstance(search_term, str) or not search_term.strip():
                continue
            tokens = _catalog_tokens(search_term)
            overlap = sum(
                1
                for token in query_tokens
                if any(
                    token == candidate_token
                    or (
                        token.isalpha()
                        and candidate_token.isalpha()
                        and min(len(token), len(candidate_token)) >= 6
                        and token[:6] == candidate_token[:6]
                    )
                    for candidate_token in tokens
                )
            )
            if overlap:
                relevant_terms.append(search_term)
                score = max(score, overlap)
            if any(_contains_catalog_phrase(search_term, phrase) for phrase in query_phrases):
                relevant_terms.append(search_term)
                score = max(score, len(query_tokens) + 1)
        if score < min(2, len(query_tokens)):
            return
        if score:
            results.append(
                {"relevancia": score, "termos_correspondentes": list(dict.fromkeys(relevant_terms)), **candidate}
            )

    for record in catalog.get("records", []):
        add_candidate(
            {
                "tipo": "funcionalidade",
                "codigo": record.get("code"),
                "modulo": record.get("module"),
                "funcionalidade": record.get("functionality"),
                "subfuncionalidade": record.get("subfunctionality"),
                "caminho_navegacao": record.get("navigation_path", []),
                "analysis_files": record.get("analysis_files", []),
                "ui_routes": record.get("ui_routes", []),
            },
            [record.get("code", ""), record.get("module", ""), record.get("functionality", ""),
             record.get("subfunctionality") or "", " > ".join(record.get("navigation_path", []))],
            record.get("search_terms", []),
        )

        for section in record.get("clinic_configuration_sections", []):
            section_candidate = {
                "tipo": "secao_configuracao",
                "codigo": record.get("code"),
                "modulo": record.get("module"),
                "funcionalidade": record.get("functionality"),
                "secao": section.get("label"),
                "anchor": section.get("anchor"),
                "visibilidade": section.get("visibility"),
                "analysis_files": record.get("analysis_files", []),
                "ui_routes": record.get("ui_routes", []),
            }
            add_candidate(section_candidate, [section.get("label", "")], section.get("search_terms", []))
            for setting in section.get("settings", []):
                add_candidate(
                    {**section_candidate, "tipo": "configuracao", "configuracao": setting.get("label")},
                    [section.get("label", ""), setting.get("label", "")],
                    setting.get("search_terms", []),
                )

    for note in catalog.get("module_notes", []):
        for setting in note.get("settings", []):
            add_candidate(
                {
                    "tipo": "configuracao_modulo",
                    "modulo": note.get("module"),
                    "secao": note.get("section"),
                    "configuracao": setting.get("label"),
                    "analysis_files": note.get("analysis_files", []),
                },
                [note.get("module", ""), note.get("section", ""), setting.get("label", "")],
                setting.get("search_terms", []),
            )

    for location in catalog.get("confirmed_locations", []):
        frontend_sources = location.get("frontend_sources", [])
        backend_sources = location.get("backend_sources", [])
        add_candidate(
            {
                "tipo": "localizacao_confirmada",
                "codigo": location.get("code"),
                "caminho_funcional": location.get("functional_path"),
                "frontend_projects": location.get("frontend_projects", []),
                "frontend_sources": frontend_sources,
                "backend_projects": location.get("backend_projects", []),
                "backend_sources": backend_sources,
                "status": location.get("status"),
            },
            [location.get("code", ""), location.get("functional_path", "")],
            [],
        )

    for prefix in catalog.get("module_prefix_map", []):
        add_candidate(
            {
                "tipo": "mapa_por_prefixo",
                "prefixo": prefix.get("prefix"),
                "modulo": prefix.get("module"),
                "frontend_projects": prefix.get("frontend_projects", []),
                "backend_projects": prefix.get("backend_projects", []),
                "complementary_projects": prefix.get("complementary_projects", []),
                "observacoes": prefix.get("notes"),
            },
            [prefix.get("prefix", ""), prefix.get("module", ""), prefix.get("notes", "")],
            [],
        )

    for project in catalog.get("projects", []):
        repository = project.get("repository") or {}
        add_candidate(
            {
                "tipo": "projeto_catalogado",
                "grupo": project.get("group"),
                "projeto": project.get("name"),
                "repositorio": repository,
                "uso_esperado": project.get("purpose"),
            },
            [project.get("group", ""), project.get("name", ""), project.get("purpose", "")],
            [],
        )

    results.sort(key=lambda result: result["relevancia"], reverse=True)
    return json.dumps(
        {
            "estado": "busca no catálogo concluída",
            "termos": query_phrases,
            "resultados": results[:15],
            "limite_resultados": 15,
            "total_resultados": len(results),
            "resultados_truncados": len(results) > 15,
            "aviso": "Resultados são pistas de navegação; valide arquivos e comportamento no repositório.",
        },
        ensure_ascii=False,
        indent=2,
    )


def _catalog_tokens(value: str) -> list[str]:
    stop_words = {"a", "as", "o", "os", "de", "do", "da", "dos", "das", "no", "na", "em", "para", "por", "e"}
    return [token.casefold() for token in re.findall(r"[\wÀ-ÿ]+", value) if len(token) >= 2 and token.casefold() not in stop_words]


def _contains_catalog_phrase(search_term: str, phrase: str) -> bool:
    if re.search(rf"(?<!\w){re.escape(phrase.casefold())}(?!\w)", search_term.casefold()):
        return True
    return (
        len(_catalog_tokens(search_term)) >= 2
        and re.search(rf"(?<!\w){re.escape(search_term.casefold())}(?!\w)", phrase.casefold()) is not None
    )


def read_repository_paths(
    project_name: str, paths: str, start_line: int | None = None, end_line: int | None = None
) -> str:
    """Valida e lê caminhos relativos selecionados dentro de um clone local."""
    project = _project_path(project_name)
    if project is None:
        return _missing_project(project_name, arquivos=[])

    files = []
    total_bytes = 0
    skipped_files = 0
    for raw_path in paths.splitlines():
        relative_path = raw_path.strip()
        if not relative_path:
            continue
        if len(files) >= MAX_READ_FILES or total_bytes >= MAX_READ_TOTAL_BYTES:
            skipped_files += 1
            continue
        path = project / relative_path
        if not _allowed_source(path, project) or not path.is_file():
            files.append({"caminho": relative_path, "estado": "ausente ou fora do escopo permitido"})
            continue
        selected_start = max(1, start_line) if start_line is not None else 1
        ranged = start_line is not None or end_line is not None
        remaining = min(MAX_READ_FILE_BYTES, MAX_READ_TOTAL_BYTES - total_bytes)
        try:
            if ranged:
                # O total de linhas só é conhecido quando o intervalo alcança o fim do arquivo.
                rendered_lines = []
                used_bytes = 0
                truncated = False
                selected_end = selected_start - 1
                line_count = 0
                ended_at_eof = True
                with path.open(encoding="utf-8", errors="replace", newline="") as source:
                    for number, line in enumerate(source, start=1):
                        line_count = number
                        if number < selected_start:
                            continue
                        if end_line is not None and number > end_line:
                            ended_at_eof = False
                            break
                        selected_end = number
                        piece = ("\n" if rendered_lines else "") + f"{number}: {line.rstrip('\r\n')}"
                        piece_bytes = piece.encode("utf-8")
                        if used_bytes + len(piece_bytes) > remaining:
                            prefix = piece_bytes[:remaining - used_bytes].decode("utf-8", errors="ignore")
                            rendered_lines.append(prefix)
                            used_bytes += len(prefix.encode("utf-8"))
                            truncated = True
                        else:
                            rendered_lines.append(piece)
                            used_bytes += len(piece_bytes)
                        if truncated:
                            ended_at_eof = False
                            break
                rendered = "".join(rendered_lines)
                more_lines = not ended_at_eof and not truncated
                line_total = line_count if ended_at_eof else None
            else:
                content = path.read_text(encoding="utf-8", errors="replace")
                lines = content.splitlines()
                line_total = len(lines)
                selected_end = line_total
                encoded = content.encode("utf-8")
                truncated = len(encoded) > remaining
                rendered = encoded[:remaining].decode("utf-8", errors="ignore") if truncated else content
                used_bytes = len(rendered.encode("utf-8"))
                more_lines = False
        except OSError:
            files.append({"caminho": relative_path, "estado": "não foi possível ler"})
            continue
        total_bytes += used_bytes
        files.append(
            {
                "caminho": relative_path,
                "caminho_verificado": True,
                "linhas": line_total,
                "conteudo": rendered,
                "linha_inicial": selected_start if ranged else 1,
                "linha_final": selected_end if ranged else min(line_total, len(rendered.splitlines())),
                "truncado": truncated or more_lines,
                "leitura_completa": not truncated and not more_lines,
            }
        )
    return json.dumps(
        {
            "projeto": project_name,
            "estado": "caminhos conferidos",
            "arquivos": files,
            "arquivos_ignorados_por_limite": skipped_files,
            "leitura_completa": skipped_files == 0 and all(item.get("leitura_completa", True) for item in files),
            "limites": {"arquivos": MAX_READ_FILES, "bytes_por_arquivo": MAX_READ_FILE_BYTES, "bytes_total": MAX_READ_TOTAL_BYTES},
        },
        ensure_ascii=False,
        indent=2,
    )
