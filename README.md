# Orquestrador de Downloads

Sistema inteligente para analisar arquivos, identificar seu tipo documental, sugerir assunto e destino, gerar painel de controle interativo e executar movimentações físicas seguras com rastreabilidade total.

## Estado Atual

- **Arquitetura:** Modular em pacotes sob `src/` (`readers`, `rules`, `logging`, `dashboard`, `actions`, `core`).
- **Ponto de entrada:** [`orquestrador.py`](orquestrador.py).
- **Modos operacionais:**
  1. **Análise / Dry-Run (Padrão):** Analisa e registra sugestões no CSV e gera o painel visual, sem mover nenhum arquivo.
  2. **Interativo / Servidor Local:** Inicia um microservidor HTTP local que conecta o painel no navegador com botões para mover em 1 clique e desfazer movimentações.
- **Testes Automatizados:** 59 testes unitários e de integração aprovados; EXP-02D.3 homologada pelo usuário, aguardando autorização para consolidação.

## Funcionalidades

- **Leitura multiformato:** TXT, DOCX, PDF, XLS/XLSX, PPTX e imagens com preview Base64.
- **Classificação heurística:** Identificação de tipo documental (TCC, Matriz, Sumário) e de assunto (Ofício SEC, Planejamento Pedagógico, Lista de Alunos, Identidade Visual).
- **Cálculo de confiança:** Níveis ALTA, MÉDIA e BAIXA, com rastreio de evidências e identificação de conflitos.
- **Território documental:** Sugestão segura de pastas governadas por contexto.
- **Painel interativo:** [`painel.html`](painel.html) moderno, com filtros, modal de visualização e botões de ação física direta.
- **Estado operacional:** O painel reconcilia registros com snapshots dos arquivos ao ser aberto e antes de operações. Movimentações e reversões atualizam estados e contadores sem reanálise completa.
- **Movimentação segura:** Nunca sobrescreve arquivos (resolução automática de colisão com `_1`, `_2`), registra logs de movimentação e permite desfazer (*Undo*).
- **Auditoria contínua:** Registros estruturados em CSV na pasta [`logs/`](logs/).

## Estrutura do Projeto

```text
.
├── orquestrador.py          # Ponto de entrada CLI
├── painel.html              # Painel HTML gerado
├── perfil.json              # Configuração de perfil e território
├── requirements.txt         # Dependências consolidadas
├── pytest.ini               # Configuração da suíte de testes
├── src/                     # Código-fonte modular
│   ├── config.py            # Configurações, caminhos e resiliência de perfil
│   ├── core.py              # Motor de varredura e análise
│   ├── server.py            # Servidor HTTP local para interatividade
│   ├── readers/             # Extratores por formato (PDF, DOCX, XLSX, PPTX, etc.)
│   ├── rules/               # Normalizador, classificadores e território
│   ├── logging/             # Auditoria e gravação de logs CSV
│   ├── dashboard/           # Gerador do painel HTML e componentes visuais
│   └── actions/             # Motor de movimentação segura e reversão (Undo)
├── tests/                   # Suíte de testes automatizados com pytest
├── historico/               # Versões históricas arquivadas (v0.6 a v0.11.2.1)
├── logs/                    # Arquivos de log e auditoria CSV
└── DIARIO_DESENVOLVIMENTO.md
```

## Instalação

```bash
# Ativar o ambiente virtual
.venv\Scripts\activate

# Instalar dependências
pip install -r requirements.txt
```

## Execução

### 1. Varredura e Análise Segura (Dry-Run)
```bash
python orquestrador.py
```
Gera a análise de todos os arquivos, grava os registros em `logs/decisoes.csv` e abre o `painel.html` no navegador.

### 2. Modo Interativo Conectado (1 Clique para Mover / Desfazer)
```bash
python orquestrador.py --servidor
```
Executa a análise, abre o painel em `http://localhost:8080/` e permite que o usuário aprove as movimentações diretamente pelo navegador com segurança total.

### 3. Homologação Manual Isolada

O lançador [tools/homologacao/iniciar_homologacao.py](tools/homologacao/iniciar_homologacao.py) prepara e inicia um ambiente reutilizável de homologação. Ele usa um perfil exclusivo e não carrega o `perfil.json` do projeto nem o perfil do usuário.

No PowerShell, na raiz do repositório:

```powershell
& .\.venv\Scripts\python.exe .\tools\homologacao\iniciar_homologacao.py --porta 18080
```

O painel abre em `http://localhost:18080/`. Encerre o servidor com `Ctrl+C`. O servidor permanece limitado à interface local.

Os documentos fictícios, perfil, logs e painel são mantidos fora do Git em `C:\Projetos\orquestrador-downloads-homologacao\`:

- `entrada\`: PDF, TXT, DOCX, XLSX e PNG fictícios.
- `destino-revisao\` e `destino-arquivo\`: destinos autorizados pelo perfil de homologação.
- `perfil-homologacao.json`: perfil exclusivo, validado pelo lançador antes de cada execução.
- `logs\` e `artefatos\`: logs e painel gerados pelo aplicativo.

Use somente os arquivos fictícios desse ambiente; não copie documentos reais para a pasta de entrada. O lançador sinaliza o contexto de homologação ao servidor, que exibe o banner “AMBIENTE DE HOMOLOGACAO - SOMENTE DADOS FICTICIOS”, independentemente da porta escolhida. A EXP-02D.3 foi homologada pelo usuário e aguarda autorização para consolidação.

### 4. Execução dos Testes Automatizados
```bash
pytest
```
Executa a suíte automatizada do sistema.
