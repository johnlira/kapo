"""Busca funcionalidades e consulta os repositórios locais."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
import re


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORIES_ROOT = (PROJECT_ROOT / "repositorios").resolve()
CATALOG_PATH = (PROJECT_ROOT / "scripts/projetos.tsv").resolve()
FUNCTIONALITY_CATALOG_PATH = PROJECT_ROOT / "data/funcionalidades.json"

SKIP_DIRECTORIES = {
    ".git",
    ".gradle",
    "build",
    "dist",
    "node_modules",
    "target",
    "vendor",
}
STACK_MARKERS = {
    "package.json": "Node.js",
    "build.gradle": "Gradle/JVM",
    "build.gradle.kts": "Gradle/Kotlin DSL",
    "pom.xml": "Maven/JVM",
    "requirements.txt": "Python",
    "pyproject.toml": "Python",
}

def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


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
                projects[project.name] = project
    return projects


def _project_path(project_name: str) -> Path | None:
    """Resolve nome de clone sem seguir links para fora da árvore permitida."""
    if REPOSITORIES_ROOT.is_symlink() or not REPOSITORIES_ROOT.is_dir():
        return None
    for category in REPOSITORIES_ROOT.iterdir():
        if category.is_symlink() or not category.is_dir() or not _within(category, REPOSITORIES_ROOT):
            continue
        project = category / project_name
        if project.is_dir() and not project.is_symlink() and _within(project, REPOSITORIES_ROOT):
            return project
    return None


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
        catalog_names.add(name)
        project = available.get(name)
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
    for name, project in sorted(available.items()):
        if name not in catalog_names:
            rows.append(
                {
                    "grupo_catalogado": project.parent.name,
                    "projeto": name,
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
        return json.dumps(
            {"projeto": project_name, "estado": "ausente localmente ou nome não encontrado", "resultados": []},
            ensure_ascii=False,
        )

    phrases = [phrase.strip().casefold() for phrase in terms.split("|") if phrase.strip()]
    stopwords = {"de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas", "e", "ou", "a", "o", "os", "as", "um", "uma", "para", "por", "com"}
    keywords = [term.casefold() for term in re.findall(r"[\wÀ-ÿ]+", terms) if len(term) >= 3 and term.casefold() not in stopwords]
    if not keywords:
        return json.dumps(
            {"projeto": project_name, "estado": "nenhum termo de busca útil", "resultados": []},
            ensure_ascii=False,
        )

    results = []
    files_checked = 0
    files_with_matches = 0
    max_files_checked = 5000
    for directory, subdirectories, filenames in _safe_directories(project):
        subdirectories[:] = [name for name in subdirectories if name not in SKIP_DIRECTORIES]
        for filename in filenames:
            path = directory / filename
            if path.is_symlink() or not _within(path, project) or not _within(path, REPOSITORIES_ROOT):
                continue
            if path.suffix.casefold() in {".class", ".jar", ".png", ".jpg", ".jpeg", ".pdf", ".zip"}:
                continue
            try:
                if path.stat().st_size > 512_000:
                    continue
                content = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            files_checked += 1
            matching_lines = []
            for number, line in enumerate(content.splitlines(), start=1):
                exact = [phrase for phrase in phrases if phrase in line.casefold()]
                matches = exact if phrases else _matched_terms(line, keywords, [])
                if matches:
                    matching_lines.append({"linha": number, "trecho": line.strip()[:240], "correspondencias": matches})
            if matching_lines:
                files_with_matches += 1
                relevant_matches = [
                    match
                    for match in matching_lines
                    if phrases or match["correspondencias"]
                ]
                matched_phrases = [phrase for phrase in phrases if phrase in content.casefold()]
                if phrases and not matched_phrases:
                    continue
                if not phrases and not relevant_matches:
                    continue
                results.append(
                    {
                        "caminho": path.relative_to(project).as_posix(),
                        "caminho_verificado": True,
                        "correspondencias": relevant_matches[:8] if relevant_matches else matching_lines[:8],
                        "frases_exatas_encontradas": matched_phrases,
                    }
                )
            if len(results) >= 30:
                break
            if files_checked >= max_files_checked:
                break
        if len(results) >= 30 or files_checked >= max_files_checked:
            break

    return json.dumps(
        {
            "projeto": project_name,
            "estado": "busca local concluída",
            "termos": keywords,
            "frases_exatas": phrases,
            "arquivos_verificados": files_checked,
            "arquivos_com_correspondencia": files_with_matches,
            "resultados": results,
            "limite_resultados": 30,
            "limite_arquivos_verificados": max_files_checked,
            "busca_completa": files_checked < max_files_checked and len(results) < 30,
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


def project_inventory(project_name: str) -> str:
    """Confere a presença e stack de um projeto citado, sem navegar seu conteúdo."""
    project = _project_path(project_name)
    if project is None:
        return json.dumps(
            {"projeto": project_name, "estado": "ausente localmente ou nome não encontrado"},
            ensure_ascii=False,
        )
    return json.dumps(
        {
            "projeto": project_name,
            "estado": "clone disponível",
            "diretorio_real": project.relative_to(PROJECT_ROOT).as_posix(),
            "stack_detectada": _stack(project),
        },
        ensure_ascii=False,
    )


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
        return json.dumps(
            {"projeto": project_name, "estado": "ausente localmente ou nome não encontrado", "arquivos": []},
            ensure_ascii=False,
        )

    files = []
    for raw_path in paths.splitlines():
        relative_path = raw_path.strip()
        if not relative_path:
            continue
        path = project / relative_path
        if path.is_symlink() or not path.is_file() or not _within(path, project) or not _within(path, REPOSITORIES_ROOT):
            files.append({"caminho": relative_path, "estado": "ausente ou fora do escopo permitido"})
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            files.append({"caminho": relative_path, "estado": "não foi possível ler"})
            continue
        lines = content.splitlines()
        selected_start = max(1, start_line) if start_line is not None else 1
        selected_end = min(len(lines), end_line) if end_line is not None else len(lines)
        selected = lines[selected_start - 1 : selected_end]
        ranged = start_line is not None or end_line is not None
        rendered = "\n".join(f"{number}: {line}" for number, line in enumerate(selected, start=selected_start)) if ranged else content[:12_000]
        files.append(
            {
                "caminho": relative_path,
                "caminho_verificado": True,
                "linhas": len(content.splitlines()),
                "conteudo": rendered,
                "linha_inicial": selected_start if ranged else 1,
                "linha_final": min(selected_end, len(lines)) if ranged else min(len(lines), len(rendered.splitlines())),
                "truncado": (len(content) > 12_000) if not ranged else selected_end < len(lines),
            }
        )
    return json.dumps(
        {"projeto": project_name, "estado": "caminhos conferidos", "arquivos": files},
        ensure_ascii=False,
        indent=2,
    )
