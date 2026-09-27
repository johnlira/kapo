"""Execute com: python -m unittest discover -s tests -p 'integration_*.py' -v.

Pré-requisito: clone real em repositorios/back/quarkclinic-gng, contendo
grails-app/views/chamador/_form.gsp.
"""

import json
import unittest

from app import sources


PROJECT = "quarkclinic-gng"
PATH = "grails-app/views/chamador/_form.gsp"


class TotemCloneIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        clone = sources.REPOSITORIES_ROOT / "back" / PROJECT
        if not (clone / PATH).is_file():
            raise RuntimeError(
                f"Integração requer clone em {clone} com o arquivo {PATH}"
            )

    def test_real_clone_totem_phrases(self):
        response = json.loads(
            sources.search_repository_files(
                PROJECT,
                "Configuração da Fila do Totem|Configuração do Totem (Web)|"
                "URL do Servidor de Impressão|Requerer o nome ao emitir fichas não agendadas",
            )
        )
        matches = {
            phrase
            for result in response["resultados"]
            for line in result["correspondencias"]
            for phrase in line["correspondencias"]
        }
        self.assertTrue(
            {
                "configuração da fila do totem",
                "configuração do totem (web)",
                "url do servidor de impressão",
                "requerer o nome ao emitir fichas não agendadas",
            } <= matches
        )

    def test_real_clone_line_range(self):
        response = json.loads(sources.read_repository_paths(PROJECT, PATH, 375, 415))
        file_result = response["arquivos"][0]
        self.assertEqual(file_result["linha_inicial"], 375)
        self.assertEqual(file_result["linha_final"], 415)
        self.assertTrue(file_result["conteudo"].startswith("375:"))
        self.assertIn("415:", file_result["conteudo"])
        self.assertIn("Configuração do Totem (Web)", file_result["conteudo"])
        self.assertIn("URL do Servidor de Impressão", file_result["conteudo"])
