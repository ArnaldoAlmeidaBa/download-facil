# Orquestrador de Downloads

Sistema para analisar arquivos, identificar seu tipo documental, sugerir assunto e destino e gerar um painel HTML para revisão humana.

## Estado atual

A versão de trabalho é [`orquestrador.py`](orquestrador.py). O sistema funciona em modo seguro/dry-run: analisa e registra sugestões, mas não move arquivos automaticamente.

## Funcionalidades

- Leitura de arquivos TXT, DOCX, PDF, XLS/XLSX e PPTX.
- Extração de texto e metadados básicos.
- Classificação do tipo documental e do assunto.
- Cálculo de confiança e registro das evidências utilizadas.
- Sugestão de território e destino.
- Geração do painel visual [`painel.html`](painel.html).
- Registro das análises em arquivos CSV na pasta [`logs/`](logs/).

## Estrutura

```text
.
├── orquestrador.py              # versão de trabalho
├── orquestrador_v*.py           # versões históricas
├── painel.html                  # painel gerado
├── logs/                        # registros CSV das análises
├── DIARIO_DESENVOLVIMENTO.md    # contexto e histórico de desenvolvimento
└── README.md                    # documentação geral
```

## Dependências

O código utiliza principalmente:

- `python-docx`
- `pypdf`
- `openpyxl`
- `xlrd`
- `python-pptx`

As dependências devem ser instaladas no ambiente Python utilizado para executar o projeto.

## Execução

```bash
python orquestrador.py
```

O programa analisa os arquivos da pasta de entrada configurada no código, registra as decisões e gera o painel HTML.

## Fluxo de funcionamento

1. Localiza os arquivos de entrada.
2. Extrai o conteúdo conforme o formato.
3. Classifica o tipo documental e o assunto.
4. Avalia possíveis destinos.
5. Registra evidências, confiança e pendências.
6. Gera o painel para revisão.

## Segurança e limitações

- O comportamento atual é dry-run; não há movimentação física automática.
- Casos sem evidência suficiente ficam aguardando decisão humana.
- Ainda não há suíte de testes automatizados nem arquivo de dependências consolidado.
- Existem várias versões históricas que precisam ser consolidadas em uma versão oficial.

## Histórico de versões

As versões anteriores estão preservadas nos arquivos `orquestrador_v*.py`. O histórico detalhado de decisões e sessões está em [`DIARIO_DESENVOLVIMENTO.md`](DIARIO_DESENVOLVIMENTO.md).

## Próximos passos sugeridos

- Validar e corrigir o ambiente de execução Python.
- Consolidar a versão oficial.
- Criar testes automatizados.
- Adicionar um arquivo de dependências.
- Melhorar a identificação segura de destinos.
