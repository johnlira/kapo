# Atendimento Funcional QuarkClinic

Assistente Agno para responder dúvidas funcionais de atendimento do QuarkClinic.

O agente responde com orientações práticas, fundamentadas no catálogo funcional e
no código dos clones locais. Os clones são consultados sem serem alterados.

O catálogo `data/funcionalidades.json` reúne termos de busca, funcionalidades,
projetos e localizações candidatas. Ele serve como pista: o agente confirma o
comportamento nos clones de `repositorios/` antes de responder.

## Executar com o Agno UI

O projeto disponibiliza um AgentOS local, que pode ser conectado ao Agno Control
Plane em [os.agno.com](https://os.agno.com). A porta padrão é `7777` e pode ser
alterada com `AGNO_QA_PORT` no `.env`.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edite .env e preencha OPENAI_API_KEY e, se necessário, AGNO_QA_PORT.
agno-qa --serve
```

`AGNO_QA_MODEL` troca o modelo, com padrão `gpt-5.4-mini`. O agente usa a OpenAI
Responses API com reasoning `low`, configurável por
`AGNO_QA_REASONING_EFFORT`. A porta configurada em `AGNO_QA_PORT` precisa ser
usada também no endpoint do Agno UI.

No Agno UI, escolha **Add new OS**, selecione **Local** e informe
`http://localhost:<AGNO_QA_PORT>` como endpoint. A API também fica disponível em
`http://localhost:<AGNO_QA_PORT>/docs`.

Para executar em modo terminal com qualquer pergunta funcional, use:

```bash
agno-qa "<pergunta funcional>"
```

O inventário compara `scripts/projetos.tsv` com os diretórios reais em
`repositorios/`. Os únicos utilitários são:

```bash
bash scripts/clonar-projetos.sh
bash scripts/atualizar-producao.sh
```

Há versões PowerShell com os mesmos nomes. O atualizador sincroniza
exclusivamente para a branch `producao` e descarta alterações locais nos clones.
Veja `docs/etapa-0.md` para o escopo atual.
