import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import sources


class SourceLimitsTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.project = self.root / "grupo" / "demo"
        self.project.mkdir(parents=True)
        self.root_patch = patch.object(sources, "REPOSITORIES_ROOT", self.root)
        self.root_patch.start()

    def tearDown(self):
        self.root_patch.stop()
        self.temp_dir.cleanup()

    def test_read_caps_file_count_and_content_bytes_with_completeness_flags(self):
        (self.project / "large.txt").write_text("x" * (sources.MAX_READ_FILE_BYTES * 2))
        for index in range(sources.MAX_READ_FILES):
            (self.project / f"file-{index}.txt").write_text("conteúdo")

        response = json.loads(
            sources.read_repository_paths(
                "demo", "\n".join(["large.txt", *[f"file-{i}.txt" for i in range(sources.MAX_READ_FILES)]])
            )
        )
        self.assertLessEqual(len(response["arquivos"]), sources.MAX_READ_FILES)
        large = response["arquivos"][0]
        self.assertTrue(large["truncado"])
        self.assertFalse(large["leitura_completa"])
        self.assertGreater(response["arquivos_ignorados_por_limite"], 0)
        self.assertFalse(response["leitura_completa"])

    def test_search_reports_result_limit_and_incomplete_scan(self):
        for index in range(sources.MAX_SEARCH_RESULTS + 2):
            (self.project / f"match-{index}.txt").write_text("palavra distintiva")

        response = json.loads(sources.search_repository_files("demo", "distintiva"))
        self.assertEqual(len(response["resultados"]), sources.MAX_SEARCH_RESULTS)
        self.assertTrue(response["resultados_truncados"])
        self.assertFalse(response["busca_completa"])

    def test_search_without_pipe_matches_individual_keywords(self):
        (self.project / "depositos.txt").write_text("Paciente realizou depósito financeiro")

        response = json.loads(sources.search_repository_files("demo", "depósito paciente"))

        self.assertEqual(len(response["resultados"]), 1)
        self.assertEqual(response["resultados"][0]["caminho"], "depositos.txt")

    def test_search_ranks_specific_file_paths_above_generic_keyword_hits(self):
        for index in range(12):
            (self.project / f"generic-{index}.txt").write_text("saldo disponível")

        form = self.project / "src" / "deposito" / "deposito-form.component.html"
        form.parent.mkdir(parents=True)
        form.write_text("Botão Adicionar para selecionar Carteira")

        response = json.loads(
            sources.search_repository_files("demo", "depósitos saldo carteira adicionar")
        )

        self.assertEqual(
            response["resultados"][0]["caminho"],
            "src/deposito/deposito-form.component.html",
        )
        self.assertEqual(response["resultados"][0]["correspondencias_no_caminho"], ["deposito"])

    def test_catalog_search_finds_patient_deposits_from_financial_terms(self):
        response = json.loads(
            sources.search_functionality_catalog("paciente financeiro depósito saldo adiantamento")
        )

        deposits = [
            result
            for result in response["resultados"]
            if result.get("codigo") == "ATEND_012.17"
        ]
        self.assertTrue(deposits)
        self.assertEqual(deposits[0]["subfuncionalidade"], "Financeiro > Depósitos")


if __name__ == "__main__":
    unittest.main()
