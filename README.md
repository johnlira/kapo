# Kapo

Kapo é um assistente Agno para responder dúvidas funcionais de atendimento do QuarkClinic.

O agente responde com orientações práticas, fundamentadas no catálogo funcional e
no código dos clones locais. Os clones são consultados sem serem alterados.

O catálogo `data/funcionalidades.json` reúne termos de busca, funcionalidades,
projetos e localizações candidatas. Ele serve como pista: o agente confirma o
comportamento nos clones de `repositorios/` antes de responder.

O atendimento é restrito a funcionalidades, fluxos e regras de negócio do
QuarkClinic. O agente consulta o código apenas para confirmar o comportamento
funcional e não deve divulgar arquivos, implementação, credenciais ou dados de
sessões. Arquivos de credenciais e diretórios privados conhecidos são excluídos
das ferramentas de busca e leitura; mantenha segredos fora dos clones e restrinja
o acesso aos repositórios, banco de sessões e traces no host.
Antes de cada execução, uma checagem de escopo classifica a pergunta por meio do
modelo: pedidos claramente alheios ao produto recebem uma recusa antes da resposta
do agente. Perguntas ambíguas que possam continuar um fluxo funcional seguem para
investigação. A checagem adiciona uma chamada ao modelo por mensagem.

## Executar o AgentOS local

O AgentOS local oferece API para a interface em `agent-ui/` e pode ser conectado
ao Agno OS hospedado. A porta padrão é `7777` (`AGNO_QA_PORT`); o endereço de
escuta é `0.0.0.0` por padrão (`AGNO_QA_HOST`) para aceitar conexões pela rede,
e o reload é opt-in (`AGNO_QA_RELOAD=true` somente em
desenvolvimento). Sessões e histórico são persistidos em
`.agno/sessions.db` (SQLite; o diretório é criado pelo `SqliteDb`); traces do
AgentOS também são gravados nesse banco. As últimas três execuções da conversa
entram no contexto. Configure
`AGNO_QA_NUM_HISTORY_RUNS` para mudar o limite, `AGNO_QA_DB_FILE` para outro
arquivo SQLite. `AGNO_QA_TOOL_CALL_LIMIT` limita chamadas de ferramentas por
execução (padrão 8), usando o limite nativo do Agno. As ferramentas limitam a
busca a 10 resultados e a leitura a 5 arquivos, 12 KB por arquivo e 32 KB no
total; indicam quando a saída ou investigação foi truncada/incompleta.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
cp .env.example .env
# Edite .env: OPENAI_API_KEY, GOOGLE_CLIENT_ID, KAPO_WORKSPACE_DOMAIN,
# KAPO_ALLOWED_EMAILS e os arquivos de chave JWT descritos abaixo.
agno-qa --serve
```

`AGNO_QA_MODEL` troca o modelo, com padrão `gpt-5.4-mini`. O agente usa a OpenAI
Responses API com reasoning `low`, configurável por
`AGNO_QA_REASONING_EFFORT`. A UI acessa a API exclusivamente pelo proxy Next.js.
O agente não repete automaticamente chamadas do modelo (`retries=0`). Em caso de
HTTP 429, a execução falha sem retries ilimitados; aguarde a janela de limite ou
reduza a frequência/contexto antes de tentar novamente.

## Login Google e acesso pela VPN

Crie um cliente **OAuth 2.0 para aplicação web** no Google Cloud e configure a
origem JavaScript e o URI de retorno para o endereço pelo qual a equipe acessará
a UI (por exemplo, `https://chat.empresa.example` e
`https://chat.empresa.example/api/auth/callback/google`). A tela de consentimento
deve permitir tanto usuários do Workspace quanto sua conta pessoal: configure-a
como **External** e, enquanto estiver em teste, inclua as contas autorizadas como
usuários de teste. O domínio Workspace sozinho não substitui a lista de e-mails
permitidos. Configure HTTPS no endereço exposto pela VPN.

No `.env` da raiz, use o ID do cliente OAuth em `GOOGLE_CLIENT_ID`, o domínio
corporativo em `KAPO_WORKSPACE_DOMAIN` e seu endereço pessoal em
`KAPO_ALLOWED_EMAILS`; deixe a allowlist vazia se não for necessária. O Kapo
assina os tokens curtos do login Google com a chave privada RSA indicada por
`AGNO_QA_JWT_PRIVATE_KEY_FILE`. Gere um par RSA local (não compartilhe a chave
privada):

```bash
mkdir -p .secrets
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out .secrets/kapo-jwt-private.pem
chmod 600 .secrets/kapo-jwt-private.pem
```

No `os.agno.com`, abra as configurações deste AgentOS, habilite **JWT
Authorization**, copie a **public verification key** e salve o conteúdo PEM em
`.secrets/agno-os-public.pem`. Esse arquivo alimenta
`AGNO_OS_JWT_PUBLIC_KEY_FILE`; a chave pública pode ser compartilhada com o
runtime, mas não a chave privada correspondente ao emissor. O AgentOS valida
tokens RS256 do Control Plane e os tokens RS256 locais do Kapo usando as
respectivas chaves públicas. Reinicie o backend após copiar a chave do OS.

No
`agent-ui/.env.local`, copie `agent-ui/.env.example`, repita o **mesmo** ID de
cliente, domínio e allowlist (`AUTH_GOOGLE_ID`, `KAPO_WORKSPACE_DOMAIN`,
`KAPO_ALLOWED_EMAILS`), informe o segredo OAuth (`AUTH_GOOGLE_SECRET`), um
`AUTH_SECRET` aleatório independente e `AGENTOS_URL=http://127.0.0.1:7777`.
Esses valores são secretos; não use variáveis `NEXT_PUBLIC_` para tokens.

Em outro terminal, inicie a UI (requer Node e pnpm):

```bash
cd agent-ui
pnpm install --frozen-lockfile
pnpm build
pnpm start
```

O proxy da UI exige sessão Auth.js,
troca o Google ID token por um JWT curto no backend e encaminha as requisições
do chat. O backend valida o token Google e permite somente o domínio Workspace
ou os e-mails pessoais explicitamente listados. O Agno associa sessões ao
`sub` verificado do Google; os testes de isolamento cobrem leitura, listagem,
exclusão e execução com `user_id` forjado na versão instalada do Agno (3.0.11).
O proxy reutiliza o JWT curto do backend durante sua validade e, quando
necessário, renova o Google ID token com o refresh token da sessão OAuth.
Se a renovação falhar ou o refresh token for revogado, entre novamente.

Cada conversa da UI mantém o `session_id` devolvido pelo AgentOS nos turnos
seguintes; **New Chat** limpa esse identificador e inicia outra sessão. O
agente usa o histórico recente para interpretar referências curtas na mesma
conversa e pede esclarecimento quando houver mais de uma interpretação relevante.

O `agent-ui/README.md` é documentação upstream para Agno v2; para instalar e
conectar o Kapo, siga as instruções deste README. Esta integração usa AgentOS
v3.0.11; os testes locais verificam o isolamento de sessões, e a compatibilidade
de login e streaming deve ser validada no host após configurar as credenciais
Google. Repita a validação ao atualizar a UI ou o SDK.

Para conectar o serviço ao Agno OS em `os.agno.com`, publique o AgentOS em um
endereço HTTPS acessível pela internet (por exemplo, atrás de um proxy reverso com
TLS) e cadastre esse endereço no OS. O OS emite JWTs RS256; a chave de verificação
pública obtida nas configurações do OS precisa estar no arquivo configurado por
`AGNO_OS_JWT_PUBLIC_KEY_FILE`. O runtime deixa a autorização por escopos do Agno
verificar esses JWTs. `AGNO_QA_HOST=0.0.0.0` permite que o processo receba tráfego
de rede, mas a publicação HTTPS/firewall continua sendo responsabilidade do host.
A UI local continua usando `AGENTOS_URL=http://127.0.0.1:7777`.

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
Após uma atualização bem-sucedida, a data UTC da sincronização é registrada em
`repositorios/.ultima-sincronizacao-producao` (não versionado).
Veja `MELHORIAS.md` para a análise das melhorias realizadas.
