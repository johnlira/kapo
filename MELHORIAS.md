# Oportunidades de melhoria

## Situação da implementação

As propostas 1–7 foram aplicadas no código: autenticação Google restrita por domínio/e-mail, isolamento de sessões pelo Agno, busca com indicadores de completude, leitura incremental por intervalo, identificação de clones homônimos, validação do catálogo, testes independentes dos clones e documentação atualizada. O cache do catálogo não foi adicionado: a medição local da leitura (~0,022 s) não indicou gargalo. A busca continua lendo arquivos elegíveis de até 512 KB por inteiro para preservar o ranking; antes de otimizá-la, é necessário medir nos clones do host de uso. O login Google e o streaming no host precisam de uma validação operacional com as credenciais OAuth reais.

Análise do estado atual do repositório (27/09/2026). O projeto já usa ferramentas nativas do Agno, limita volume de resultados e leitura, preserva histórico em SQLite e tem testes de busca e sessões. As propostas abaixo priorizam correções localizadas antes de novas abstrações.

## Prioridade alta

### 1. Definir claramente o limite de acesso à API

**Evidência:** `app/main.py:28-33` inicia o servidor em `0.0.0.0`, com `reload=True`; `app/main.py:45-49` expõe AgentOS com histórico e tracing no banco, e `README.md:59-64` informa que a UI não autentica nem envia `user_id` por padrão. Assim, a configuração local não estabelece isolamento de usuários nem restringe a API ao próprio computador.

**Ação:** para uso estritamente local, tornar o endereço de escuta configurável com padrão `127.0.0.1` e deixar `reload` reservado ao desenvolvimento. Antes de disponibilizar o serviço na rede, validar autenticação e separação do histórico por usuário com os mecanismos do AgentOS; documentar o modo de acesso escolhido. **Critério:** o padrão não escuta em interfaces externas; um cenário multiusuário só é habilitado após teste de acesso ao histórico entre usuários.

### 2. Corrigir a indicação de busca completa no limite de arquivos

**Evidência:** `app/sources.py:189-191,238-248` para após 5.000 arquivos lidos, mas calcula `scan_complete = files_checked < max_files_checked`. Ao atingir exatamente 5.000 no último arquivo, a resposta informa investigação incompleta mesmo quando não restam arquivos. Além disso, arquivos descartados por tamanho/extensão não entram nessa contagem (`app/sources.py:196-205`), e a resposta não mostra quantos foram omitidos; a busca tampouco pode confirmar ausência de ocorrências nesses arquivos.

**Ação:** distinguir limite atingido, arquivos examinados e arquivos ignorados; marcar a varredura incompleta somente quando efetivamente restarem candidatos não verificados. Manter o aviso de resultados truncados separado do aviso de varredura parcial. **Critério:** testes com 4.999, 5.000 e 5.001 arquivos e com arquivo grande confirmam os indicadores exibidos ao agente.

### 3. Evitar leitura integral de arquivos quando só se pede um trecho

**Evidência:** `read_repository_paths` lê o arquivo inteiro antes de selecionar linhas e só então limita a resposta a 12 KB (`app/sources.py:528-545`); a busca também lê cada arquivo elegível inteiro e analisa todas as linhas antes de montar até dez resultados (`app/sources.py:199-245`). Apesar do limite de 512 KB por arquivo na busca, percorrer muitos arquivos ainda pode custar tempo; ler um arquivo grande para retornar poucas linhas consome memória desnecessária.

**Ação:** medir tempo das buscas representativas e, se o custo justificar, ler intervalos solicitados de forma incremental; na busca, manter os limites atuais e evitar trabalho que não afete o ranking final. **Critério:** comparação de tempo e memória antes/depois em clones locais, mantendo os resultados dos testes de relevância.

## Prioridade média

### 4. Tratar nomes duplicados de projetos no inventário

**Evidência:** `_project_directories` indexa clones apenas por `project.name` (`app/sources.py:73-83`), e `_project_path` escolhe o primeiro projeto com esse nome em qualquer grupo (`app/sources.py:86-96`). Um mesmo nome em `front/` e `back/` sobrescreve o inventário ou torna a escolha dependente da ordem de diretórios.

**Ação:** detectar colisões e exigir identificação inequívoca (`grupo/projeto`) quando ocorrerem, preservando nomes simples quando únicos. **Critério:** teste com dois grupos contendo o mesmo nome retorna ambos no inventário e nunca lê o clone errado.

### 5. Garantir atualidade e validade do catálogo funcional

**Evidência:** `data/funcionalidades.json` tem mais de 20 mil linhas e localizações que o próprio cabeçalho classifica como pistas; `search_functionality_catalog` lê e decodifica tudo em cada chamada (`app/sources.py:325-326`) e devolve até 15 itens sem indicar quantos ficaram de fora (`app/sources.py:475-483`).

**Ação:** acrescentar uma verificação leve de formato e referências do catálogo aos testes, além de registrar quando os clones de `producao` foram sincronizados. Se houver lentidão mensurável, cachear a leitura com invalidação por alteração do arquivo. **Critério:** entradas inválidas e caminhos de projeto inexistentes são identificados antes de uso; respostas de catálogo indicam truncamento quando aplicável.

### 6. Aumentar a confiabilidade dos testes sem depender dos clones locais

**Evidência:** `tests/test_totem_repository.py:11-55` usa `quarkclinic-gng` e um arquivo real sob `repositorios/`, enquanto `.gitignore:13-14` exclui os clones do versionamento. A suíte passa neste ambiente, mas uma instalação limpa sem clones falha nesses testes.

**Ação:** criar fixtures pequenas para validar busca de frases e leitura por intervalo; deixar as verificações sobre clones reais como teste de integração opcional, com pré-requisito explícito. **Critério:** `python -m unittest discover -s tests -v` passa após instalação sem `repositorios/` populado; a integração pode ser executada separadamente após clonar.

### 7. Alinhar documentação e configuração operacional

**Evidência:** `README.md:87` aponta para `docs/etapa-0.md`, que está removido no diretório de trabalho; `agent-ui/README.md:18-21` descreve suporte principal a Agno v2 enquanto `README.md:66-69` registra validação local com v3. Há ainda instruções extensas quase duplicadas em `.agents/AGENTS.md` e `app/agent_instructions.md`.

**Ação:** corrigir o link após decidir o destino do documento removido, indicar no README principal qual guia da UI é upstream e qual combinação foi efetivamente verificada, e manter as instruções do agente em uma fonte clara de manutenção. **Critério:** links locais resolvem e a documentação de inicialização corresponde ao ambiente efetivo.

## Verificação

- `.venv/bin/python -m unittest discover -s tests -v`: **28 testes passaram**, incluindo isolamento entre usuários e catálogo, sem exigir clones nos testes unitários.
- `pnpm run typecheck` e `pnpm run build` em `agent-ui/`: concluídos com sucesso.
- Integração com Google OAuth real e streaming pelo host da VPN: requer configuração das credenciais e teste no ambiente de implantação.
- Alterações preexistentes observadas: remoção de `docs/analise-consumo-tokens-e-melhorias.md` e `docs/etapa-0.md`. Este documento não altera esses arquivos.
