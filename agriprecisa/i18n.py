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
              "<b>Potência P:</b> controla quanto o peso cai com a distância. P = 1 gera mapa mais "
              "suave; P = 2 é o mais usado; P acima de 3 cria 'ilhas' em volta das amostras.<br><br>"
              "<b>Raio de busca:</b> só as amostras dentro desse raio entram no cálculo. Use um valor "
              "maior que a distância entre amostras (em grade de 1 ponto por hectare, cerca de "
              "100 m). Com 0 (Sem limite), todas são usadas. Pixels sem amostra no raio ficam sem "
              "valor.<br><br>"
              "<b>Tamanho do pixel:</b> lado de cada pixel do raster e de cada célula da grade "
              "vetorial. Padrão de 5 m.",
        "en": "<b>Step 3: IDW parameters</b><br><br>"
              "IDW (Inverse Distance Weighting) estimates each pixel as the average of nearby "
              "samples, giving more weight to the closest ones.<br><br>"
              "<b>Power P:</b> how fast the weight falls with distance. P = 1 gives a smoother map; "
              "P = 2 is the most common; P above 3 creates 'bull's-eyes' around samples.<br><br>"
              "<b>Search radius:</b> only samples within this radius are used. Use a value larger "
              "than the sample spacing (about 100 m for a 1 sample per hectare grid). With 0 "
              "(No limit), all samples are used. Pixels with no sample within the radius stay "
              "empty.<br><br>"
              "<b>Pixel size:</b> side of each raster pixel and of each vector grid cell. "
              "Default 5 m.",
        "es": "<b>Paso 3: Parámetros del IDW</b><br><br>"
              "El IDW (inverso de la distancia ponderada) estima cada píxel como el promedio de las "
              "muestras vecinas, dando más peso a las más cercanas.<br><br>"
              "<b>Potencia P:</b> controla cuánto cae el peso con la distancia. P = 1 da un mapa más "
              "suave; P = 2 es el más usado; P mayor que 3 crea 'islas' alrededor de las "
              "muestras.<br><br>"
              "<b>Radio de búsqueda:</b> solo se usan las muestras dentro de este radio. Use un valor "
              "mayor que la distancia entre muestras (unos 100 m en una grilla de 1 punto por "
              "hectárea). Con 0 (Sin límite), se usan todas. Los píxeles sin muestras en el radio "
              "quedan vacíos.<br><br>"
              "<b>Tamaño del píxel:</b> lado de cada píxel del ráster y de cada celda de la "
              "cuadrícula vectorial. Por defecto 5 m."},

    # ---------------------------------------------------------------- page 4
    "p4_title": {"pt": "Etapa 4 de 4: Resumo", "en": "Step 4 of 4: Summary", "es": "Paso 4 de 4: Resumen"},
    "p4_subtitle": {"pt": "Confira as escolhas e clique em Executar.",
                    "en": "Check your choices and click Run.",
                    "es": "Revise sus elecciones y haga clic en Ejecutar."},
    "p4_summary": {
        "pt": "<b>Contorno:</b> {boundary} ({crs}), {area} ha<br><b>Tolerância:</b> {tol} m<br>"
              "<b>Pasta de saída:</b> {folder}<br><br><b>Atributos ({n}):</b><ul>{items}</ul>"
              "<b>IDW:</b> P = {power}; raio = {radius}; pixel = {pixel} m<br>"
              "<b>Estilo:</b> graduado, {classes} classes, quebras naturais (Jenks), {ramp}",
        "en": "<b>Boundary:</b> {boundary} ({crs}), {area} ha<br><b>Tolerance:</b> {tol} m<br>"
              "<b>Output folder:</b> {folder}<br><br><b>Fields ({n}):</b><ul>{items}</ul>"
              "<b>IDW:</b> P = {power}; radius = {radius}; pixel = {pixel} m<br>"
              "<b>Style:</b> graduated, {classes} classes, natural breaks (Jenks), {ramp}",
        "es": "<b>Contorno:</b> {boundary} ({crs}), {area} ha<br><b>Tolerancia:</b> {tol} m<br>"
              "<b>Carpeta de salida:</b> {folder}<br><br><b>Atributos ({n}):</b><ul>{items}</ul>"
              "<b>IDW:</b> P = {power}; radio = {radius}; píxel = {pixel} m<br>"
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
              "As camadas devem estar em um sistema projetado em metros. A saída é carregada com estilo "
              "graduado (5 classes, Jenks, RdYlGn) do primeiro atributo. Para uma camada estilizada por "
              "atributo, use o assistente em Vetor > AgriPrecisa.",
        "en": "Interpolates the chosen fields of a point layer by IDW, creates a polygon grid with the "
              "pixel size clipped by the boundary and computes, by zonal statistics, the mean of each "
              "field in each cell.\n\n"
              "The boundary bounding box defines the interpolation area. The tolerance accepts points "
              "slightly outside the boundary. Radius 0 uses all samples.\n\n"
              "Layers must be in a projected CRS in metres. The output is loaded with a graduated style "
              "(5 classes, Jenks, RdYlGn) on the first field. For one styled layer per field, use the "
              "wizard in Vector > AgriPrecisa.",
        "es": "Interpola por IDW los atributos elegidos de una capa de puntos, crea una cuadrícula de "
              "polígonos con el tamaño del píxel recortada por el contorno y calcula, por estadística "
              "zonal, el promedio de cada atributo en cada celda.\n\n"
              "El rectángulo envolvente del contorno define el área de interpolación. La tolerancia "
              "acepta puntos algo fuera del contorno. Radio 0 usa todas las muestras.\n\n"
              "Las capas deben estar en un SRC proyectado en metros. La salida se carga con estilo "
              "graduado (5 clases, Jenks, RdYlGn) del primer atributo. Para una capa con estilo por "
              "atributo, use el asistente en Vectorial > AgriPrecisa."},
}
