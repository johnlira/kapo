import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import sources


class SourceImprovementsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.root = Path(self.temp_dir.name)
        self.project = self.root / "front" / "demo"
        self.project.mkdir(parents=True)
        root_patch = patch.object(sources, "REPOSITORIES_ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def test_search_limit_counts_only_eligible_files_and_preserves_completeness(self):
        # Arquivos vazios bastam para verificar o limite sem criar conteúdo artificial volumoso.
        for index in range(5001):
            (self.project / f"{index:04}.txt").touch()
        for count in (4999, 5000, 5001):
            with patch.object(sources, "_safe_directories", return_value=iter([
                (self.project, [], [f"{index:04}.txt" for index in range(count)])
            ])):
                result = json.loads(sources.search_repository_files("demo", "agendamento"))
            self.assertEqual(result["arquivos_verificados"], min(count, 5000))
            self.assertEqual(result["arquivos_nao_verificados_por_limite"], max(0, count - 5000))
            self.assertEqual(result["varredura_completa"], count <= 5000)
            self.assertEqual(result["busca_completa"], count <= 5000)

    def test_exclusions_prevent_claim_of_exhaustive_search(self):
        (self.project / "huge.txt").write_bytes(b"x" * 512001)
        (self.project / "picture.png").touch()
        (self.project / "candidate.txt").write_text("nada")
        result = json.loads(sources.search_repository_files("demo", "agendamento"))
        self.assertEqual(result["arquivos_verificados"], 1)
        self.assertEqual(result["arquivos_ignorados"], 2)
        self.assertEqual(result["arquivos_nao_verificados_por_limite"], 0)
        self.assertFalse(result["varredura_completa"])

    def test_results_truncated_independently_of_scan(self):
        for index in range(11):
            (self.project / f"match-{index}.txt").write_text("agendamento")
        result = json.loads(sources.search_repository_files("demo", "agendamento"))
        self.assertTrue(result["varredura_completa"])
        self.assertTrue(result["resultados_truncados"])
        self.assertFalse(result["busca_completa"])

    def test_colliding_project_names_require_group_and_inventory_lists_both(self):
        other = self.root / "back" / "demo"
        other.mkdir(parents=True)
        (self.project / "proof.txt").write_text("frente")
        (other / "proof.txt").write_text("fundo")
        with patch.object(sources, "_catalog", return_value=[]), patch.object(sources, "PROJECT_ROOT", self.root):
            inventory = json.loads(sources.catalog_repositories())
        self.assertEqual(inventory["total_clones_locais"], 2)
        self.assertEqual({row["diretorio_real"] for row in inventory["projetos"]},
                         {"front/demo", "back/demo"})
        ambiguous = json.loads(sources.read_repository_paths("demo", "proof.txt"))
        self.assertIn("ambíguo", ambiguous["estado"])
        self.assertEqual(ambiguous["opcoes"], ["back/demo", "front/demo"])
        self.assertEqual(ambiguous["arquivos"], [])
        self.assertIn("ambíguo", json.loads(sources.search_repository_files("demo", "fundo"))["estado"])
        for group, expected in (("front", "frente"), ("back", "fundo")):
            read = json.loads(sources.read_repository_paths(f"{group}/demo", "proof.txt"))
            self.assertEqual(read["arquivos"][0]["conteudo"], expected)
            search = json.loads(sources.search_repository_files(f"{group}/demo", expected))
            self.assertEqual(search["resultados"][0]["caminho"], "proof.txt")

    def test_range_reads_only_requested_prefix_and_reports_partial_line_count(self):
        path = self.project / "long.txt"
        path.write_text("\n".join(str(index) for index in range(100000)))
        with patch.object(Path, "read_text", side_effect=AssertionError("whole-file read")):
            result = json.loads(sources.read_repository_paths("demo", "long.txt", 3, 5))
        entry = result["arquivos"][0]
        self.assertEqual(entry["conteudo"], "3: 2\n4: 3\n5: 4")
        self.assertIsNone(entry["linhas"])
        self.assertTrue(entry["truncado"])

    def test_catalog_validation_and_truncation(self):
        catalog = {"records": [], "module_notes": [], "projects": [
            {"group": "front", "name": "demo", "purpose": "agendamento"} for _ in range(20)
        ], "module_prefix_map": [], "confirmed_locations": []}
        path = self.root / "catalog.json"
        with patch.object(sources, "FUNCTIONALITY_CATALOG_PATH", path), patch.object(sources, "PROJECT_ROOT", self.root):
            path.write_text(json.dumps(catalog))
            result = json.loads(sources.search_functionality_catalog("agendamento"))
            self.assertEqual(result["total_resultados"], 20)
            self.assertEqual(len(result["resultados"]), 15)
            self.assertTrue(result["resultados_truncados"])
            catalog["module_prefix_map"] = [{"frontend_projects": [
                {"repository_group": "front", "project": "nonexistent"}
            ]}]
            path.write_text(json.dumps(catalog))
            self.assertIn("inválido", json.loads(sources.search_functionality_catalog("agendamento"))["estado"])
            path.write_text(json.dumps([]))
            self.assertIn("inválido", json.loads(sources.search_functionality_catalog("agendamento"))["estado"])

    def test_real_catalog_format_and_project_references(self):
        catalog = json.loads(sources.FUNCTIONALITY_CATALOG_PATH.read_text(encoding="utf-8"))
        self.assertEqual(sources._validate_functionality_catalog(catalog), [])


if __name__ == "__main__":
    unittest.main()
