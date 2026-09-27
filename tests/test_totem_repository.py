import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import sources
from app.sources import (
    read_repository_paths,
    search_functionality_catalog,
    search_repository_files,
)


PROJECT = "demo-totem"
PATH = "grails-app/views/chamador/_form.gsp"


class TotemRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        root = Path(self.temp_dir.name)
        project = root / "back" / PROJECT
        file_path = project / PATH
        file_path.parent.mkdir(parents=True)
        file_path.write_text(
            "Cabeçalho\n"
            "Configuração do Totem (Web)\n"
            "URL do Servidor de Impressão\n"
            "Configuração da Fila do Totem\n"
            "Requerer o nome ao emitir fichas não agendadas\n"
            "Rodapé\n",
            encoding="utf-8",
        )
        root_patch = patch.object(sources, "REPOSITORIES_ROOT", root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def test_exact_alternative_phrases_find_totem_fields(self):
        response = json.loads(
            search_repository_files(
                PROJECT,
                "Configuração da Fila do Totem|Configuração do Totem (Web)|"
                "URL do Servidor de Impressão|Requerer o nome ao emitir fichas não agendadas",
            )
        )
        matches = [
            phrase
            for result in response["resultados"]
            for line in result["correspondencias"]
            for phrase in line["correspondencias"]
        ]
        self.assertIn("configuração do totem (web)", matches)
        self.assertIn("url do servidor de impressão", matches)
        self.assertIn("configuração da fila do totem", matches)
        self.assertIn("requerer o nome ao emitir fichas não agendadas", matches)

    def test_totem_prefix_finds_frontend_and_backend_projects(self):
        response = json.loads(search_functionality_catalog("TOT"))
        prefix = next(
            result
            for result in response["resultados"]
            if result["tipo"] == "mapa_por_prefixo" and result["prefixo"] == "TOT"
        )
        frontend = {item["project"] for item in prefix["frontend_projects"]}
        backend = {item["project"] for item in prefix["backend_projects"]}
        self.assertIn("quarkclinic-totem-front", frontend)
        self.assertIn("quarkclinic-totem-back", backend)

    def test_line_range_returns_numbered_requested_lines(self):
        response = json.loads(read_repository_paths(PROJECT, PATH, 2, 3))
        file_result = response["arquivos"][0]
        self.assertEqual(file_result["linha_inicial"], 2)
        self.assertEqual(file_result["linha_final"], 3)
        self.assertEqual(
            file_result["conteudo"],
            "2: Configuração do Totem (Web)\n3: URL do Servidor de Impressão",
        )


if __name__ == "__main__":
    unittest.main()
