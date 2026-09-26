# Agno QA

Projeto mínimo para começar a criar agentes com Agno.

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

`AGNO_QA_MODEL` troca o modelo, com padrão `gpt-4o-mini`. A porta configurada
em `AGNO_QA_PORT` precisa ser usada também no endpoint do Agno UI.

No Agno UI, escolha **Add new OS**, selecione **Local** e informe
`http://localhost:<AGNO_QA_PORT>` como endpoint. A API também fica disponível em
`http://localhost:<AGNO_QA_PORT>/docs`.

Para executar em modo terminal, use `agno-qa "Olá!"`.
