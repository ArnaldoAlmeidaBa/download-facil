# Diário de Desenvolvimento

Este arquivo preserva o contexto das decisões, alterações, problemas e próximos passos do projeto. Deve ser atualizado ao final de cada sessão relevante.

## Estado atual

- **Arquitetura:** Modular em pacotes sob `src/` (`core`, `readers`, `rules`, `logging`, `dashboard`, `actions`, `server`)
- **Ponto de entrada:** `orquestrador.py`
- **Painel:** `painel.html` com suporte a modo interativo (mover em 1 clique e desfazer)
- **Persistência:** arquivos CSV em `logs/` (`decisoes.csv`, `movimentacoes.csv`)
- **Modo operacional:** Dry-run por padrão; acionamento físico opcional via servidor local (`python orquestrador.py --servidor`)
- **Qualidade:** 24 testes automatizados com `pytest` (100% de aprovação)
- **Status:** Estável, modularizado, testado e com resiliência total de perfil

## Sessão — 2026-11-23 — Desbloqueio, Modularização, Testes e Interatividade

### Objetivo

Desbloquear a execução no usuário atual (`ALUNO - CETI`), eliminar pontos únicos de falha de configuração, arquivar versões históricas, modularizar o código-fonte, criar suíte de testes automatizados e implementar interatividade para movimentação segura.

### Atividades realizadas

- Corrigido o bloqueio crítico de `FileNotFoundError` ao carregar perfil: criada lógica com fallback automático (busca `%LOCALAPPDATA%`, `perfil.json` local ou gera padrão dinâmico).
- Provisionada a pasta `%LOCALAPPDATA%\Akira` e `Documents\Revisar` para o usuário `ALUNO - CETI`.
- Gerado o arquivo consolidado de dependências `requirements.txt` e configurado `pytest.ini`.
- Arquivados 10 arquivos legados `orquestrador_v*.py` na pasta `historico/`, limpando a raiz do repositório.
- Modularizada toda a base de código (~4.100 linhas monolíticas) em pacotes sob `src/`:
  - `src/config.py`: constantes, caminhos e carregamento tolerante a falhas.
  - `src/readers/`: extratores específicos para TXT, DOCX, PDF, XLSX, XLS, PPTX e previews de imagem/mídia.
  - `src/rules/`: normalização de strings, regras de tipo documental, assunto e território governado.
  - `src/logging/`: registro estruturado de auditoria em CSV.
  - `src/dashboard/`: gerador do painel HTML com botões interativos e toasts visuais.
  - `src/actions/`: motor de movimentação com resolução automática de colisões de nome (`_1`, `_2`) e pilha de reversão (*Undo*).
  - `src/server.py`: microservidor HTTP nativo local para servir o painel e processar comandos de movimentação/reversão.
  - `src/core.py`: motor orquestrador com suporte a CLI (`--servidor`, `--porta`, `--sem-navegador`).
- Criada suíte completa de testes unitários e de integração (`tests/`):
  - `test_normalizer.py`
  - `test_classifiers.py`
  - `test_territory.py`
  - `test_readers.py`
  - `test_logger.py`
  - `test_file_mover.py`
  - `test_dashboard.py`
- Executada a análise real de ponta a ponta sobre 63 arquivos da pasta de Downloads do usuário atual.

### Testes e validações

- `pytest`: 24 testes executados e 100% aprovados em 1.17s.
- `python orquestrador.py --sem-navegador`: Análise executada com sucesso sobre 63 arquivos reais, gerando `logs/decisoes.csv` e `painel.html`.

### Próximos passos

1. Adicionar regras universais de identificação para documentos civis (RG, CPF, CNH) e faturas financeiras.
2. Empacotar em executável desktop `.exe` para distribuição sem necessidade de Python.
3. Adicionar monitoramento em segundo plano com ícone na bandeja do sistema (System Tray).

## Sessão — 2026-09-09 — Preparação do ambiente da nova máquina

### Atividades realizadas

- Confirmada a ausência inicial de Python funcional no `PATH`.
- Instalado o Python 3.14.7.
- Recriado o ambiente virtual local `.venv`, pois o ambiente trazido da máquina anterior continha caminhos inválidos.
- Instaladas e validadas as bibliotecas `python-docx`, `pypdf`, `openpyxl`, `xlrd` e `python-pptx`.
- A compilação de `orquestrador.py` foi validada com sucesso.
- Criado o `perfil.json` inicial para a máquina `PC 02 - CETI`.
- Criada a pasta local `%LOCALAPPDATA%\\Akira` e copiado o perfil para `perfil.json`.
- Criada a pasta de revisão `C:\\Users\\PC 02 - CETI\\Documents\\Revisar`.
- Instalada a ferramenta Git for Windows; a disponibilidade no terminal ainda precisa ser confirmada após reiniciar o VSCode ou o Windows.

### Estado ao final da sessão

- Python e dependências: funcionando.
- Perfil do Akira: criado e encontrado.
- Execução do programa: pronta para novo teste.
- Git: instalado, mas o comando ainda não estava disponível no terminal aberto.

### Próximos passos

1. Abrir um novo terminal ou reiniciar o Windows e confirmar `git --version`.
2. Executar `python orquestrador.py`.
3. Conferir o painel gerado e os registros em `logs`.
4. Inicializar o repositório Git depois que o comando estiver disponível.

## Sessão — 2026-09-09 — Documentação inicial

### Objetivo

Registrar o estado do projeto e criar uma documentação permanente para preservar contexto entre sessões.

### Observações realizadas

- Não existiam arquivos `.md` nem `README.md` na raiz.
- Foram encontradas versões históricas de `orquestrador_v0_6.py` até `orquestrador_v0_11_2_1.py`.
- `orquestrador.py` contém o fluxo principal de análise e geração do painel.
- O projeto possui logs CSV em `logs/`, incluindo registros de análises reais.
- Os registros indicam operação em modo `NENHUMA — DRY-RUN` e uso de decisão humana quando o destino não é suficientemente seguro.
- A validação de compilação não foi concluída porque o executável Python configurado no ambiente está indisponível ou aponta para um caminho quebrado.
- O comando `git` não está disponível no ambiente atual.

### Arquivos criados

- `README.md` — documentação geral, execução, estrutura e limitações.
- `DIARIO_DESENVOLVIMENTO.md` — histórico e modelo de registro de sessões.

### Decisões

- Manter as versões históricas existentes até que uma versão oficial seja validada.
- Documentar explicitamente o comportamento dry-run para evitar a expectativa de movimentação automática.
- Usar este diário para registrar toda sessão que altere código, comportamento, configuração ou decisões do projeto.

### Próximos passos

1. Corrigir ou recriar o ambiente Python.
2. Identificar e registrar as dependências em um arquivo próprio.
3. Executar uma validação de sintaxe e um teste funcional.
4. Comparar as versões históricas e definir a versão oficial.
5. Criar testes automatizados para leitura, classificação, logging e geração do painel.

## Modelo para novas sessões

## Sessão — AAAA-MM-DD — Título

### Objetivo

Descrever o que se pretendia realizar.

### Atividades realizadas

-

### Arquivos alterados

- `arquivo` — descrição da alteração

### Decisões tomadas

- Decisão:
- Motivo:
- Impacto:

### Testes e validações

- Comando ou procedimento:
- Resultado:

### Problemas encontrados

- Problema:
- Situação:
- Próxima ação:

### Próximos passos

1.
2.
