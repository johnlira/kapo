# Atendimento Funcional QuarkClinic

Assistente Agno para responder dúvidas funcionais de atendimento do QuarkClinic.

O agente responde com orientações práticas, fundamentadas no catálogo funcional e
no código dos clones locais. Os clones são consultados sem serem alterados.

O catálogo `data/funcionalidades.json` reúne termos de busca, funcionalidades,
projetos e localizações candidatas. Ele serve como pista: o agente confirma o
comportamento nos clones de `repositorios/` antes de responder.

## Executar o AgentOS local

O AgentOS local oferece API para o Agent UI oficial (incluído em `agent-ui/`) e
também pode ser conectado ao Agno Control Plane em [os.agno.com](https://os.agno.com).
Esses são clientes distintos do mesmo backend. A porta padrão é `7777` e pode ser
alterada com `AGNO_QA_PORT` no `.env`. Sessões e histórico são persistidos em
`.agno/sessions.db` (SQLite; o diretório é criado pelo `SqliteDb`); traces do
AgentOS também são gravados nesse banco. As últimas três execuções da conversa
entram no contexto. Configure
`AGNO_QA_NUM_HISTORY_RUNS` para mudar o limite, `AGNO_QA_DB_FILE` para outro
arquivo SQLite. A criação do provider fica isolada na configuração do Agent,
permitindo trocar o adapter futuramente sem alterar as ferramentas ou instruções.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edite .env e preencha OPENAI_API_KEY; opcionalmente configure porta/banco/limite.
agno-qa --serve
```

`AGNO_QA_MODEL` troca o modelo, com padrão `gpt-5.4-mini`. O agente usa a OpenAI
Responses API com reasoning `low`, configurável por
`AGNO_QA_REASONING_EFFORT`. A porta configurada em `AGNO_QA_PORT` precisa ser
usada também no endpoint do Agno UI.

Em outro terminal, inicie a interface oficial (requer Node e pnpm):

```bash
cd agent-ui
pnpm install --frozen-lockfile
pnpm dev
```

Abra `http://localhost:3000`; o endpoint padrão `http://localhost:7777` já vem
selecionado. O AgentOS usa as origens CORS padrão do Agno, permitindo o Agent UI
local (`localhost:3000`) e o Agno Control Plane (`os.agno.com`). A API também
fica disponível em `http://localhost:<AGNO_QA_PORT>/docs`.
Para consultar traces, abra a seção **Traces** no Control Plane. Eles incluem
detalhes das execuções e podem conter entradas, respostas e resultados das tools.

Cada conversa da UI mantém o `session_id` devolvido pelo AgentOS nos turnos
seguintes; **New Chat** limpa esse identificador e inicia outra sessão. Se um
cliente API enviar `user_id`, o Agno associa as execuções a esse usuário; a UI
incluída não autentica nem envia `user_id` por padrão. O agente usa o histórico
recente para interpretar referências curtas na mesma conversa e pede
esclarecimento quando houver mais de uma interpretação relevante.

O Agent UI upstream declara suporte primário ao Agno v2. Nesta combinação, o chat,
as sessões e o streaming foram validados com o AgentOS v3.0.11; repita a validação
ao atualizar a UI ou o SDK. A interface não inclui telas de gerenciamento de
memória ou knowledge.

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
