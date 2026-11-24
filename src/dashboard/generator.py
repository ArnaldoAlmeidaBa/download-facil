"""Módulo gerador do painel HTML da Caixa de Entrada Documental."""
from pathlib import Path
from datetime import datetime
from html import escape
from src.config import PAINEL_FILE, rotulo, carregar_perfil
from src.document_access import identificador_destino
from src.rules.normalizer import normalizar

def classe_confianca(
    confianca: str
) -> str:

    mapa = {
        "ALTA": "alta",
        "MEDIA": "media",
        "BAIXA": "baixa",
    }

    return mapa.get(
        confianca,
        "neutra"
    )


def contar_tipo(
    registros: list[dict],
    tipo: str
) -> int:

    return sum(
        1
        for registro in registros
        if (
            registro["tipo_tecnico"] == tipo
            and registro["estado_ficha"]
            != "IGNORADO"
        )
    )


def contar_estado(registros: list[dict], estado: str) -> int:
    return sum(
        1
        for registro in registros
        if registro.get("estado_operacional", "AGUARDANDO_DECISAO_HUMANA") == estado
    )


def contar_movimentados(registros: list[dict]) -> int:
    return sum(
        1
        for registro in registros
        if registro.get("estado_operacional", "").startswith("MOVIDO")
    )


def contar_inconsistencias(registros: list[dict]) -> int:
    return sum(
        1
        for registro in registros
        if registro.get("estado_operacional", "AGUARDANDO_DECISAO_HUMANA")
        in {
            "AUSENTE_OU_RENOMEADO",
            "ALTERADO_EXTERNAMENTE",
            "SUBSTITUIDO_EXTERNAMENTE",
            "MOVIDO_AUSENTE",
            "MOVIDO_ALTERADO",
            "MOVIDO_SUBSTITUIDO",
            "MOVIDO_SEM_PREVIEW",
        }
    )


def gerar_html_preview(
    registro: dict,
    indice: int,
) -> str:

    preview = registro["preview"]

    nome = escape(
        registro["arquivo"]
    )

    tipo = preview["tipo"]

    if tipo == "pdf":
        corpo = f"""
        <iframe
            class="preview-pdf"
            src="{escape(preview['url'])}"
            title="Visualização de {nome}"
        ></iframe>
        """

    elif tipo == "imagem":
        corpo = f"""
        <div class="preview-imagem-area">
            <img
                class="preview-imagem"
                src="{preview['url']}"
                alt="Visualização de {nome}"
            >
        </div>
        """

    elif tipo == "audio":
        corpo = f"""
        <div class="preview-midia-area">
            <audio
                class="preview-audio"
                controls
                preload="metadata"
                src="{preview['url']}"
            >
                Seu navegador não conseguiu reproduzir este áudio.
            </audio>
        </div>
        """

    elif tipo == "video":
        corpo = f"""
        <div class="preview-midia-area">
            <video
                class="preview-video"
                controls
                preload="metadata"
                src="{preview['url']}"
            >
                Seu navegador não conseguiu reproduzir este vídeo.
            </video>
        </div>
        """

    elif tipo == "texto":
        corpo = f"""
        <pre class="preview-texto">{
            escape(preview["conteudo"])
        }</pre>
        """

    else:
        corpo = f"""
        <div class="preview-mensagem">
            {escape(preview["conteudo"])}
        </div>
        """

    return f"""
    <div
        class="preview-template"
        id="preview-{indice}"
        hidden
    >
        {corpo}
    </div>
    """


def gerar_painel_html(
    registros: list[dict],
    caminho_saida: Path = PAINEL_FILE,
    perfil: dict = None,
) -> Path:
    if perfil is None:
        perfil = carregar_perfil()

    visiveis = [
        registro
        for registro in registros
        if registro["estado_ficha"] != "IGNORADO"
    ]

    fichas = []
    previews = []

    for indice, registro in enumerate(
        visiveis,
        start=1
    ):

        nome = escape(
            registro["arquivo"]
        )

        caminho = escape(
            registro["caminho"]
        )

        tipo_tecnico = escape(
            registro["tipo_tecnico"]
        )

        extensao = escape(
            registro["extensao"]
            .upper()
            .replace(".", "")
        )

        tamanho = escape(
            registro["tamanho"]
        )

        data_modificacao = escape(
            registro["data_modificacao"]
        )

        tipo_arquivo_interface = escape(
            registro["tipo_arquivo"]
        )

        tipo_documental_interface = escape(
            "A identificar"
            if registro["tipo_documental"] in {
                "NAO_IDENTIFICADO",
                "NAO_APLICAVEL",
            }
            else rotulo(
                registro["tipo_documental"]
            )
        )

        assunto_interface = escape(
            "A identificar"
            if registro["assunto"] in {
                "NAO_IDENTIFICADO",
                "NAO_APLICAVEL",
            }
            else rotulo(
                registro["assunto"]
            )
        )

        confianca_tipo = escape(
            registro[
                "confianca_tipo_documental"
            ]
        )

        descricao = escape(
            registro["descricao"]
        )

        destino = escape(
            registro["destino_sugerido"]
            or "A definir"
        )

        if (
            registro["estado_destino"]
            == "SEM_DESTINO_SUFICIENTEMENTE_SEGURO"
        ):
            estado_destino_interface = (
                "Aguardando definição"
            )

        elif (
            registro["estado_destino"]
            == "DESTINO_EXISTENTE_SUGERIDO"
        ):
            estado_destino_interface = (
                "Destino sugerido"
            )

        else:
            estado_destino_interface = (
                "Não se aplica"
            )

        estado_destino = escape(
            estado_destino_interface
        )

        evidencias_destino = escape(
            registro["evidencias_destino"]
        )

        motivo_destino = escape(
            registro["motivo_destino"]
        )

        destino_legado = escape(
            registro["destino_legado"]
            or "Nenhum"
        )

        evidencias = escape(
            registro[
                "evidencias_tipo_documental"
            ]
        )

        estado_leitura = escape(
            registro["estado_leitura"]
        )

        motivo = escape(
            registro["motivo"]
        )

        classe = classe_confianca(
            registro[
                "confianca_tipo_documental"
            ]
        )

        busca = escape(
            normalizar(
                " ".join([
                    registro["arquivo"],
                    registro["tipo_tecnico"],
                    registro["tipo_arquivo"],
                    rotulo(
                        registro[
                            "tipo_documental"
                        ]
                    ),
                    rotulo(
                        registro["assunto"]
                    ),
                    registro["descricao"],
                    registro["destino_sugerido"],
                    registro["estado_destino"],
                    registro["evidencias_destino"],
                ])
            )
        )

        problema = (
            registro["tamanho_bytes"] == 0
            or registro[
                "estado_leitura"
            ].startswith(
                "ERRO_LEITURA"
            )
        )

        estado_operacional = registro.get(
            "estado_operacional",
            "AGUARDANDO_DECISAO_HUMANA",
        )
        rotulos_estado = {
            "AGUARDANDO_DECISAO_HUMANA": "Aguardando decisão",
            "MOVIDO": "Movimentado",
            "AUSENTE_OU_RENOMEADO": "Ausente ou renomeado — reanalise",
            "ALTERADO_EXTERNAMENTE": "Alterado externamente — reanalise",
            "SUBSTITUIDO_EXTERNAMENTE": "Substituído externamente — reanalise",
            "MOVIDO_AUSENTE": "Movido; arquivo ausente",
            "MOVIDO_ALTERADO": "Movido; arquivo alterado",
            "MOVIDO_SUBSTITUIDO": "Movido; arquivo substituído",
            "MOVIDO_SEM_PREVIEW": "Movido; preview indisponível",
        }
        estado_visual = rotulos_estado.get(
            estado_operacional,
            "Precisa de atenção" if problema else "Estado não reconhecido",
        )
        classe_status = (
            "status movimentado"
            if estado_operacional == "MOVIDO"
            else "status problema"
            if estado_operacional != "AGUARDANDO_DECISAO_HUMANA" or problema
            else "status"
        )

        revisar_padrao = str(Path.home() / "Documents" / "Revisar")
        destino_acao = registro.get("destino_caminho") or revisar_padrao
        id_arquivo = registro.get("id_arquivo")
        id_destino = identificador_destino(destino_acao)
        if (
            estado_operacional == "AGUARDANDO_DECISAO_HUMANA"
            and id_arquivo
            and id_destino
        ):
            classe_botao = (
                "btn-acao-mover"
                if registro.get("destino_caminho")
                else "btn-acao-revisar"
            )
            btn_acao_html = f"""
                    <button
                        type="button"
                        class="{classe_botao}"
                        data-arquivo-id="{escape(id_arquivo)}"
                        data-destino-id="{escape(id_destino)}"
                        onclick="moverArquivo(this)"
                    >
                        📁 Mover para {destino}
                    </button>
            """
        elif estado_operacional == "MOVIDO":
            btn_acao_html = """
                    <button
                        type="button"
                        class="btn-acao-sucesso"
                        disabled
                    >
                        ✓ Movido com Sucesso
                    </button>
            """
        else:
            btn_acao_html = f"""
                    <button
                        type="button"
                        class="btn-acao-revisar"
                        disabled
                        title="{escape(estado_visual)}"
                    >
                        Reanálise necessária
                    </button>
            """

        ficha = f"""
        <article
            class="ficha"
            data-busca="{busca}"
            data-tipo="{tipo_tecnico}"
            data-estado-operacional="{escape(estado_operacional)}"
        >

            <div class="ficha-topo">

                <div class="arquivo-area">

                    <div class="icone-arquivo">
                        {extensao or "ARQ"}
                    </div>

                    <div class="arquivo-texto">

                        <h2>
                            {nome}
                        </h2>

                        <div class="metadados">
                            {tipo_tecnico}
                            ·
                            {tamanho}
                            ·
                            {data_modificacao}
                        </div>

                        <div class="caminho">
                            {caminho}
                        </div>

                    </div>

                </div>


                <div class="acoes-topo">

                    {btn_acao_html}

                    <button
                        type="button"
                        class="visualizar"
                        data-preview="{indice}"
                        data-nome="{nome}"
                    >
                        Visualizar
                    </button>

                    <span class="{classe_status}">
                        {estado_visual}
                    </span>

                </div>

            </div>


            <div class="conteudo-ficha">

                <section class="coluna entendimento">

                    <h3>
                        O que chegou
                    </h3>

                    <div class="grade-entendimento">

                        <div class="campo">

                            <span>
                                Tipo de arquivo
                            </span>

                            <strong>
                                {tipo_arquivo_interface}
                            </strong>

                        </div>


                        <div class="campo">

                            <span>
                                Natureza
                            </span>

                            <strong>
                                {tipo_documental_interface}
                            </strong>

                        </div>


                        <div class="campo largura-total">

                            <span>
                                Tema
                            </span>

                            <strong>
                                {assunto_interface}
                            </strong>

                        </div>

                    </div>


                    <div class="descricao">

                        <span>
                            Em poucas palavras
                        </span>

                        <p>
                            {descricao}
                        </p>

                    </div>

                </section>


                <section class="coluna organizacao">

                    <h3>
                        Organização sugerida
                    </h3>

                    <div class="campo">

                        <span>
                            Pasta
                        </span>

                        <strong>
                            📁 {destino}
                        </strong>

                    </div>


                    <div class="campo">

                        <span>
                            Situação
                        </span>

                        <strong>
                            {estado_destino}
                        </strong>

                    </div>


                    <div class="campo">

                        <span>
                            Projeto
                        </span>

                        <strong>
                            Nenhum projeto vinculado
                        </strong>

                    </div>


                    <div class="nota">
                        {motivo_destino}
                    </div>

                </section>


                <section class="coluna detalhes">

                    <h3>
                        Detalhes
                    </h3>

                    <dl>

                        <div>
                            <dt>
                                Leitura
                            </dt>

                            <dd>
                                {estado_leitura}
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Evidências
                            </dt>

                            <dd>
                                {evidencias}
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Formato
                            </dt>

                            <dd>
                                {tipo_tecnico}
                                ({extensao or "-"})
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Tamanho
                            </dt>

                            <dd>
                                {tamanho}
                            </dd>
                        </div>


                        <div>
                            <dt>
                                Modificação
                            </dt>

                            <dd>
                                {data_modificacao}
                            </dd>
                        </div>

                    </dl>


                    <details>

                        <summary>
                            Ver análise técnica
                        </summary>

                        <p>
                            <strong>Confiança interna:</strong>
                            {confianca_tipo}
                        </p>

                        <p>
                            {motivo}
                        </p>

                        <p>
                            <strong>Destino — evidências:</strong>
                            {evidencias_destino}
                        </p>

                        <p>
                            <strong>Sugestão legada preservada
                            para rastreabilidade:</strong>
                            {destino_legado}
                        </p>

                    </details>

                </section>

            </div>


            <section class="decisao">

                <h3>
                    O que você quer fazer?
                </h3>

                <div class="botoes">

                    <button
                        class="principal"
                        disabled
                    >
                        ✓ Arquivar aqui
                    </button>

                    <button disabled>
                        Escolher outra pasta
                    </button>

                    <button disabled>
                        Criar pasta
                    </button>

                    <button disabled>
                        Vincular a projeto
                    </button>

                    <button disabled>
                        Editar informações
                    </button>

                    <button disabled>
                        Deixar para depois
                    </button>

                    <button
                        class="lixeira"
                        disabled
                    >
                        Enviar para lixeira
                    </button>

                </div>

            </section>

        </article>
        """

        fichas.append(
            ficha
        )

        previews.append(
            gerar_html_preview(
                registro,
                indice
            )
        )

    total = len(
        visiveis
    )

    documentos = contar_tipo(
        visiveis,
        "DOCUMENTO"
    )

    imagens = contar_tipo(
        visiveis,
        "IMAGEM"
    )

    planilhas = contar_tipo(
        visiveis,
        "PLANILHA"
    )

    apresentacoes = contar_tipo(
        visiveis,
        "APRESENTACAO"
    )

    compactados = contar_tipo(
        visiveis,
        "ARQUIVO_COMPACTADO"
    )

    instaladores = contar_tipo(
        visiveis,
        "INSTALADOR"
    )

    outros = (
        total
        - documentos
        - imagens
        - planilhas
        - apresentacoes
        - compactados
        - instaladores
    )
    aguardando = contar_estado(visiveis, "AGUARDANDO_DECISAO_HUMANA")
    movimentados = contar_movimentados(visiveis)
    inconsistencias = contar_inconsistencias(visiveis)

    gerado_em = datetime.now().strftime(
        "%d/%m/%Y às %H:%M"
    )

    usuario_interface = escape(
        perfil.get(
            "usuario_windows",
            "Usuário atual",
        )
    )

    entrada_configurada = next(
        (
            pasta
            for pasta in perfil.get(
                "pastas_entrada",
                [],
            )
            if pasta.get("monitorar", True)
            and pasta.get("caminho")
        ),
        {},
    )

    entrada_nome_interface = escape(
        entrada_configurada.get(
            "nome",
            "Entrada",
        )
    )

    entrada_caminho_interface = escape(
        str(
            entrada_configurada.get(
                "caminho",
                "Pasta de Entrada",
            )
        )
    )

    territorio = perfil.get("territorio_documental", [])
    destinos_conhecidos = [
        pasta
        for pasta in territorio
        if pasta.get("papel") == "DESTINO"
        and pasta.get(
            "pode_receber_arquivos",
            False,
        )
    ]

    destinos_nomes = [
        escape(
            str(
                pasta.get(
                    "nome",
                    pasta.get(
                        "caminho",
                        "Destino",
                    ),
                )
            )
        )
        for pasta in destinos_conhecidos
    ]

    destinos_interface = (
        ", ".join(destinos_nomes)
        if destinos_nomes
        else "Nenhum destino cadastrado"
    )

    total_destinos = len(
        destinos_conhecidos
    )

    html = f"""
<!DOCTYPE html>

<html lang="pt-BR">

<head>

<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>
    Caixa de Entrada Documental
</title>

<style>

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    font-family:
        Arial,
        Helvetica,
        sans-serif;
    background: #f5f7fa;
    color: #172033;
    line-height: 1.35;
}}

body.modal-aberto {{
    overflow: hidden;
}}

header {{
    height: 74px;
    background: #ffffff;
    border-bottom: 1px solid #dfe3e8;
    display: flex;
    align-items: center;
    padding: 0 20px;
}}

.cabecalho {{
    width: 100%;
    display: flex;
    justify-content: space-between;
    gap: 30px;
}}

.titulo-principal h1 {{
    margin: 0;
    font-size: 25px;
}}

.titulo-principal p {{
    margin: 3px 0 0;
    color: #667085;
    font-size: 14px;
}}

.modo {{
    text-align: right;
    font-size: 12px;
    color: #667085;
}}

.modo strong {{
    display: block;
    color: #344054;
}}

.contexto-perfil {{
    background: #f8fafc;
    border-bottom: 1px solid #dfe3e8;
    padding: 9px 20px;
    display: flex;
    flex-wrap: wrap;
    gap: 8px 18px;
    align-items: center;
    font-size: 12px;
    color: #475467;
}}

.contexto-perfil .item-perfil {{
    display: flex;
    gap: 5px;
    align-items: baseline;
    min-width: 0;
}}

.contexto-perfil .item-perfil span {{
    color: #667085;
}}

.contexto-perfil .item-perfil strong {{
    color: #344054;
    font-weight: 700;
    word-break: break-word;
}}

.contexto-perfil .caminho-perfil {{
    color: #98a2b3;
    font-weight: 400;
}}

.layout {{
    display: grid;
    grid-template-columns: 200px minmax(0, 1fr);
    min-height: calc(100vh - 74px);
}}

aside {{
    background: #ffffff;
    border-right: 1px solid #dfe3e8;
    padding: 18px 9px;
}}

aside h4 {{
    margin: 18px 8px 8px;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: .06em;
    color: #667085;
}}

.menu-item {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    min-height: 36px;
    padding: 7px 9px;
    border-radius: 7px;
    font-size: 14px;
    cursor: pointer;
}}

.menu-item:hover {{
    background: #f2f4f7;
}}

.menu-item.ativo {{
    background: #eef4ff;
    color: #155eef;
    font-weight: 700;
}}

.contagem {{
    min-width: 25px;
    text-align: center;
    background: #eef2f6;
    border-radius: 999px;
    padding: 2px 7px;
    font-size: 12px;
}}

.principal-area {{
    min-width: 0;
    padding: 16px 18px;
}}

.barra-superior {{
    display: grid;
    grid-template-columns: 1fr minmax(280px, 420px);
    gap: 18px;
    align-items: center;
    margin-bottom: 12px;
}}

.barra-superior h2 {{
    margin: 0;
    font-size: 20px;
}}

.barra-superior h2 span {{
    font-size: 13px;
    font-weight: 400;
    color: #667085;
    margin-left: 7px;
}}

.busca {{
    height: 38px;
    border: 1px solid #cfd5dd;
    border-radius: 9px;
    padding: 0 13px;
    font-size: 14px;
    background: #fff;
}}

.ficha {{
    background: #fff;
    border: 1px solid #d9dfe7;
    border-radius: 10px;
    margin-bottom: 11px;
    overflow: hidden;
}}

.ficha-topo {{
    padding: 10px 13px;
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 14px;
    border-bottom: 1px solid #e7eaf0;
}}

.arquivo-area {{
    display: flex;
    gap: 11px;
    min-width: 0;
}}

.icone-arquivo {{
    min-width: 42px;
    height: 42px;
    background: #eef4ff;
    border: 1px solid #c7d7fe;
    border-radius: 7px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: #155eef;
    font-size: 11px;
    font-weight: 800;
}}

.arquivo-texto {{
    min-width: 0;
}}

.arquivo-texto h2 {{
    margin: 0 0 2px;
    font-size: 16px;
    word-break: break-word;
}}

.metadados {{
    font-size: 12px;
    color: #667085;
}}

.caminho {{
    margin-top: 2px;
    font-size: 11px;
    color: #98a2b3;
    word-break: break-all;
}}

.acoes-topo {{
    display: flex;
    align-items: center;
    gap: 7px;
}}

.btn-acao-mover, .btn-acao-revisar {{
    border: 1px solid #155eef;
    background: #155eef;
    color: #ffffff;
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 11.5px;
    font-weight: 600;
    transition: background 0.15s;
}}

.btn-acao-revisar {{
    border-color: #475467;
    background: #475467;
}}

.btn-acao-mover:hover {{
    background: #175cd3;
}}

.btn-acao-revisar:hover {{
    background: #344054;
}}

.btn-acao-sucesso {{
    border: 1px solid #027a48 !important;
    background: #027a48 !important;
    color: #ffffff !important;
    border-radius: 6px;
    padding: 6px 10px;
    font-size: 11.5px;
    font-weight: 600;
}}

.btn-topo-interativo {{
    border: 1px solid #d0d5dd;
    background: #ffffff;
    color: #344054;
    border-radius: 6px;
    padding: 4px 10px;
    font-size: 11.5px;
    font-weight: 600;
    cursor: pointer;
    margin-left: 6px;
}}

.btn-topo-interativo:hover {{
    background: #f8fafc;
}}

.toast-notificacao {{
    position: fixed;
    bottom: 24px;
    right: 24px;
    background: #027a48;
    color: #ffffff;
    padding: 12px 20px;
    border-radius: 8px;
    box-shadow: 0 4px 14px rgba(0,0,0,0.18);
    font-size: 13px;
    font-weight: 600;
    z-index: 99999;
    display: none;
}}

.visualizar {{
    border: 1px solid #b7c5dd;
    background: #fff;
    color: #344054;
    border-radius: 6px;
    padding: 6px 10px;
    cursor: pointer;
    font-size: 11.5px;
}}

.visualizar:hover {{
    background: #f6f8fb;
}}

.status {{
    background: #fff4cc;
    border: 1px solid #f7dfa2;
    border-radius: 999px;
    padding: 4px 9px;
    font-size: 11px;
    color: #6d5200;
    white-space: nowrap;
}}

.status.problema {{
    background: #fee4e2;
    border-color: #fecdca;
    color: #b42318;
}}

.conteudo-ficha {{
    display: grid;
    grid-template-columns:
        minmax(360px, 1.25fr)
        minmax(230px, .72fr)
        minmax(280px, .88fr);
}}

.coluna {{
    padding: 9px 11px;
    min-width: 0;
}}

.coluna + .coluna {{
    border-left: 1px solid #e7eaf0;
}}

.coluna h3 {{
    font-size: 14px;
    margin: 0 0 7px;
}}

.grade-entendimento {{
    display: grid;
    grid-template-columns: 2fr .72fr;
    gap: 7px;
}}

.largura-total {{
    grid-column: 1 / -1;
}}

.campo {{
    background: #f7f8fa;
    border-radius: 6px;
    padding: 7px 9px;
}}

.campo span,
.descricao span {{
    display: block;
    font-size: 11px;
    color: #667085;
    margin-bottom: 2px;
}}

.campo strong {{
    font-size: 13px;
    word-break: break-word;
}}

.descricao {{
    margin-top: 7px;
    background: #f7f8fa;
    border-radius: 6px;
    padding: 7px 9px;
}}

.descricao p {{
    margin: 2px 0 0;
    font-size: 12.5px;
    line-height: 1.38;
}}

.confianca {{
    display: inline-block;
    border-radius: 5px;
    padding: 2px 6px;
}}

.alta {{
    background: #d1fadf;
    color: #05603a;
}}

.media {{
    background: #fff3c7;
    color: #7a4f01;
}}

.baixa {{
    background: #fee4e2;
    color: #b42318;
}}

.status.movimentado {{
    background: #d1fadf;
    color: #05603a;
}}

.organizacao .campo {{
    margin-bottom: 7px;
}}

.nota {{
    background: #eef4ff;
    color: #175cd3;
    padding: 8px 9px;
    border-radius: 6px;
    font-size: 11.5px;
}}

dl {{
    margin: 0;
}}

dl > div {{
    display: grid;
    grid-template-columns: 105px 1fr;
    gap: 7px;
    padding: 4px 0;
    border-bottom: 1px solid #edf0f3;
    font-size: 11.5px;
}}

dt {{
    color: #667085;
}}

dd {{
    margin: 0;
    word-break: break-word;
}}

details {{
    margin-top: 7px;
    font-size: 11.5px;
}}

summary {{
    cursor: pointer;
    font-weight: 600;
}}

details p {{
    color: #667085;
}}

.decisao {{
    border-top: 1px solid #e7eaf0;
    padding: 7px 11px 9px;
}}

.decisao h3 {{
    font-size: 13px;
    margin: 0 0 6px;
}}

.botoes {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
}}

button {{
    min-height: 31px;
    padding: 6px 10px;
    border: 1px solid #cfd5dd;
    border-radius: 6px;
    background: #fff;
    color: #667085;
    font-size: 11.5px;
}}

button:disabled {{
    opacity: .75;
    cursor: not-allowed;
}}

button.principal {{
    background: #155eef;
    border-color: #155eef;
    color: #fff;
}}

button.lixeira {{
    margin-left: auto;
    border-color: #fda29b;
    color: #d92d20;
}}

.sem-resultados {{
    display: none;
    padding: 35px;
    text-align: center;
    color: #667085;
}}

footer {{
    padding: 4px 0 18px;
    text-align: center;
    color: #98a2b3;
    font-size: 11px;
}}


/* ========================================================
   MODAL
   ======================================================== */

.modal {{
    position: fixed;
    inset: 0;
    background: rgba(20, 27, 40, .58);
    display: none;
    align-items: center;
    justify-content: center;
    padding: 22px;
    z-index: 9999;
}}

.modal.aberto {{
    display: flex;
}}

.modal-caixa {{
    width: min(1280px, 96vw);
    height: min(850px, 92vh);
    background: #fff;
    border-radius: 11px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
}}

.modal-topo {{
    min-height: 54px;
    padding: 10px 14px;
    border-bottom: 1px solid #e3e6eb;
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 15px;
}}

.modal-titulo-area {{
    min-width: 0;
}}

.modal-titulo {{
    margin: 0;
    font-size: 16px;
    word-break: break-word;
}}

.modal-subtitulo {{
    font-size: 11.5px;
    color: #667085;
}}

.modal-fechar {{
    border: 1px solid #cfd5dd;
    background: #fff;
    color: #344054;
    border-radius: 6px;
    min-width: 72px;
    cursor: pointer;
}}

.modal-conteudo {{
    flex: 1;
    min-height: 0;
    background: #eef1f5;
    padding: 12px;
}}

.modal-documento {{
    height: 100%;
    background: #fff;
    border: 1px solid #d8dde5;
    border-radius: 7px;
    overflow: auto;
}}

.preview-pdf {{
    display: block;
    width: 100%;
    height: 100%;
    border: 0;
}}

.preview-imagem-area {{
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 22px;
}}

.preview-imagem {{
    display: block;
    max-width: 100%;
    max-height: 720px;
    width: auto;
    height: auto;
    object-fit: contain;
}}

.preview-midia-area {{
    min-height: 100%;
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 28px;
}}

.preview-audio {{
    width: min(760px, 100%);
}}

.preview-video {{
    display: block;
    width: min(960px, 100%);
    max-height: 720px;
}}

.preview-texto {{
    margin: 0;
    padding: 28px 34px;
    white-space: pre-wrap;
    word-break: break-word;
    font-family:
        Arial,
        Helvetica,
        sans-serif;
    font-size: 14px;
    line-height: 1.55;
    color: #222;
}}

.preview-mensagem {{
    padding: 40px;
    font-size: 15px;
    color: #667085;
}}


@media (
    max-width: 1100px
) {{

    .layout {{
        grid-template-columns: 1fr;
    }}

    aside {{
        display: none;
    }}

    .conteudo-ficha {{
        grid-template-columns: 1fr 1fr;
    }}

    .detalhes {{
        grid-column: 1 / -1;
        border-left: 0 !important;
        border-top: 1px solid #e7eaf0;
    }}
}}


@media (
    max-width: 720px
) {{

    .principal-area {{
        padding: 10px;
    }}

    .barra-superior {{
        grid-template-columns: 1fr;
    }}

    .conteudo-ficha {{
        grid-template-columns: 1fr;
    }}

    .coluna + .coluna {{
        border-left: 0;
        border-top: 1px solid #e7eaf0;
    }}

    .detalhes {{
        grid-column: auto;
    }}

    .grade-entendimento {{
        grid-template-columns: 1fr;
    }}

    .largura-total {{
        grid-column: auto;
    }}

    button.lixeira {{
        margin-left: 0;
    }}

    .modo {{
        display: none;
    }}

    .acoes-topo {{
        flex-direction: column;
        align-items: flex-end;
    }}

    .modal {{
        padding: 6px;
    }}

    .modal-caixa {{
        width: 100%;
        height: 92vh;
    }}

    .preview-texto {{
        padding: 18px;
    }}
}}

</style>

</head>


<body>

<header>

    <div class="cabecalho">

        <div class="titulo-principal">

            <h1>
                Caixa de Entrada Documental
            </h1>

            <p>
                Arquivos recebidos e analisados.
                A decisão continua sendo sua.
            </p>

        </div>


        <div class="modo">

            <strong>
                Painel de Triagem Documental
            </strong>

            Atualizado em {gerado_em}

            <div style="margin-top: 6px;">
                <button type="button" class="btn-topo-interativo" id="btn-reanalisar" onclick="reanalisarPasta()">🔄 Reanalisar</button>
                <button type="button" class="btn-topo-interativo" id="btn-desfazer" onclick="desfazerAcao()">↩ Desfazer Ação</button>
            </div>

        </div>

    </div>

</header>

<div class="contexto-perfil">

    <div class="item-perfil">
        <span>Perfil:</span>
        <strong>{usuario_interface}</strong>
    </div>

    <div class="item-perfil">
        <span>Entrada observada:</span>
        <strong>{entrada_nome_interface}</strong>
        <span class="caminho-perfil">
            {entrada_caminho_interface}
        </span>
    </div>

    <div class="item-perfil">
        <span>Destinos conhecidos:</span>
        <strong>{total_destinos}</strong>
        <span>{destinos_interface}</span>
    </div>

</div>


<div class="layout">


<aside>

    <div
        class="menu-item ativo filtro"
        data-filtro="TODOS"
    >
        <span>Todos</span>
        <span class="contagem">{total}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="DOCUMENTO"
    >
        <span>Documentos</span>
        <span class="contagem">{documentos}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="IMAGEM"
    >
        <span>Imagens</span>
        <span class="contagem">{imagens}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="PLANILHA"
    >
        <span>Planilhas</span>
        <span class="contagem">{planilhas}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="APRESENTACAO"
    >
        <span>Apresentações</span>
        <span class="contagem">{apresentacoes}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="ARQUIVO_COMPACTADO"
    >
        <span>Compactados</span>
        <span class="contagem">{compactados}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="INSTALADOR"
    >
        <span>Instaladores</span>
        <span class="contagem">{instaladores}</span>
    </div>

    <div
        class="menu-item filtro"
        data-filtro="OUTRO"
    >
        <span>Outros</span>
        <span class="contagem">{outros}</span>
    </div>


    <h4>
        Estado
    </h4>

    <div
        class="menu-item filtro-estado ativo"
        data-filtro-estado="TODOS"
    >
        <span>Todos os estados</span>
        <span class="contagem">{total}</span>
    </div>

    <div
        class="menu-item filtro-estado"
        data-filtro-estado="AGUARDANDO_DECISAO_HUMANA"
    >
        <span>Aguardando decisão</span>
        <span class="contagem" data-contagem-estado="AGUARDANDO_DECISAO_HUMANA">{aguardando}</span>
    </div>

    <div
        class="menu-item filtro-estado"
        data-filtro-estado="MOVIDO"
    >
        <span>Movimentados</span>
        <span class="contagem" data-contagem-estado="MOVIDO">{movimentados}</span>
    </div>

    <div
        class="menu-item filtro-estado"
        data-filtro-estado="INCONSISTENCIAS"
    >
        <span>Inconsistências</span>
        <span class="contagem" data-contagem-estado="INCONSISTENCIAS">{inconsistencias}</span>
    </div>

</aside>


<section class="principal-area">


    <div class="barra-superior">

        <h2>
            Todos os arquivos

            <span>
                {total} arquivo(s)
            </span>
        </h2>


        <input
            id="busca"
            class="busca"
            type="search"
            placeholder="Buscar por nome, tema, tipo ou destino..."
        >

    </div>


    <main id="lista-fichas">

        {"".join(fichas)}

        <div
            id="sem-resultados"
            class="sem-resultados"
        >
            Nenhum arquivo corresponde
            aos filtros atuais.
        </div>

    </main>


    <footer>
        Caixa de Entrada Documental · V0.10
    </footer>

</section>

</div>


<div
    id="modal"
    class="modal"
    role="dialog"
    aria-modal="true"
    aria-labelledby="modal-titulo"
>

    <div class="modal-caixa">

        <div class="modal-topo">

            <div class="modal-titulo-area">

                <h2
                    id="modal-titulo"
                    class="modal-titulo"
                >
                    Visualizar arquivo
                </h2>

                <div class="modal-subtitulo">
                    Pré-visualização dentro do painel
                </div>

            </div>


            <button
                id="modal-fechar"
                class="modal-fechar"
                type="button"
            >
                Fechar
            </button>

        </div>


        <div class="modal-conteudo">

            <div
                id="modal-documento"
                class="modal-documento"
            ></div>

        </div>

    </div>

</div>


<div hidden>
    {"".join(previews)}
</div>


<script>

const busca =
    document.getElementById("busca");

const fichas = Array.from(
    document.querySelectorAll(".ficha")
);

const filtros = Array.from(
    document.querySelectorAll(".filtro")
);

const filtrosEstado = Array.from(
    document.querySelectorAll(".filtro-estado")
);

const semResultados =
    document.getElementById(
        "sem-resultados"
    );

const modal =
    document.getElementById("modal");

const modalDocumento =
    document.getElementById(
        "modal-documento"
    );

const modalTitulo =
    document.getElementById(
        "modal-titulo"
    );

const modalFechar =
    document.getElementById(
        "modal-fechar"
    );

let filtroAtual = "TODOS";
let filtroEstadoAtual = "TODOS";


function normalizarTexto(texto) {{
    return texto
        .normalize("NFD")
        .replace(
            /[\\u0300-\\u036f]/g,
            ""
        )
        .toLowerCase()
        .trim();
}}


function aplicarFiltros() {{

    const termo = normalizarTexto(
        busca.value
    );

    let visiveis = 0;

    fichas.forEach(
        ficha => {{

            const texto =
                normalizarTexto(
                    ficha.dataset.busca || ""
                );

            const tipo =
                ficha.dataset.tipo || "";

            const estado =
                ficha.dataset.estadoOperacional || "";

            const correspondeBusca =
                !termo ||
                texto.includes(termo);

            const correspondeTipo =
                filtroAtual === "TODOS" ||
                tipo === filtroAtual ||
                (
                    filtroAtual === "OUTRO" &&
                    ![
                        "DOCUMENTO",
                        "IMAGEM",
                        "PLANILHA",
                        "APRESENTACAO",
                        "ARQUIVO_COMPACTADO",
                        "INSTALADOR"
                    ].includes(tipo)
                );

            const correspondeEstado =
                filtroEstadoAtual === "TODOS" ||
                estado === filtroEstadoAtual ||
                (
                    filtroEstadoAtual === "MOVIDO" &&
                    estado.startsWith("MOVIDO_")
                ) ||
                (
                    filtroEstadoAtual === "INCONSISTENCIAS" &&
                    estado !== "AGUARDANDO_DECISAO_HUMANA" &&
                    estado !== "MOVIDO"
                );

            const mostrar =
                correspondeBusca &&
                correspondeTipo &&
                correspondeEstado;

            ficha.style.display =
                mostrar
                ? ""
                : "none";

            if (mostrar) {{
                visiveis += 1;
            }}

        }}
    );

    semResultados.style.display =
        visiveis === 0
        ? "block"
        : "none";
}}


function salvarFiltros() {{
    try {{
        sessionStorage.setItem(
            "download-facil-filtros",
            JSON.stringify({{
                tipo: filtroAtual,
                estado: filtroEstadoAtual,
                busca: busca.value
            }})
        );
    }} catch (e) {{}}
}}

function restaurarFiltros() {{
    try {{
        const salvo = sessionStorage.getItem("download-facil-filtros");
        if (!salvo) return;
        const filtrosSalvos = JSON.parse(salvo);
        const filtroTipo = filtros.find(
            item => item.dataset.filtro === filtrosSalvos.tipo
        );
        const filtroEstado = filtrosEstado.find(
            item => item.dataset.filtroEstado === filtrosSalvos.estado
        );

        if (filtroTipo) {{
            filtros.forEach(item => item.classList.remove("ativo"));
            filtroTipo.classList.add("ativo");
            filtroAtual = filtroTipo.dataset.filtro;
        }}
        if (filtroEstado) {{
            filtrosEstado.forEach(item => item.classList.remove("ativo"));
            filtroEstado.classList.add("ativo");
            filtroEstadoAtual = filtroEstado.dataset.filtroEstado;
        }}
        if (typeof filtrosSalvos.busca === "string") {{
            busca.value = filtrosSalvos.busca;
        }}
    }} catch (e) {{
        try {{
            sessionStorage.removeItem("download-facil-filtros");
        }} catch (erro) {{}}
    }}
}}


function abrirModal(
    indice,
    nome
) {{

    const template =
        document.getElementById(
            "preview-" + indice
        );

    if (!template) {{
        return;
    }}

    modalDocumento.innerHTML =
        template.innerHTML;

    modalTitulo.textContent =
        nome;

    modal.classList.add(
        "aberto"
    );

    document.body.classList.add(
        "modal-aberto"
    );

    modalFechar.focus();
}}


function fecharModal() {{

    modal.classList.remove(
        "aberto"
    );

    document.body.classList.remove(
        "modal-aberto"
    );

    modalDocumento.innerHTML = "";
}}


busca.addEventListener(
    "input",
    aplicarFiltros
);


filtros.forEach(
    filtro => {{

        filtro.addEventListener(
            "click",
            () => {{

                filtros.forEach(
                    item =>
                        item.classList.remove(
                            "ativo"
                        )
                );

                filtro.classList.add(
                    "ativo"
                );

                filtroAtual =
                    filtro.dataset.filtro;

                aplicarFiltros();

            }}
        );

    }}
);


filtrosEstado.forEach(
    filtro => {{
        filtro.addEventListener(
            "click",
            () => {{
                filtrosEstado.forEach(
                    item => item.classList.remove("ativo")
                );
                filtro.classList.add("ativo");
                filtroEstadoAtual = filtro.dataset.filtroEstado;
                aplicarFiltros();
            }}
        );
    }}
);

restaurarFiltros();
aplicarFiltros();


document
    .querySelectorAll(
        ".visualizar"
    )
    .forEach(
        botao => {{

            botao.addEventListener(
                "click",
                () => {{

                    abrirModal(
                        botao.dataset.preview,
                        botao.dataset.nome
                    );

                }}
            );

        }}
    );


modalFechar.addEventListener(
    "click",
    fecharModal
);


modal.addEventListener(
    "click",
    evento => {{

        if (evento.target === modal) {{
            fecharModal();
        }}

    }}
);


document.addEventListener(
    "keydown",
    evento => {{

        if (
            evento.key === "Escape"
            &&
            modal.classList.contains(
                "aberto"
            )
        ) {{
            fecharModal();
        }}

    }}
);

function obterTokenCSRF() {{
    const meta = document.querySelector('meta[name="csrf-token"]');
    return meta ? meta.content : "";
}}

async function moverArquivo(btn) {{
    const arquivoId = btn.getAttribute("data-arquivo-id");
    const destinoId = btn.getAttribute("data-destino-id");
    if (!arquivoId || !destinoId) return;

    const textoOriginal = btn.innerText;
    btn.disabled = true;
    btn.innerText = "Movendo...";

    try {{
        const resp = await fetch("/api/mover", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
                "X-CSRF-Token": obterTokenCSRF()
            }},
            body: JSON.stringify({{arquivo_id: arquivoId, destino_id: destinoId}})
        }});
        const dados = await resp.json();
        if (resp.ok && dados.sucesso) {{
            salvarFiltros();
            location.reload();
        }} else {{
            btn.disabled = false;
            btn.innerText = textoOriginal;
            alert("Não foi possível mover: " + (dados.erro || "Erro"));
            if (dados.estado_operacional) {{
                salvarFiltros();
                location.reload();
            }}
        }}
    }} catch (e) {{
        btn.disabled = false;
        btn.innerText = textoOriginal;
        alert("O servidor do painel não está ativo em segundo plano.\\nPara mover arquivos com 1 clique, execute:\\npython orquestrador.py --servidor");
    }}
}}

async function desfazerAcao() {{
    try {{
        const resp = await fetch("/api/desfazer", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
                "X-CSRF-Token": obterTokenCSRF()
            }},
            body: JSON.stringify({{}})
        }});
        const dados = await resp.json();
        if (resp.ok && dados.sucesso) {{
            salvarFiltros();
            location.reload();
        }} else {{
            alert(dados.erro || "Nenhuma ação recente para desfazer.");
        }}
    }} catch (e) {{
        alert("O servidor do painel não está ativo em segundo plano.");
    }}
}}

async function reanalisarPasta() {{
    const btn = document.getElementById("btn-reanalisar");
    if (btn) {{
        btn.disabled = true;
        btn.innerText = "Analisando...";
    }}
    try {{
        const resp = await fetch("/api/reanalisar", {{
            method: "POST",
            headers: {{
                "Content-Type": "application/json",
                "X-CSRF-Token": obterTokenCSRF()
            }},
            body: JSON.stringify({{}})
        }});
        const dados = await resp.json();
        if (resp.ok && dados.sucesso) {{
            salvarFiltros();
            location.reload();
        }} else {{
            alert("Erro ao reanalisar.");
        }}
    }} catch (e) {{
        if (btn) {{
            btn.disabled = false;
            btn.innerText = "🔄 Reanalisar";
        }}
        alert("O servidor do painel não está ativo.");
    }}
}}

function mostrarNotificacao(msg) {{
    let toast = document.getElementById("toast-notificacao");
    if (!toast) {{
        toast = document.createElement("div");
        toast.id = "toast-notificacao";
        toast.className = "toast-notificacao";
        document.body.appendChild(toast);
    }}
    toast.innerText = msg;
    toast.style.display = "block";
    setTimeout(() => {{
        toast.style.display = "none";
    }}, 4000);
}}

</script>


</body>

</html>
"""

    caminho_saida.write_text(
        html,
        encoding="utf-8",
    )

    return caminho_saida
