# -*- coding: utf-8 -*-
"""
AgriPrecisa: interface texts in Portuguese, English and Spanish.

The language follows the QGIS interface locale: pt* -> Portuguese,
es* -> Spanish, anything else -> English.

To add or change a text, edit the STRINGS dictionary. Every key must have
the three languages (checked by tests/test_i18n.py).
"""

_LANG = None


def current_language():
    global _LANG
    if _LANG is not None:
        return _LANG
    locale = ""
    try:
        from qgis.core import QgsApplication
        locale = QgsApplication.locale() or ""
    except Exception:
        pass
    if not locale:
        try:
            from qgis.PyQt.QtCore import QLocale
            locale = QLocale.system().name()
        except Exception:
            locale = "en"
    locale = locale.lower()
    _LANG = "pt" if locale.startswith("pt") else "es" if locale.startswith("es") else "en"
    return _LANG


def set_language(lang):
    """Force a language ('pt', 'en' or 'es'); used by tests."""
    global _LANG
    _LANG = lang


def tr(key, **kwargs):
    entry = STRINGS.get(key)
    if entry is None:
        return key
    text = entry.get(current_language()) or entry["en"]
    return text.format(**kwargs) if kwargs else text


def fmt(value, decimals=0):
    """Number in the interface language: 4.969 / 39,8 (pt, es) or 4,969 / 39.8 (en)."""
    if value is None:
        return "-"
    text = f"{value:,.{decimals}f}"  # 4,969.8
    if current_language() in ("pt", "es"):
        text = text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    return text


STRINGS = {
    # ---------------------------------------------------------------- general
    "help": {"pt": "Ajuda", "en": "Help", "es": "Ayuda"},
    "next": {"pt": "Próximo >", "en": "Next >", "es": "Siguiente >"},
    "back": {"pt": "< Voltar", "en": "< Back", "es": "< Atrás"},
    "run": {"pt": "Executar", "en": "Run", "es": "Ejecutar"},
    "cancel": {"pt": "Cancelar", "en": "Cancel", "es": "Cancelar"},
    "browse": {"pt": "Procurar...", "en": "Browse...", "es": "Examinar..."},
    "ok": {"pt": "OK", "en": "OK", "es": "OK"},
    "not_meters": {"pt": "NÃO está em metros", "en": "NOT in metres", "es": "NO está en metros"},
    "no_limit": {"pt": "Sem limite", "en": "No limit", "es": "Sin límite"},
    "starting": {"pt": "Iniciando...", "en": "Starting...", "es": "Iniciando..."},
    "canceled": {"pt": "Processamento cancelado pelo usuário.",
                 "en": "Processing canceled by the user.",
                 "es": "Procesamiento cancelado por el usuario."},
    "error_title": {"pt": "Erro no processamento", "en": "Processing error",
                    "es": "Error en el procesamiento"},
    "warnings": {"pt": "Avisos:", "en": "Warnings:", "es": "Avisos:"},
    "group_name": {"pt": "Interpolados", "en": "Interpolated", "es": "Interpolados"},
    "selected_features": {"pt": "feições selecionadas", "en": "selected features",
                          "es": "entidades seleccionadas"},
    "project_layer_title": {"pt": "Reprojete a camada", "en": "Reproject the layer",
                            "es": "Reproyecte la capa"},
    "project_title": {"pt": "SRC do projeto", "en": "Project CRS", "es": "SRC del proyecto"},

    # ---------------------------------------------------------------- plugin
    "action_idw": {"pt": "IDW em grade vetorial...", "en": "IDW vector grid...",
                   "es": "IDW en cuadrícula vectorial..."},
    "action_idw_tip": {
        "pt": "Interpolação IDW, grade vetorial do tamanho do pixel e mapas graduados",
        "en": "IDW interpolation, pixel-sized vector grid and graduated maps",
        "es": "Interpolación IDW, cuadrícula vectorial del tamaño del píxel y mapas graduados"},
    "action_help": {"pt": "Documentação do AgriPrecisa", "en": "AgriPrecisa documentation",
                    "es": "Documentación de AgriPrecisa"},
    "wizard_title": {"pt": "AgriPrecisa | IDW em grade vetorial",
                     "en": "AgriPrecisa | IDW vector grid",
                     "es": "AgriPrecisa | IDW en cuadrícula vectorial"},

    # ---------------------------------------------------------------- page 1
    "p1_title": {"pt": "Etapa 1 de 4: Contorno da área e pasta de saída",
                 "en": "Step 1 of 4: Field boundary and output folder",
                 "es": "Paso 1 de 4: Contorno del área y carpeta de salida"},
    "p1_subtitle": {"pt": "Escolha o polígono do talhão e onde os resultados serão salvos.",
                    "en": "Choose the field polygon and where results will be saved.",
                    "es": "Elija el polígono del lote y dónde se guardarán los resultados."},
    "p1_boundary": {"pt": "Camada de contorno (polígono):", "en": "Boundary layer (polygon):",
                    "es": "Capa de contorno (polígono):"},
    "p1_selected_only": {"pt": "Usar apenas as feições selecionadas",
                         "en": "Use selected features only",
                         "es": "Usar solo las entidades seleccionadas"},
    "p1_tolerance": {"pt": "Tolerância além do contorno:", "en": "Tolerance beyond boundary:",
                     "es": "Tolerancia más allá del contorno:"},
    "p1_folder": {"pt": "Pasta de saída:", "en": "Output folder:", "es": "Carpeta de salida:"},
    "p1_folder_dialog": {"pt": "Pasta para salvar os mapas interpolados",
                         "en": "Folder to save the interpolated maps",
                         "es": "Carpeta para guardar los mapas interpolados"},
    "p1_no_polygons": {"pt": "Nenhuma camada de polígonos encontrada no projeto.",
                       "en": "No polygon layer found in the project.",
                       "es": "No se encontró ninguna capa de polígonos en el proyecto."},
    "p1_crs_info": {"pt": "SRC do contorno: {layer_crs} ({ok_l})<br>SRC do projeto: {project_crs} ({ok_p})",
                    "en": "Boundary CRS: {layer_crs} ({ok_l})<br>Project CRS: {project_crs} ({ok_p})",
                    "es": "SRC del contorno: {layer_crs} ({ok_l})<br>SRC del proyecto: {project_crs} ({ok_p})"},
    "p1_err_choose": {"pt": "Escolha uma camada de polígonos para o contorno.",
                      "en": "Choose a polygon layer for the boundary.",
                      "es": "Elija una capa de polígonos para el contorno."},
    "p1_err_empty": {"pt": "A camada de contorno não possui feições com geometria.",
                     "en": "The boundary layer has no features with geometry.",
                     "es": "La capa de contorno no tiene entidades con geometría."},
    "p1_err_crs": {
        "pt": "A camada '{name}' está em {crs}, que não é um sistema projetado em metros.\n\n"
              "Reprojete a camada (Vetor > Gerenciar dados > Reprojetar camada), por exemplo "
              "para SIRGAS 2000 / UTM 22S (EPSG:31982), e execute novamente.",
        "en": "Layer '{name}' is in {crs}, which is not a projected system in metres.\n\n"
              "Reproject the layer (Vector > Data Management Tools > Reproject Layer) to a "
              "projected CRS such as UTM and run again.",
        "es": "La capa '{name}' está en {crs}, que no es un sistema proyectado en metros.\n\n"
              "Reproyecte la capa (Vectorial > Herramientas de gestión de datos > Reproyectar capa) "
              "a un SRC proyectado, por ejemplo UTM, y ejecute de nuevo."},
    "p1_ask_project_crs": {
        "pt": "O projeto está em {crs}, que não é um sistema projetado em metros.\n\n"
              "Recomenda-se ajustar em Projeto > Propriedades > SRC. Os cálculos usam o SRC "
              "do contorno, então é possível continuar.\n\nDeseja continuar mesmo assim?",
        "en": "The project is in {crs}, which is not a projected system in metres.\n\n"
              "It is recommended to change it in Project > Properties > CRS. Calculations use "
              "the boundary CRS, so you may continue.\n\nContinue anyway?",
        "es": "El proyecto está en {crs}, que no es un sistema proyectado en metros.\n\n"
              "Se recomienda ajustarlo en Proyecto > Propiedades > SRC. Los cálculos usan el SRC "
              "del contorno, así que es posible continuar.\n\n¿Desea continuar de todos modos?"},
    "p1_err_folder": {"pt": "Escolha uma pasta existente e com permissão de escrita.",
                      "en": "Choose an existing folder with write permission.",
                      "es": "Elija una carpeta existente y con permiso de escritura."},
    "help_page1": {
        "pt": "<b>Etapa 1: Contorno e pasta de saída</b><br><br>"
              "<b>Camada de contorno:</b> polígono que delimita o talhão. O retângulo envolvente "
              "dele define a área da interpolação, e ele também recorta a grade final. Se houver "
              "feições selecionadas, é possível usar apenas elas (por exemplo, um talhão de uma "
              "camada com vários).<br><br>"
              "<b>Tolerância:</b> distância, em metros, além do contorno em que os pontos ainda são "
              "aceitos. Inclui amostras que ficaram um pouco fora do limite, por exemplo em manobras. "
              "Também define quais camadas de pontos aparecem na próxima etapa.<br><br>"
              "<b>Pasta de saída:</b> onde ficam os rasters interpolados (GeoTIFF) e a grade "
              "vetorial final (GeoPackage).<br><br>"
              "<b>Sistema de coordenadas:</b> o contorno e os pontos precisam estar em um sistema "
              "projetado em metros, como SIRGAS 2000 / UTM 22S (EPSG:31982).",
        "en": "<b>Step 1: Boundary and output folder</b><br><br>"
              "<b>Boundary layer:</b> polygon delimiting the field. Its bounding box defines the "
              "interpolation area and it also clips the final grid. If features are selected, you "
              "can use only them (e.g. one field from a layer with many).<br><br>"
              "<b>Tolerance:</b> distance, in metres, beyond the boundary within which points are "
              "still accepted. It keeps samples slightly outside the limit, e.g. from machine "
              "turns. It also defines which point layers are listed in the next step.<br><br>"
              "<b>Output folder:</b> where the interpolated rasters (GeoTIFF) and the final "
              "vector grid (GeoPackage) are saved.<br><br>"
              "<b>Coordinate system:</b> boundary and points must be in a projected CRS in "
              "metres, such as a UTM zone.",
        "es": "<b>Paso 1: Contorno y carpeta de salida</b><br><br>"
              "<b>Capa de contorno:</b> polígono que delimita el lote. Su rectángulo envolvente "
              "define el área de interpolación y también recorta la cuadrícula final. Si hay "
              "entidades seleccionadas, se pueden usar solo ellas (por ejemplo, un lote de una "
              "capa con varios).<br><br>"
              "<b>Tolerancia:</b> distancia, en metros, más allá del contorno dentro de la cual los "
              "puntos aún se aceptan. Incluye muestras algo fuera del límite, por ejemplo en "
              "maniobras. También define qué capas de puntos aparecen en el siguiente paso.<br><br>"
              "<b>Carpeta de salida:</b> donde se guardan los ráster interpolados (GeoTIFF) y la "
              "cuadrícula vectorial final (GeoPackage).<br><br>"
              "<b>Sistema de coordenadas:</b> el contorno y los puntos deben estar en un SRC "
              "proyectado en metros, como una zona UTM."},

    # ---------------------------------------------------------------- page 2
    "p2_title": {"pt": "Etapa 2 de 4: Pontos e atributos a interpolar",
                 "en": "Step 2 of 4: Points and fields to interpolate",
                 "es": "Paso 2 de 4: Puntos y atributos a interpolar"},
    "p2_subtitle": {"pt": "Expanda as camadas pelas setas e marque os atributos desejados.",
                    "en": "Expand the layers with the arrows and tick the fields you want.",
                    "es": "Expanda las capas con las flechas y marque los atributos deseados."},
    "p2_subtitle_area": {
        "pt": "Talhão: {area} ha. Expanda as camadas pelas setas e marque os atributos desejados.",
        "en": "Field: {area} ha. Expand the layers with the arrows and tick the fields you want.",
        "es": "Lote: {area} ha. Expanda las capas con las flechas y marque los atributos deseados."},
    "p2_count": {"pt": "{n} ({density} amostras/ha)", "en": "{n} ({density} samples/ha)",
                 "es": "{n} ({density} muestras/ha)"},
    "p2_tip_count": {
        "pt": "{inside} amostras dentro do talhão ({density} amostras/ha). Na interpolação "
              "serão usadas {used}, incluindo as que estão até {tol} m fora do contorno.",
        "en": "{inside} samples inside the field ({density} samples/ha). Interpolation "
              "will use {used}, including those up to {tol} m outside the boundary.",
        "es": "{inside} muestras dentro del lote ({density} muestras/ha). En la interpolación "
              "se usarán {used}, incluidas las que están hasta {tol} m fuera del contorno."},
    "p2_col_layer": {"pt": "Camada / atributo", "en": "Layer / field", "es": "Capa / atributo"},
    "p2_no_crs": {"pt": "sem SRC", "en": "no CRS", "es": "sin SRC"},
    "p2_tip_ok": {"pt": "{crs}: sistema projetado em metros, pronto para interpolar.",
                  "en": "{crs}: projected system in metres, ready to interpolate.",
                  "es": "{crs}: sistema proyectado en metros, listo para interpolar."},
    "p2_tip_geographic": {
        "pt": "{crs} é um sistema geográfico (graus). O sistema de coordenadas deverá ser projetado "
              "para um sistema em metros, por exemplo SIRGAS 2000 / UTM 22S (EPSG:31982). "
              "Use Vetor > Gerenciar dados > Reprojetar camada.",
        "en": "{crs} is a geographic system (degrees). The coordinate system must be projected to a "
              "system in metres, for example a UTM zone. Use Vector > Data Management Tools > "
              "Reproject Layer.",
        "es": "{crs} es un sistema geográfico (grados). El sistema de coordenadas deberá proyectarse "
              "a un sistema en metros, por ejemplo una zona UTM. Use Vectorial > Herramientas de "
              "gestión de datos > Reproyectar capa."},
    "p2_tip_not_meters": {
        "pt": "{crs} é projetado, mas a unidade não é o metro. O sistema de coordenadas deverá ser "
              "projetado para um sistema em metros, por exemplo SIRGAS 2000 / UTM 22S (EPSG:31982).",
        "en": "{crs} is projected but its unit is not the metre. The coordinate system must be "
              "projected to a system in metres, for example a UTM zone.",
        "es": "{crs} es proyectado, pero su unidad no es el metro. El sistema de coordenadas deberá "
              "proyectarse a un sistema en metros, por ejemplo una zona UTM."},
    "p2_tip_invalid": {
        "pt": "A camada não tem sistema de coordenadas definido. Defina o SRC correto e projete para "
              "um sistema em metros, por exemplo SIRGAS 2000 / UTM 22S (EPSG:31982).",
        "en": "The layer has no coordinate system. Set the correct CRS and project it to a system in "
              "metres, for example a UTM zone.",
        "es": "La capa no tiene sistema de coordenadas. Defina el SRC correcto y proyéctelo a un "
              "sistema en metros, por ejemplo una zona UTM."},
    "p2_col_points": {"pt": "Amostras no talhão (densidade)", "en": "Samples in field (density)",
                      "es": "Muestras en el lote (densidad)"},
    "expand_all": {"pt": "Expandir tudo", "en": "Expand all", "es": "Expandir todo"},
    "collapse_all": {"pt": "Recolher tudo", "en": "Collapse all", "es": "Contraer todo"},
    "check_all": {"pt": "Marcar tudo", "en": "Check all", "es": "Marcar todo"},
    "uncheck_all": {"pt": "Desmarcar tudo", "en": "Uncheck all", "es": "Desmarcar todo"},
    "p2_none": {"pt": "Nenhuma camada de pontos com atributos numéricos foi encontrada na área. "
                      "Volte e aumente a tolerância ou carregue as camadas de pontos no projeto.",
                "en": "No point layer with numeric fields was found in the area. Go back and "
                      "increase the tolerance or load the point layers into the project.",
                "es": "No se encontró ninguna capa de puntos con atributos numéricos en el área. "
                      "Vuelva y aumente la tolerancia o cargue las capas de puntos en el proyecto."},
    "p2_found": {"pt": "{n} camada(s) de pontos encontrada(s) na área.",
                 "en": "{n} point layer(s) found in the area.",
                 "es": "{n} capa(s) de puntos encontrada(s) en el área."},
    "p2_err_none": {"pt": "Marque pelo menos um atributo para interpolar.",
                    "en": "Tick at least one field to interpolate.",
                    "es": "Marque al menos un atributo para interpolar."},
    "p2_err_crs": {"pt": "As camadas abaixo não estão em um sistema projetado em metros:\n\n{layers}"
                         "\n\nReprojete-as e execute novamente.",
                   "en": "The layers below are not in a projected system in metres:\n\n{layers}"
                         "\n\nReproject them and run again.",
                   "es": "Las capas siguientes no están en un sistema proyectado en metros:\n\n{layers}"
                         "\n\nReproyéctelas y ejecute de nuevo."},
    "help_page2": {
        "pt": "<b>Etapa 2: Camadas de pontos e atributos</b><br><br>"
              "Aparecem apenas as camadas de pontos com amostras dentro do contorno ampliado pela "
              "tolerância. O cabeçalho mostra a área do talhão em hectares.<br><br>"
              "<b>Amostras no talhão (densidade):</b> na linha de cada camada, o número de pontos "
              "dentro do talhão. Entre parênteses está a densidade amostral (amostras/ha), que indica o "
              "quanto a amostragem consegue captar a variabilidade espacial: quanto menor a "
              "densidade, maior a distância entre amostras e mais suavizado tende a ficar o mapa. "
              "Passe o cursor sobre o número para ver quantas amostras serão usadas na "
              "interpolação, incluindo a tolerância.<br><br>"
              "O código EPSG aparece entre colchetes após o nome de cada camada. O ícone de alerta "
              "à direita indica que a camada não está em um sistema projetado em metros; passe o "
              "cursor sobre ele para ver como corrigir.<br><br>"
              "Clique na <b>seta</b> de cada camada para expandir ou recolher os atributos "
              "numéricos e marque os que deseja interpolar. Marcar a camada seleciona todos os "
              "atributos dela.<br><br>"
              "Cada atributo marcado gera um raster interpolado e uma coluna na grade final.",
        "en": "<b>Step 2: Point layers and fields</b><br><br>"
              "Only point layers with samples inside the boundary enlarged by the tolerance are "
              "listed. The header shows the field area in hectares.<br><br>"
              "<b>Samples in field (density):</b> on each layer row, the number of points inside the "
              "field. In brackets is the sampling density (samples/ha), which indicates how well the "
              "sampling captures spatial variability: the lower the density, the larger the "
              "distance between samples and the smoother the map tends to be. Hover over the number "
              "to see how many samples interpolation will use, including the tolerance.<br><br>"
              "The EPSG code is shown in brackets after each layer name. The warning icon on the "
              "right means the layer is not in a projected system in metres; hover over it to see "
              "how to fix it.<br><br>"
              "Click the <b>arrow</b> of each layer to expand or collapse its numeric fields and "
              "tick the ones to interpolate. Ticking a layer selects all of its fields.<br><br>"
              "Each ticked field produces an interpolated raster and a column in the final grid.",
        "es": "<b>Paso 2: Capas de puntos y atributos</b><br><br>"
              "Solo aparecen las capas de puntos con muestras dentro del contorno ampliado por la "
              "tolerancia. El encabezado muestra el área del lote en hectáreas.<br><br>"
              "<b>Muestras en el lote (densidad):</b> en la fila de cada capa, el número de puntos "
              "dentro del lote. Entre paréntesis está la densidad de muestreo (muestras/ha), que indica "
              "cuánto capta el muestreo la variabilidad espacial: cuanto menor la densidad, mayor la "
              "distancia entre muestras y más suavizado tiende a quedar el mapa. Pase el cursor "
              "sobre el número para ver cuántas muestras usará la interpolación, incluida la "
              "tolerancia.<br><br>"
              "El código EPSG aparece entre corchetes tras el nombre de cada capa. El icono de alerta "
              "a la derecha indica que la capa no está en un sistema proyectado en metros; pase el "
              "cursor sobre él para ver cómo corregirlo.<br><br>"
              "Haga clic en la <b>flecha</b> de cada capa para expandir o contraer sus atributos "
              "numéricos y marque los que desea interpolar. Marcar la capa selecciona todos sus "
              "atributos.<br><br>"
              "Cada atributo marcado genera un ráster interpolado y una columna en la cuadrícula final."},

    # ---------------------------------------------------------------- page 3
    "p3_title": {"pt": "Etapa 3 de 4: Parâmetros da interpolação IDW",
                 "en": "Step 3 of 4: IDW interpolation parameters",
                 "es": "Paso 3 de 4: Parámetros de la interpolación IDW"},
    "p3_subtitle": {"pt": "Ajuste a potência, o raio de busca e o tamanho do pixel.",
                    "en": "Set the power, the search radius and the pixel size.",
                    "es": "Ajuste la potencia, el radio de búsqueda y el tamaño del píxel."},
    "p3_power": {"pt": "Potência (P):", "en": "Power (P):", "es": "Potencia (P):"},
    "p3_radius": {"pt": "Raio de busca:", "en": "Search radius:", "es": "Radio de búsqueda:"},
    "p3_pixel": {"pt": "Tamanho do pixel:", "en": "Pixel size:", "es": "Tamaño del píxel:"},
    "p3_estimate": {"pt": "Raster estimado: {ncol} colunas x {nrow} linhas = {total} pixels por atributo.",
                    "en": "Estimated raster: {ncol} columns x {nrow} rows = {total} pixels per field.",
                    "es": "Ráster estimado: {ncol} columnas x {nrow} filas = {total} píxeles por atributo."},
    "p3_big": {"pt": "<b>Atenção:</b> grade muito grande; o processamento pode demorar bastante.",
               "en": "<b>Warning:</b> very large grid; processing may take a long time.",
               "es": "<b>Atención:</b> cuadrícula muy grande; el procesamiento puede tardar bastante."},
    "help_page3": {
        "pt": "<b>Etapa 3: Parâmetros do IDW</b><br><br>"
              "O IDW (inverso da distância ponderada) estima cada pixel pela média das amostras "
              "vizinhas, dando mais peso às mais próximas.<br><br>"
              "<b>Cada atributo tem seus próprios P e raio</b>, porque a dependência espacial e a "
              "variabilidade mudam de um atributo para outro. Escolha o atributo no topo; as barras, "
              "a curva e a prévia passam a valer para ele. A tabela mostra os parâmetros de todos e a "
              "origem de cada um (padrão, validação ou manual).<br><br>"
              "<b>Modo aluno:</b> barras deslizantes com explicações que mudam conforme o valor, a "
              "curva de peso × distância e uma prévia do mapa com os seus dados. Mova as barras e "
              "observe como o mapa muda. Os links <i>Saiba mais</i> trazem a explicação técnica.<br>"
              "<b>Modo avançado:</b> campos numéricos livres, com P acima de 3 e raio sem limite. "
              "O modo escolhido fica salvo para a próxima vez.<br><br>"
              "<b>Potência P:</b> quanto maior, mais rápido o peso cai com a distância.<br>"
              "<b>Raio de busca:</b> no modo aluno, é definido em múltiplos da distância de "
              "cobertura (distância que cobre 95% do talhão); o valor em metros aparece acima da "
              "barra.<br>"
              "<b>Sugerir para este / para todos:</b> a validação cruzada testa combinações e indica, "
              "para cada atributo, a de menor erro.<br>"
              "<b>Mostrar amostras:</b> liga ou desliga os pontos na prévia.<br>"
              "<b>Tamanho do pixel:</b> lado de cada pixel e de cada célula da grade final. "
              "Padrão de 5 m.",
        "en": "<b>Step 3: IDW parameters</b><br><br>"
              "IDW (Inverse Distance Weighting) estimates each pixel as the average of nearby "
              "samples, giving more weight to the closest ones.<br><br>"
              "<b>Each attribute has its own P and radius</b>, because spatial dependence and "
              "variability change from one attribute to another. Choose the attribute at the top; "
              "the sliders, curve and preview then apply to it. The table shows the parameters of all "
              "attributes and where each came from (default, validation or manual).<br><br>"
              "<b>Student mode:</b> sliders with explanations that change with the value, the "
              "weight × distance curve and a map preview with your data. Move the sliders and "
              "watch the map change. The <i>Learn more</i> links give the technical explanation.<br>"
              "<b>Advanced mode:</b> free numeric fields, with P above 3 and unlimited radius. "
              "The chosen mode is remembered.<br><br>"
              "<b>Power P:</b> the higher it is, the faster the weight falls with distance.<br>"
              "<b>Search radius:</b> in student mode it is set in multiples of the coverage "
              "distance (distance covering 95% of the field); the value in metres is shown above "
              "the slider.<br>"
              "<b>Suggest for this one / for all:</b> cross-validation tests combinations and points "
              "out, for each attribute, the one with the lowest error.<br>"
              "<b>Show samples:</b> turns the points on or off in the preview.<br>"
              "<b>Pixel size:</b> side of each pixel and of each final grid cell. Default 5 m.",
        "es": "<b>Paso 3: Parámetros del IDW</b><br><br>"
              "El IDW (inverso de la distancia ponderada) estima cada píxel como el promedio de las "
              "muestras vecinas, dando más peso a las más cercanas.<br><br>"
              "<b>Cada atributo tiene su propio P y radio</b>, porque la dependencia espacial y la "
              "variabilidad cambian de un atributo a otro. Elija el atributo arriba; las barras, la "
              "curva y la vista previa pasan a valer para él. La tabla muestra los parámetros de todos "
              "y el origen de cada uno (por defecto, validación o manual).<br><br>"
              "<b>Modo estudiante:</b> barras deslizantes con explicaciones que cambian con el "
              "valor, la curva peso × distancia y una vista previa del mapa con sus datos. Mueva "
              "las barras y observe cómo cambia el mapa. Los enlaces <i>Saber más</i> traen la "
              "explicación técnica.<br>"
              "<b>Modo avanzado:</b> campos numéricos libres, con P mayor que 3 y radio sin límite. "
              "El modo elegido se recuerda.<br><br>"
              "<b>Potencia P:</b> cuanto mayor, más rápido cae el peso con la distancia.<br>"
              "<b>Radio de búsqueda:</b> en modo estudiante se define en múltiplos de la distancia de "
              "cobertura (distancia que cubre el 95% del lote); el valor en metros aparece sobre la "
              "barra.<br>"
              "<b>Sugerir para este / para todos:</b> la validación cruzada prueba combinaciones e "
              "indica, para cada atributo, la de menor error.<br>"
              "<b>Mostrar muestras:</b> enciende o apaga los puntos en la vista previa.<br>"
              "<b>Tamaño del píxel:</b> lado de cada píxel y de cada celda de la cuadrícula final. "
              "Por defecto 5 m."},
    "learn_more": {"pt": "Saiba mais", "en": "Learn more", "es": "Saber más"},
    "p3_mode": {"pt": "Modo:", "en": "Mode:", "es": "Modo:"},
    "p3_mode_student": {"pt": "Aluno (visual)", "en": "Student (visual)", "es": "Estudiante (visual)"},
    "p3_mode_advanced": {"pt": "Avançado (valores livres)", "en": "Advanced (free values)",
                         "es": "Avanzado (valores libres)"},
    "p3_advanced_note": {
        "pt": "No modo avançado é possível usar P acima de 3 e raio sem limite (0).",
        "en": "Advanced mode allows P above 3 and an unlimited radius (0).",
        "es": "El modo avanzado permite P mayor que 3 y radio sin límite (0)."},
    "p3_power_group": {"pt": "Potência (P)", "en": "Power (P)", "es": "Potencia (P)"},
    "p3_power_value": {"pt": "P = {p}", "en": "P = {p}", "es": "P = {p}"},
    "p3_power_low": {
        "pt": "P baixo: suaviza o mapa, porque amostras mais distantes também influenciam cada "
              "pixel. Geralmente usado quando a variável muda pouco no talhão (variabilidade menor).",
        "en": "Low P: smooths the map, because more distant samples also influence each pixel. "
              "Usually used when the variable changes little across the field (lower variability).",
        "es": "P bajo: suaviza el mapa, porque las muestras más lejanas también influyen en cada "
              "píxel. Se usa generalmente cuando la variable cambia poco en el lote (menor variabilidad)."},
    "p3_power_mid": {
        "pt": "P intermediário: equilíbrio entre suavizar e respeitar cada amostra. O valor 2 é o "
              "mais usado e é um bom ponto de partida.",
        "en": "Intermediate P: balance between smoothing and honouring each sample. P = 2 is the "
              "most common choice and a good starting point.",
        "es": "P intermedio: equilibrio entre suavizar y respetar cada muestra. P = 2 es el más "
              "usado y un buen punto de partida."},
    "p3_power_high": {
        "pt": "P alto: dá mais peso às amostras próximas. Geralmente usado quando a variável muda "
              "muito em curtas distâncias (variabilidade maior). Valores altos criam 'ilhas' em volta "
              "das amostras.",
        "en": "High P: gives more weight to nearby samples. Usually used when the variable changes a "
              "lot over short distances (higher variability). High values create 'islands' around the "
              "samples.",
        "es": "P alto: da más peso a las muestras cercanas. Se usa generalmente cuando la variable "
              "cambia mucho en distancias cortas (mayor variabilidad). Valores altos crean 'islas' "
              "alrededor de las muestras."},
    "p3_power_more": {
        "pt": "<b>Potência P do IDW</b><br><br>O valor de cada pixel é a média ponderada das amostras "
              "vizinhas, com peso 1/d<sup>P</sup> (d = distância até a amostra).<ul>"
              "<li><b>P baixo (perto de 1):</b> o peso cai devagar com a distância e amostras mais "
              "distantes também influenciam. O mapa fica suave e mostra a tendência geral da área. "
              "Combina com variáveis de baixa variabilidade ou com dependência espacial de longo "
              "alcance.</li>"
              "<li><b>P = 2:</b> o valor mais usado na literatura e nos programas de agricultura de "
              "precisão; equilibra suavização e fidelidade às amostras.</li>"
              "<li><b>P alto (perto de 3 ou mais):</b> o peso cai rápido e cada pixel fica parecido "
              "com a amostra mais próxima. Realça variações locais, mas cria o efeito 'olho de boi' "
              "(manchas circulares em volta das amostras). Combina com variáveis de alta "
              "variabilidade em curtas distâncias e amostragem densa.</li></ul>"
              "Para escolher com critério, compare os mapas na prévia. Em pesquisa, use a validação "
              "cruzada: retire cada amostra, estime-a pelas demais e compare o erro entre valores "
              "de P. Quando a dependência espacial é bem descrita por um semivariograma, a krigagem "
              "costuma ser preferível ao IDW.",
        "en": "<b>IDW power P</b><br><br>Each pixel is the weighted average of nearby samples, with "
              "weight 1/d<sup>P</sup> (d = distance to the sample).<ul>"
              "<li><b>Low P (near 1):</b> the weight falls slowly with distance and more distant "
              "samples also count. The map is smooth and shows the general trend. Suits variables "
              "with low variability or long-range spatial dependence.</li>"
              "<li><b>P = 2:</b> the most common value in the literature and in precision agriculture "
              "software; balances smoothing and fidelity to the samples.</li>"
              "<li><b>High P (near 3 or more):</b> the weight falls quickly and each pixel resembles "
              "the nearest sample. Highlights local variation but creates the 'bull's-eye' effect "
              "(circular spots around samples). Suits variables with high short-range variability "
              "and dense sampling.</li></ul>"
              "To choose with criteria, compare the maps in the preview. In research, use "
              "cross-validation: remove each sample, estimate it from the others and compare the "
              "error between P values. When spatial dependence is well described by a "
              "semivariogram, kriging is usually preferable to IDW.",
        "es": "<b>Potencia P del IDW</b><br><br>Cada píxel es el promedio ponderado de las muestras "
              "vecinas, con peso 1/d<sup>P</sup> (d = distancia a la muestra).<ul>"
              "<li><b>P bajo (cerca de 1):</b> el peso cae lentamente con la distancia y las muestras "
              "más lejanas también influyen. El mapa queda suave y muestra la tendencia general. "
              "Adecuado para variables de baja variabilidad o dependencia espacial de largo "
              "alcance.</li>"
              "<li><b>P = 2:</b> el valor más usado en la literatura y en los programas de agricultura "
              "de precisión; equilibra suavizado y fidelidad a las muestras.</li>"
              "<li><b>P alto (cerca de 3 o más):</b> el peso cae rápido y cada píxel se parece a la "
              "muestra más cercana. Resalta variaciones locales, pero crea el efecto 'ojo de buey' "
              "(manchas circulares alrededor de las muestras). Adecuado para variables de alta "
              "variabilidad en distancias cortas y muestreo denso.</li></ul>"
              "Para elegir con criterio, compare los mapas en la vista previa. En investigación, use "
              "la validación cruzada: retire cada muestra, estímela con las demás y compare el error "
              "entre valores de P. Cuando la dependencia espacial está bien descrita por un "
              "semivariograma, el kriging suele ser preferible al IDW."},
    "p3_radius_group": {"pt": "Raio de busca", "en": "Search radius", "es": "Radio de búsqueda"},
    "p3_spacing": {
        "pt": "Distância de cobertura: 95% do talhão fica a até {spacing} m de uma amostra "
              "({density} amostras/ha).",
        "en": "Coverage distance: 95% of the field is within {spacing} m of a sample "
              "({density} samples/ha).",
        "es": "Distancia de cobertura: el 95% del lote está a menos de {spacing} m de una muestra "
              "({density} muestras/ha)."},
    "p3_spacing_none": {
        "pt": "Não foi possível estimar o espaçamento entre amostras. Use o modo avançado para "
              "definir o raio em metros.",
        "en": "The sample spacing could not be estimated. Use advanced mode to set the radius in metres.",
        "es": "No se pudo estimar el espaciamiento entre muestras. Use el modo avanzado para definir "
              "el radio en metros."},
    "p3_radius_value": {"pt": "Raio = {mult} × {spacing} m = {radius} m",
                        "en": "Radius = {mult} × {spacing} m = {radius} m",
                        "es": "Radio = {mult} × {spacing} m = {radius} m"},
    "p3_radius_short": {
        "pt": "Raio curto: cada pixel enxerga poucas amostras. O mapa fica mais local e podem surgir "
              "falhas (pixels sem valor, em cinza na prévia).",
        "en": "Short radius: each pixel sees few samples. The map is more local and gaps may appear "
              "(pixels without value, grey in the preview).",
        "es": "Radio corto: cada píxel ve pocas muestras. El mapa es más local y pueden aparecer "
              "huecos (píxeles sin valor, en gris en la vista previa)."},
    "p3_radius_ok": {
        "pt": "Raio recomendado: cada pixel considera várias amostras vizinhas, cerca de 2 vezes a "
              "distância de cobertura.",
        "en": "Recommended radius: each pixel considers several neighbouring samples, about twice "
              "the coverage distance.",
        "es": "Radio recomendado: cada píxel considera varias muestras vecinas, cerca de 2 veces la "
              "distancia de cobertura."},
    "p3_radius_long": {
        "pt": "Raio longo: o mapa fica mais suave e sem falhas, mas detalhes locais se perdem e o "
              "cálculo fica mais lento.",
        "en": "Long radius: the map is smoother and without gaps, but local detail is lost and "
              "processing is slower.",
        "es": "Radio largo: el mapa queda más suave y sin huecos, pero se pierden detalles locales y "
              "el cálculo es más lento."},
    "p3_radius_more": {
        "pt": "<b>Raio de busca</b><br><br>Só as amostras dentro do raio entram no cálculo de cada "
              "pixel. A barra usa a <b>distância de cobertura</b>: mede-se, para os pixels do talhão, a "
              "distância até a amostra mais próxima, e 95% deles ficam a até essa distância.<br><br>"
              "Ela funciona tanto para amostragem em grade quanto para sensores em passadas (como a CE), "
              "em que os pontos ficam muito próximos na linha e distantes entre as linhas. Nesse caso, "
              "um espaçamento calculado só pela densidade seria pequeno demais e deixaria faixas sem "
              "valor entre as passadas.<br><br>"
              "Um raio de 1,5 a 2,5 vezes a distância de cobertura garante várias vizinhas em cada pixel. "
              "Raios menores deixam falhas; raios maiores suavizam e deixam o cálculo mais lento. Em "
              "pesquisa, o alcance do semivariograma é uma boa referência.<br><br>"
              "Com mais de um atributo marcado, vale o de menor cobertura (amostragem mais esparsa).",
        "en": "<b>Search radius</b><br><br>Only samples within the radius are used for each pixel. The "
              "slider uses the <b>coverage distance</b>: for the field pixels, the distance to the nearest "
              "sample is measured, and 95% of them are within this distance.<br><br>"
              "It works both for grid sampling and for sensor passes (such as EC), where points are very "
              "close along the line and far apart between lines. In that case, a spacing computed from "
              "density alone would be too small and leave strips without value between passes.<br><br>"
              "A radius of 1.5 to 2.5 times the coverage distance ensures several neighbours per pixel. "
              "Smaller radii leave gaps; larger radii smooth and slow processing. In research, the "
              "semivariogram range is a good reference.<br><br>"
              "With several attributes ticked, the one with the sparsest sampling is used.",
        "es": "<b>Radio de búsqueda</b><br><br>Solo las muestras dentro del radio entran en el cálculo de "
              "cada píxel. La barra usa la <b>distancia de cobertura</b>: se mide, para los píxeles del "
              "lote, la distancia a la muestra más cercana, y el 95% de ellos está a menos de esa "
              "distancia.<br><br>"
              "Funciona tanto para muestreo en grilla como para sensores en pasadas (como la CE), donde "
              "los puntos están muy cerca en la línea y lejos entre líneas. En ese caso, un espaciamiento "
              "calculado solo por la densidad sería demasiado pequeño y dejaría franjas sin valor.<br><br>"
              "Un radio de 1,5 a 2,5 veces la distancia de cobertura garantiza varias vecinas por píxel. "
              "Radios menores dejan huecos; radios mayores suavizan y hacen el cálculo más lento. En "
              "investigación, el alcance del semivariograma es una buena referencia.<br><br>"
              "Con varios atributos marcados, vale el de muestreo más disperso."},
    "p3_curve_group": {"pt": "Peso das amostras × distância", "en": "Sample weight × distance",
                       "es": "Peso de las muestras × distancia"},
    "p3_curve_x": {"pt": "distância até a amostra", "en": "distance to the sample",
                   "es": "distancia a la muestra"},
    "p3_curve_y": {"pt": "peso", "en": "weight", "es": "peso"},
    "p3_curve_radius": {"pt": "raio", "en": "radius", "es": "radio"},
    "p3_curve_ref": {"pt": "P = 1 e P = 3", "en": "P = 1 and P = 3", "es": "P = 1 y P = 3"},
    "p3_preview_group": {"pt": "Prévia do mapa", "en": "Map preview", "es": "Vista previa del mapa"},
    "p3_preview_attr": {"pt": "Atributo:", "en": "Attribute:", "es": "Atributo:"},
    "p3_attribute": {"pt": "Atributo:", "en": "Attribute:", "es": "Atributo:"},
    "p3_summary_group": {"pt": "Parâmetros por atributo", "en": "Parameters per attribute",
                         "es": "Parámetros por atributo"},
    "sum_col_attr": {"pt": "Atributo", "en": "Attribute", "es": "Atributo"},
    "sum_col_p": {"pt": "P", "en": "P", "es": "P"},
    "sum_col_r": {"pt": "Raio", "en": "Radius", "es": "Radio"},
    "sum_col_origin": {"pt": "Origem", "en": "Origin", "es": "Origen"},
    "origin_default": {"pt": "padrão", "en": "default", "es": "por defecto"},
    "origin_cv": {"pt": "validação", "en": "validation", "es": "validación"},
    "origin_manual": {"pt": "manual", "en": "manual", "es": "manual"},
    "origin_default_tip": {"pt": "Valor inicial: P = 2 e raio de 2 vezes a distância de cobertura.",
                           "en": "Initial value: P = 2 and radius of twice the coverage distance.",
                           "es": "Valor inicial: P = 2 y radio de 2 veces la distancia de cobertura."},
    "origin_cv_tip": {"pt": "Sugerido pela validação cruzada deste atributo.",
                      "en": "Suggested by this attribute's cross-validation.",
                      "es": "Sugerido por la validación cruzada de este atributo."},
    "origin_manual_tip": {"pt": "Ajustado pelo usuário.", "en": "Set by the user.",
                          "es": "Ajustado por el usuario."},
    "cv_this": {"pt": "Sugerir para este", "en": "Suggest for this one", "es": "Sugerir para este"},
    "cv_this_tip": {"pt": "Validação cruzada do atributo selecionado, com a tabela de erro por P e raio.",
                    "en": "Cross-validation of the selected attribute, with the error table by P and radius.",
                    "es": "Validación cruzada del atributo seleccionado, con la tabla de error por P y radio."},
    "cv_all": {"pt": "Sugerir para todos", "en": "Suggest for all", "es": "Sugerir para todos"},
    "cv_all_tip": {"pt": "Faz a validação cruzada de cada atributo e aplica P e raio próprios a cada um.",
                   "en": "Cross-validates each attribute and applies its own P and radius to each one.",
                   "es": "Valida cada atributo y aplica a cada uno su propio P y radio."},
    "cv_all_progress": {"pt": "Validação cruzada: {label}...", "en": "Cross-validation: {label}...",
                        "es": "Validación cruzada: {label}..."},
    "cv_all_done": {"pt": "Parâmetros sugeridos e aplicados a cada atributo:\n\n{lines}",
                    "en": "Parameters suggested and applied to each attribute:\n\n{lines}",
                    "es": "Parámetros sugeridos y aplicados a cada atributo:\n\n{lines}"},
    "cv_all_line": {"pt": "{label}: P = {p}, raio {mult}× ({radius} m), RMSE = {rmse}",
                    "en": "{label}: P = {p}, radius {mult}× ({radius} m), RMSE = {rmse}",
                    "es": "{label}: P = {p}, radio {mult}× ({radius} m), RMSE = {rmse}"},
    "cv_all_fail_line": {"pt": "{label}: não aplicado. {reason}", "en": "{label}: not applied. {reason}",
                         "es": "{label}: no aplicado. {reason}"},
    "cv_reason_cover": {"pt": "Não foi possível medir a distância de cobertura deste atributo.",
                        "en": "The coverage distance of this attribute could not be measured.",
                        "es": "No se pudo medir la distancia de cobertura de este atributo."},
    "p4_item": {"pt": "<li>{layer}: <b>{field}</b> · P = {p} · raio = {r} ({origin})</li>",
                "en": "<li>{layer}: <b>{field}</b> · P = {p} · radius = {r} ({origin})</li>",
                "es": "<li>{layer}: <b>{field}</b> · P = {p} · radio = {r} ({origin})</li>"},
    "alg_p_auto": {
        "pt": "Escolher P e raio de cada atributo por validação cruzada (substitui os valores acima)",
        "en": "Choose P and radius of each attribute by cross-validation (replaces the values above)",
        "es": "Elegir P y radio de cada atributo por validación cruzada (reemplaza los valores de arriba)"},
    "alg_log_auto": {"pt": "{label}: P = {p}, raio = {r} m (validação cruzada, RMSE = {rmse})",
                     "en": "{label}: P = {p}, radius = {r} m (cross-validation, RMSE = {rmse})",
                     "es": "{label}: P = {p}, radio = {r} m (validación cruzada, RMSE = {rmse})"},
    "alg_log_auto_fail": {
        "pt": "{label}: validação cruzada não foi possível ({reason}); usando P = {p} e raio = {r}.",
        "en": "{label}: cross-validation not possible ({reason}); using P = {p} and radius = {r}.",
        "es": "{label}: validación cruzada no posible ({reason}); usando P = {p} y radio = {r}."},
    "p3_show_samples": {"pt": "Mostrar amostras", "en": "Show samples", "es": "Mostrar muestras"},
    "cv_title": {"pt": "Validação cruzada do IDW", "en": "IDW cross-validation",
                 "es": "Validación cruzada del IDW"},
    "cv_few": {"pt": "Só {n} amostras atendem aos critérios de validação (mínimo {min}). Aumente a "
                     "quantidade de amostras ou use outro atributo.",
               "en": "Only {n} samples meet the validation criteria (minimum {min}). Use more samples "
                     "or another attribute.",
               "es": "Solo {n} muestras cumplen los criterios de validación (mínimo {min}). Use más "
                     "muestras u otro atributo."},
    "cv_failed": {"pt": "Nenhuma combinação conseguiu estimar as amostras de validação. Verifique os dados.",
                  "en": "No combination could estimate the validation samples. Check the data.",
                  "es": "Ninguna combinación pudo estimar las muestras de validación. Verifique los datos."},
    "cv_header": {
        "pt": "<b>Atributo:</b> {attribute}<br><b>{n} amostras de validação</b>, espalhadas pelo talhão, "
              "longe da borda e sem valores discrepantes. Ao validar cada uma, as amostras a menos de "
              "{exclusion} m foram ignoradas (zona de exclusão). Distância de cobertura: {spacing} m.",
        "en": "<b>Attribute:</b> {attribute}<br><b>{n} validation samples</b>, spread over the field, "
              "away from the border and without outliers. When validating each one, samples closer "
              "than {exclusion} m were ignored (exclusion zone). Coverage distance: {spacing} m.",
        "es": "<b>Atributo:</b> {attribute}<br><b>{n} muestras de validación</b>, distribuidas en el "
              "lote, lejos del borde y sin valores atípicos. Al validar cada una, se ignoraron las "
              "muestras a menos de {exclusion} m (zona de exclusión). Distancia de cobertura: {spacing} m."},
    "cv_col": {"pt": "{mult}×\n({radius} m)", "en": "{mult}×\n({radius} m)", "es": "{mult}×\n({radius} m)"},
    "cv_axes": {"pt": "Linhas: potência P  ·  Colunas: raio de busca (múltiplos da distância de cobertura)",
                "en": "Rows: power P  ·  Columns: search radius (multiples of the coverage distance)",
                "es": "Filas: potencia P  ·  Columnas: radio de búsqueda (múltiplos de la distancia de cobertura)"},
    "cv_na": {"pt": "n/d", "en": "n/a", "es": "n/d"},
    "cv_na_tip": {"pt": "Raio curto demais: nenhuma amostra vizinha para estimar.",
                  "en": "Radius too short: no neighbouring sample to estimate from.",
                  "es": "Radio demasiado corto: ninguna muestra vecina para estimar."},
    "cv_cell_tip": {"pt": "{cov}% das amostras de validação foram estimadas (em cinza quando abaixo de 95%).",
                    "en": "{cov}% of the validation samples were estimated (grey when below 95%).",
                    "es": "{cov}% de las muestras de validación fueron estimadas (en gris por debajo de 95%)."},
    "cv_gap_tip": {"pt": "Este raio deixaria {gap}% do talhão sem valor (falhas no mapa), por isso não pode ser sugerido.",
                   "en": "This radius would leave {gap}% of the field without value (gaps in the map), so it cannot be suggested.",
                   "es": "Este radio dejaría el {gap}% del lote sin valor (huecos en el mapa), por eso no puede sugerirse."},
    "cv_best": {
        "pt": "<b>Melhor combinação: P = {p} e raio {mult}× ({radius} m).</b> Erro médio (RMSE) = {rmse}, "
              "cerca de {pct}% da média. O P foi refinado em passos de 0,1 para o raio escolhido.",
        "en": "<b>Best combination: P = {p} and radius {mult}× ({radius} m).</b> Mean error (RMSE) = {rmse}, "
              "about {pct}% of the mean. P was refined in 0.1 steps for the chosen radius.",
        "es": "<b>Mejor combinación: P = {p} y radio {mult}× ({radius} m).</b> Error medio (RMSE) = {rmse}, "
              "cerca del {pct}% de la media. P se refinó en pasos de 0,1 para el radio elegido."},
    "cv_explain": {
        "pt": "Cada número da tabela é o erro médio ao estimar as amostras de validação como se elas "
              "não existissem. Quanto menor, melhor o mapa representa os dados. Compare as linhas (P) e "
              "as colunas (raio) para ver como cada parâmetro muda o erro. Valores em cinza deixariam "
              "falhas no mapa e não são sugeridos.",
        "en": "Each number in the table is the average error when estimating the validation samples as "
              "if they did not exist. The lower, the better the map represents the data. Compare rows (P) "
              "and columns (radius) to see how each parameter changes the error. Grey values would leave "
              "gaps in the map and are not suggested.",
        "es": "Cada número de la tabla es el error medio al estimar las muestras de validación como si no "
              "existieran. Cuanto menor, mejor representa el mapa los datos. Compare filas (P) y columnas "
              "(radio) para ver cómo cada parámetro cambia el error. Los valores en gris dejarían huecos "
              "en el mapa y no se sugieren."},
    "cv_apply": {"pt": "Aplicar", "en": "Apply", "es": "Aplicar"},
    "cv_close": {"pt": "Fechar", "en": "Close", "es": "Cerrar"},
    "cv_more": {
        "pt": "<b>Validação cruzada</b><br><br>Algumas amostras são retiradas uma de cada vez e estimadas "
              "pelas demais, com cada combinação de P e raio. O erro (RMSE, raiz do erro quadrático "
              "médio) mostra qual combinação reproduz melhor os valores reais.<br><br>"
              "<b>Escolha das amostras de validação</b> (até 60, sorteio reprodutível):<ul>"
              "<li>espalhadas por todo o talhão (o talhão é dividido em blocos);</li>"
              "<li>longe da borda, onde o IDW tem menos vizinhos;</li>"
              "<li>sem valores discrepantes (fora de ±3 desvios padrão), que distorceriam o erro;</li>"
              "<li>equilibradas entre valores baixos, médios e altos, para que o ajuste valha para toda a "
              "variabilidade, e não só para os valores próximos da média.</li></ul>"
              "<b>Zona de exclusão:</b> dados de sensores (como a CE) têm pontos a 1 ou 2 m na mesma "
              "passada, quase iguais entre si. Se esses vizinhos fossem usados, o erro pareceria "
              "pequeno demais e o método escolheria sempre P alto e raio curto (Roberts et al., 2017, "
              "<i>Ecography</i> 40: 913-929). Por isso, ao validar cada amostra, as vizinhas mais próximas "
              "que a distância típica entre um pixel e a amostra mais próxima são ignoradas.<br><br>"
              "Para referência, Mueller et al. (2004, <i>Soil Science</i> 169: 841-851) obtiveram o melhor "
              "resultado com IDW de potência 1,7 em mapas de condutividade elétrica do solo.",
        "en": "<b>Cross-validation</b><br><br>Some samples are removed one at a time and estimated from "
              "the others with each combination of P and radius. The error (RMSE, root mean square "
              "error) shows which combination best reproduces the real values.<br><br>"
              "<b>Choice of validation samples</b> (up to 60, reproducible draw):<ul>"
              "<li>spread over the whole field (the field is split into blocks);</li>"
              "<li>away from the border, where IDW has fewer neighbours;</li>"
              "<li>without outliers (beyond ±3 standard deviations), which would distort the error;</li>"
              "<li>balanced among low, medium and high values, so the fit holds for all the variability, "
              "not only for values near the mean.</li></ul>"
              "<b>Exclusion zone:</b> sensor data (such as EC) have points 1 or 2 m apart on the same pass, "
              "almost identical. If those neighbours were used, the error would look too small and the "
              "method would always choose high P and a short radius (Roberts et al., 2017, "
              "<i>Ecography</i> 40: 913-929). So, when validating each sample, neighbours closer than the "
              "typical distance between a pixel and its nearest sample are ignored.<br><br>"
              "For reference, Mueller et al. (2004, <i>Soil Science</i> 169: 841-851) obtained the best "
              "results with IDW power 1.7 for soil electrical conductivity maps.",
        "es": "<b>Validación cruzada</b><br><br>Algunas muestras se retiran una a una y se estiman con las "
              "demás, con cada combinación de P y radio. El error (RMSE, raíz del error cuadrático medio) "
              "muestra qué combinación reproduce mejor los valores reales.<br><br>"
              "<b>Elección de las muestras de validación</b> (hasta 60, sorteo reproducible):<ul>"
              "<li>distribuidas por todo el lote (el lote se divide en bloques);</li>"
              "<li>lejos del borde, donde el IDW tiene menos vecinas;</li>"
              "<li>sin valores atípicos (fuera de ±3 desviaciones estándar), que distorsionarían el error;</li>"
              "<li>equilibradas entre valores bajos, medios y altos, para que el ajuste valga para toda la "
              "variabilidad y no solo para los valores cercanos a la media.</li></ul>"
              "<b>Zona de exclusión:</b> los datos de sensores (como la CE) tienen puntos a 1 o 2 m en la "
              "misma pasada, casi iguales. Si se usaran esas vecinas, el error parecería demasiado pequeño "
              "y el método elegiría siempre P alto y radio corto (Roberts et al., 2017, <i>Ecography</i> "
              "40: 913-929). Por eso, al validar cada muestra, se ignoran las vecinas más cercanas que la "
              "distancia típica entre un píxel y su muestra más próxima.<br><br>"
              "Como referencia, Mueller et al. (2004, <i>Soil Science</i> 169: 841-851) obtuvieron el mejor "
              "resultado con IDW de potencia 1,7 en mapas de conductividad eléctrica del suelo."},
    "p3_preview_n": {"pt": "{n} amostras", "en": "{n} samples", "es": "{n} muestras"},
    "p3_preview_note": {
        "pt": "Prévia em baixa resolução, só para comparar parâmetros. Vermelho = valores baixos, "
              "verde = valores altos, cinza = pixels sem amostras no raio. Pontos pretos = amostras.",
        "en": "Low-resolution preview, only to compare parameters. Red = low values, green = high "
              "values, grey = pixels without samples in the radius. Black dots = samples.",
        "es": "Vista previa de baja resolución, solo para comparar parámetros. Rojo = valores bajos, "
              "verde = valores altos, gris = píxeles sin muestras en el radio. Puntos negros = muestras."},
    "p3_preview_empty": {"pt": "Sem amostras para a prévia.", "en": "No samples for the preview.",
                         "es": "Sin muestras para la vista previa."},

    # ---------------------------------------------------------------- page 4
    "p4_title": {"pt": "Etapa 4 de 4: Resumo", "en": "Step 4 of 4: Summary", "es": "Paso 4 de 4: Resumen"},
    "p4_subtitle": {"pt": "Confira as escolhas e clique em Executar.",
                    "en": "Check your choices and click Run.",
                    "es": "Revise sus elecciones y haga clic en Ejecutar."},
    "p4_summary": {
        "pt": "<b>Contorno:</b> {boundary} ({crs}), {area} ha<br><b>Tolerância:</b> {tol} m<br>"
              "<b>Pasta de saída:</b> {folder}<br><br><b>Atributos e parâmetros do IDW ({n}):</b><ul>{items}</ul>"
              "<b>Pixel:</b> {pixel} m<br>"
              "<b>Estilo:</b> graduado, {classes} classes, quebras naturais (Jenks), {ramp}",
        "en": "<b>Boundary:</b> {boundary} ({crs}), {area} ha<br><b>Tolerance:</b> {tol} m<br>"
              "<b>Output folder:</b> {folder}<br><br><b>Attributes and IDW parameters ({n}):</b><ul>{items}</ul>"
              "<b>Pixel:</b> {pixel} m<br>"
              "<b>Style:</b> graduated, {classes} classes, natural breaks (Jenks), {ramp}",
        "es": "<b>Contorno:</b> {boundary} ({crs}), {area} ha<br><b>Tolerancia:</b> {tol} m<br>"
              "<b>Carpeta de salida:</b> {folder}<br><br><b>Atributos y parámetros del IDW ({n}):</b><ul>{items}</ul>"
              "<b>Píxel:</b> {pixel} m<br>"
              "<b>Estilo:</b> graduado, {classes} clases, cortes naturales (Jenks), {ramp}"},
    "help_page4": {
        "pt": "<b>Etapa 4: Resumo</b><br><br>Ao clicar em <b>Executar</b>:<br>"
              "1. cada atributo é interpolado por IDW e salvo como GeoTIFF;<br>"
              "2. é criada a grade de polígonos com o tamanho do pixel, recortada pelo contorno;<br>"
              "3. calcula-se a média dos pixels de cada atributo em cada célula (estatística zonal);<br>"
              "4. a grade é salva em GeoPackage e carregada uma vez por atributo no grupo "
              "'Interpolados', com estilo graduado.<br><br>Use <b>Voltar</b> para corrigir.",
        "en": "<b>Step 4: Summary</b><br><br>When you click <b>Run</b>:<br>"
              "1. each field is interpolated by IDW and saved as GeoTIFF;<br>"
              "2. a polygon grid with the pixel size is created and clipped by the boundary;<br>"
              "3. the mean of each field's pixels is computed per cell (zonal statistics);<br>"
              "4. the grid is saved as GeoPackage and loaded once per field in the "
              "'Interpolated' group, with a graduated style.<br><br>Use <b>Back</b> to make changes.",
        "es": "<b>Paso 4: Resumen</b><br><br>Al hacer clic en <b>Ejecutar</b>:<br>"
              "1. cada atributo se interpola por IDW y se guarda como GeoTIFF;<br>"
              "2. se crea la cuadrícula de polígonos con el tamaño del píxel, recortada por el contorno;<br>"
              "3. se calcula el promedio de los píxeles de cada atributo en cada celda (estadística zonal);<br>"
              "4. la cuadrícula se guarda en GeoPackage y se carga una vez por atributo en el grupo "
              "'Interpolados', con estilo graduado.<br><br>Use <b>Atrás</b> para corregir."},

    # ---------------------------------------------------------------- pipeline
    "log_interpolating": {"pt": "Interpolando {label}...", "en": "Interpolating {label}...",
                          "es": "Interpolando {label}..."},
    "log_params": {"pt": "  {label}: P = {p}, raio = {r}", "en": "  {label}: P = {p}, radius = {r}",
                   "es": "  {label}: P = {p}, radio = {r}"},
    "log_fixing": {"pt": "Corrigindo geometrias do contorno...", "en": "Fixing boundary geometries...",
                   "es": "Corrigiendo geometrías del contorno..."},
    "log_grid": {"pt": "Criando a grade de polígonos...", "en": "Creating the polygon grid...",
                 "es": "Creando la cuadrícula de polígonos..."},
    "log_clip": {"pt": "Recortando a grade pelo contorno...", "en": "Clipping the grid by the boundary...",
                 "es": "Recortando la cuadrícula por el contorno..."},
    "log_zonal": {"pt": "Estatística zonal: {label}...", "en": "Zonal statistics: {label}...",
                  "es": "Estadística zonal: {label}..."},
    "warn_no_values": {"pt": "{label}: nenhum valor válido na área, atributo ignorado.",
                       "en": "{label}: no valid value in the area, field skipped.",
                       "es": "{label}: ningún valor válido en el área, atributo omitido."},
    "warn_load": {"pt": "Não foi possível carregar a camada de {label}.",
                  "en": "Could not load the layer for {label}.",
                  "es": "No se pudo cargar la capa de {label}."},
    "err_nothing_interpolated": {"pt": "Nenhum atributo pôde ser interpolado.",
                                 "en": "No field could be interpolated.",
                                 "es": "Ningún atributo pudo ser interpolado."},
    "err_empty_grid": {"pt": "A grade recortada ficou vazia. Verifique o contorno.",
                       "en": "The clipped grid is empty. Check the boundary.",
                       "es": "La cuadrícula recortada quedó vacía. Verifique el contorno."},
    "err_create_file": {"pt": "Não foi possível criar o arquivo {path}",
                        "en": "Could not create file {path}",
                        "es": "No se pudo crear el archivo {path}"},
    "done_line": {"pt": "  {label}: {n} pontos usados", "en": "  {label}: {n} points used",
                  "es": "  {label}: {n} puntos usados"},
    "done_msg": {"pt": "Processamento concluído.\n\nAtributos interpolados:\n{summary}\n\n"
                       "Arquivos salvos em:\n{folder}\n\nGrade final: {output}",
                 "en": "Processing finished.\n\nInterpolated fields:\n{summary}\n\n"
                       "Files saved in:\n{folder}\n\nFinal grid: {output}",
                 "es": "Procesamiento finalizado.\n\nAtributos interpolados:\n{summary}\n\n"
                       "Archivos guardados en:\n{folder}\n\nCuadrícula final: {output}"},

    # ---------------------------------------------------------------- processing
    "alg_name": {"pt": "IDW em grade vetorial", "en": "IDW vector grid",
                 "es": "IDW en cuadrícula vectorial"},
    "alg_group": {"pt": "Interpolação", "en": "Interpolation", "es": "Interpolación"},
    "alg_p_boundary": {"pt": "Contorno da área (polígono)", "en": "Field boundary (polygon)",
                       "es": "Contorno del área (polígono)"},
    "alg_p_points": {"pt": "Camada de pontos", "en": "Point layer", "es": "Capa de puntos"},
    "alg_p_fields": {"pt": "Atributos a interpolar", "en": "Fields to interpolate",
                     "es": "Atributos a interpolar"},
    "alg_p_tolerance": {"pt": "Tolerância além do contorno (m)", "en": "Tolerance beyond boundary (m)",
                        "es": "Tolerancia más allá del contorno (m)"},
    "alg_p_power": {"pt": "Potência P do IDW", "en": "IDW power P", "es": "Potencia P del IDW"},
    "alg_p_radius": {"pt": "Raio de busca (m, 0 = sem limite)", "en": "Search radius (m, 0 = no limit)",
                     "es": "Radio de búsqueda (m, 0 = sin límite)"},
    "alg_p_pixel": {"pt": "Tamanho do pixel (m)", "en": "Pixel size (m)", "es": "Tamaño del píxel (m)"},
    "alg_p_folder": {"pt": "Pasta para os rasters interpolados", "en": "Folder for interpolated rasters",
                     "es": "Carpeta para los ráster interpolados"},
    "alg_p_output": {"pt": "Grade vetorial com médias", "en": "Vector grid with means",
                     "es": "Cuadrícula vectorial con promedios"},
    "alg_err_crs": {"pt": "A camada '{name}' está em {crs}. Reprojete para um sistema projetado em metros.",
                    "en": "Layer '{name}' is in {crs}. Reproject it to a projected CRS in metres.",
                    "es": "La capa '{name}' está en {crs}. Reproyéctela a un SRC proyectado en metros."},
    "alg_help": {
        "pt": "Interpola por IDW os atributos escolhidos de uma camada de pontos, cria uma grade de "
              "polígonos com o tamanho do pixel recortada pelo contorno e calcula, por estatística "
              "zonal, a média de cada atributo em cada célula.\n\n"
              "O retângulo envolvente do contorno define a área da interpolação. A tolerância aceita "
              "pontos um pouco fora do contorno. Raio 0 usa todas as amostras.\n\n"
              "Opção: escolher P e raio de cada atributo por validação cruzada.\n\n"
              "As camadas devem estar em um sistema projetado em metros. A saída é carregada com estilo "
              "graduado (5 classes, Jenks, RdYlGn) do primeiro atributo. Para uma camada estilizada por "
              "atributo, use o assistente em Vetor > AgriPrecisa.",
        "en": "Interpolates the chosen fields of a point layer by IDW, creates a polygon grid with the "
              "pixel size clipped by the boundary and computes, by zonal statistics, the mean of each "
              "field in each cell.\n\n"
              "The boundary bounding box defines the interpolation area. The tolerance accepts points "
              "slightly outside the boundary. Radius 0 uses all samples.\n\n"
              "Option: choose P and radius of each attribute by cross-validation.\n\n"
              "Layers must be in a projected CRS in metres. The output is loaded with a graduated style "
              "(5 classes, Jenks, RdYlGn) on the first field. For one styled layer per field, use the "
              "wizard in Vector > AgriPrecisa.",
        "es": "Interpola por IDW los atributos elegidos de una capa de puntos, crea una cuadrícula de "
              "polígonos con el tamaño del píxel recortada por el contorno y calcula, por estadística "
              "zonal, el promedio de cada atributo en cada celda.\n\n"
              "El rectángulo envolvente del contorno define el área de interpolación. La tolerancia "
              "acepta puntos algo fuera del contorno. Radio 0 usa todas las muestras.\n\n"
              "Opción: elegir P y radio de cada atributo por validación cruzada.\n\n"
              "Las capas deben estar en un SRC proyectado en metros. La salida se carga con estilo "
              "graduado (5 clases, Jenks, RdYlGn) del primer atributo. Para una capa con estilo por "
              "atributo, use el asistente en Vectorial > AgriPrecisa."},
}
