# -*- coding: utf-8 -*-
"""
AgriPrecisa: interface texts in Portuguese, English and Spanish.

The language follows the QGIS interface locale: pt* -> Portuguese,
es* -> Spanish, anything else -> English.

To add or change a text, edit the STRINGS dictionary. Every key must have
the three languages (checked by tests/test_i18n.py).
"""

_LANG = None

# Last plugin version for which every Help text (help_page*, *_more, alg_help) was reviewed.
# Must be updated together with "version=" in metadata.txt (checked by tests/test_package.py).
HELP_REVIEWED_VERSION = "1.6.0"


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
    "p1_title": {"pt": "Etapa 1 de 4: Contorno da área, grade vetorial e pasta de saída",
                 "en": "Step 1 of 4: Field boundary, vector grid and output folder",
                 "es": "Paso 1 de 4: Contorno del área, cuadrícula vectorial y carpeta de salida"},
    "p1_subtitle": {"pt": "Escolha o polígono do talhão, a grade vetorial e onde os resultados serão salvos.",
                    "en": "Choose the field polygon, the vector grid and where results will be saved.",
                    "es": "Elija el polígono del lote, la cuadrícula vectorial y dónde se guardarán los resultados."},
    "p1_boundary": {"pt": "Camada de contorno (polígono):", "en": "Boundary layer (polygon):",
                    "es": "Capa de contorno (polígono):"},
    "p1_selected_only": {"pt": "Usar apenas as feições selecionadas",
                         "en": "Use selected features only",
                         "es": "Usar solo las entidades seleccionadas"},
    "p1_tolerance": {"pt": "Tolerância além do contorno:", "en": "Tolerance beyond boundary:",
                     "es": "Tolerancia más allá del contorno:"},
    "p1_folder": {"pt": "Pasta de saída:", "en": "Output folder:", "es": "Carpeta de salida:"},
    "p1_grid_group": {"pt": "Grade vetorial", "en": "Vector grid", "es": "Cuadrícula vectorial"},
    "p1_grid_new": {"pt": "Gerar grade nova", "en": "Create a new grid", "es": "Crear cuadrícula nueva"},
    "p1_cell_size": {"pt": "Tamanho da célula:", "en": "Cell size:", "es": "Tamaño de la celda:"},
    "p1_grid_existing": {"pt": "Usar grade existente:", "en": "Use an existing grid:",
                         "es": "Usar cuadrícula existente:"},
    "p1_grid_new_hint": {"pt": "Será salva na pasta de saída como \"{name}\", com células inteiras, para reutilizar depois.",
                         "en": "It will be saved in the output folder as \"{name}\", with whole cells, to reuse later.",
                         "es": "Se guardará en la carpeta de salida como \"{name}\", con celdas enteras, para reutilizar después."},
    "p1_grid_existing_hint": {"pt": "Serão usadas apenas as células que tocam o talhão.",
                              "en": "Only the cells touching the field will be used.",
                              "es": "Solo se usarán las celdas que tocan el lote."},
    "p1_grid_err_choose": {"pt": "Escolha a camada da grade existente.", "en": "Choose the existing grid layer.",
                           "es": "Elija la capa de la cuadrícula existente."},
    "p1_grid_err_outside": {"pt": "Nenhuma célula da grade escolhida toca o talhão.",
                            "en": "No cell of the chosen grid touches the field.",
                            "es": "Ninguna celda de la cuadrícula elegida toca el lote."},
    "p3_pixel_tip": {"pt": "O pixel da interpolação não pode ser maior que a célula da grade ({cell} m): cada célula precisa conter pixels para calcular a média.",
                     "en": "The interpolation pixel cannot be larger than the grid cell ({cell} m): each cell must contain pixels to compute the mean.",
                     "es": "El píxel de la interpolación no puede ser mayor que la celda de la cuadrícula ({cell} m): cada celda debe contener píxeles para calcular la media."},
    "p4_grid_new": {"pt": "nova, salva como {name}", "en": "new, saved as {name}", "es": "nueva, guardada como {name}"},
    "p4_grid_existing": {"pt": "existente: {name} (células de cerca de {cell} m)",
                         "en": "existing: {name} (cells of about {cell} m)",
                         "es": "existente: {name} (celdas de unos {cell} m)"},
    "grid_exists_title": {"pt": "Grade já existe", "en": "Grid already exists", "es": "La cuadrícula ya existe"},
    "grid_exists_text": {"pt": "A pasta de saída já tem a grade \"{name}\".\n\nDeseja reutilizá-la ou gerar de novo e sobrescrever o arquivo?",
                         "en": "The output folder already has the grid \"{name}\".\n\nReuse it, or create it again and overwrite the file?",
                         "es": "La carpeta de salida ya tiene la cuadrícula \"{name}\".\n\n¿Desea reutilizarla o crearla de nuevo y sobrescribir el archivo?"},
    "grid_reuse": {"pt": "Reutilizar", "en": "Reuse", "es": "Reutilizar"},
    "grid_overwrite": {"pt": "Sobrescrever", "en": "Overwrite", "es": "Sobrescribir"},
    "done_grid": {"pt": "Grade padrão: {grid}", "en": "Standard grid: {grid}", "es": "Cuadrícula estándar: {grid}"},
    "log_grid_existing": {"pt": "Usando a grade existente (células que tocam o talhão)...",
                          "en": "Using the existing grid (cells touching the field)...",
                          "es": "Usando la cuadrícula existente (celdas que tocan el lote)..."},
    "log_grid_reuse": {"pt": "Reutilizando a grade {path}", "en": "Reusing the grid {path}",
                       "es": "Reutilizando la cuadrícula {path}"},
    "log_grid_saved": {"pt": "Grade salva: {path}", "en": "Grid saved: {path}", "es": "Cuadrícula guardada: {path}"},
    "alg_p_cell": {"pt": "Tamanho da célula da grade (m)", "en": "Grid cell size (m)",
                   "es": "Tamaño de la celda de la cuadrícula (m)"},
    "alg_p_grid": {"pt": "Grade existente (opcional; substitui o tamanho da célula)",
                   "en": "Existing grid (optional; replaces the cell size)",
                   "es": "Cuadrícula existente (opcional; reemplaza el tamaño de la celda)"},
    "alg_err_pixel_cell": {"pt": "O pixel ({pixel} m) não pode ser maior que a célula da grade ({cell} m).",
                           "en": "The pixel ({pixel} m) cannot be larger than the grid cell ({cell} m).",
                           "es": "El píxel ({pixel} m) no puede ser mayor que la celda ({cell} m)."},
    "p1_folder_from_last": {"pt": "Última pasta usada.", "en": "Last folder used.",
                            "es": "Última carpeta usada."},
    "p1_folder_from_project": {
        "pt": "Subpasta AgriPrecisa dentro da pasta do projeto (será criada se não existir).",
        "en": "AgriPrecisa subfolder inside the project folder (created if it does not exist).",
        "es": "Subcarpeta AgriPrecisa dentro de la carpeta del proyecto (se creará si no existe)."},
    "p1_folder_none": {
        "pt": "Salve o projeto do QGIS para usar a pasta dele, ou escolha uma pasta.",
        "en": "Save the QGIS project to use its folder, or choose a folder.",
        "es": "Guarde el proyecto de QGIS para usar su carpeta, o elija una carpeta."},
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
    "p1_err_folder": {"pt": "Escolha uma pasta de saída. Não foi possível criar ou gravar na pasta informada.",
                      "en": "Choose an output folder. The folder could not be created or written to.",
                      "es": "Elija una carpeta de salida. No se pudo crear ni escribir en la carpeta indicada."},
    "help_page1": {
        "pt": "<b>Etapa 1: Contorno, grade vetorial e pasta de saída</b><br><br>"
              "<b>Camada de contorno:</b> polígono que delimita o talhão. O retângulo envolvente "
              "dele, acrescido de 100 m de margem, define a área da interpolação, e o contorno "
              "recorta a grade final depois do cálculo das médias. Se houver "
              "feições selecionadas, é possível usar apenas elas (por exemplo, um talhão de uma "
              "camada com vários).<br><br>"
              "<b>Tolerância:</b> distância, em metros, além do contorno em que os pontos ainda são "
              "aceitos. Inclui amostras que ficaram um pouco fora do limite, por exemplo em manobras. "
              "Também define quais camadas de pontos aparecem na próxima etapa.<br><br>"
              "<b>Grade vetorial:</b> gere uma grade nova escolhendo o tamanho da célula (por exemplo, "
              "10 × 10 m) ou use uma grade criada antes. A grade nova é salva como "
              "<i>&lt;contorno&gt;_Grade Padrão_10x10.shp</i>, com células inteiras, e pode ser reutilizada. "
              "A interpolação cobre o retângulo do talhão com 100 m de margem; a média é calculada em cada "
              "célula inteira e só depois a grade é recortada pelo contorno, para nenhuma célula da borda "
              "ficar sem valor.<br><br>"
              "<b>Pasta de saída:</b> onde ficam os rasters interpolados (GeoTIFF), a grade padrão e a grade "
              "final com as médias (Shapefile). Vem preenchida com a última pasta usada ou, na primeira "
              "vez, com a subpasta AgriPrecisa dentro da pasta do projeto, criada automaticamente.<br><br>"
              "<b>Sistema de coordenadas:</b> o contorno e os pontos precisam estar em um sistema "
              "projetado em metros, como SIRGAS 2000 / UTM 22S (EPSG:31982).",
        "en": "<b>Step 1: Boundary, vector grid and output folder</b><br><br>"
              "<b>Boundary layer:</b> polygon delimiting the field. Its bounding box, plus a 100 m "
              "margin, defines the interpolation area, and the boundary clips the final grid after "
              "the means are computed. If features are selected, you "
              "can use only them (e.g. one field from a layer with many).<br><br>"
              "<b>Tolerance:</b> distance, in metres, beyond the boundary within which points are "
              "still accepted. It keeps samples slightly outside the limit, e.g. from machine "
              "turns. It also defines which point layers are listed in the next step.<br><br>"
              "<b>Vector grid:</b> create a new grid choosing the cell size (e.g. 10 × 10 m) or use a grid "
              "created before. The new grid is saved as <i>&lt;boundary&gt;_Grade Padrão_10x10.shp</i>, with "
              "whole cells, and can be reused. Interpolation covers the field rectangle plus a 100 m margin; "
              "the mean is computed in each whole cell and only then the grid is clipped by the boundary, so "
              "no border cell is left without value.<br><br>"
              "<b>Output folder:</b> where the interpolated rasters (GeoTIFF), the standard grid and the final "
              "grid with the means (Shapefile) are saved. It is filled with the last folder used or, the "
              "first time, with the AgriPrecisa subfolder inside the project folder, created "
              "automatically.<br><br>"
              "<b>Coordinate system:</b> boundary and points must be in a projected CRS in "
              "metres, such as a UTM zone.",
        "es": "<b>Paso 1: Contorno, cuadrícula vectorial y carpeta de salida</b><br><br>"
              "<b>Capa de contorno:</b> polígono que delimita el lote. Su rectángulo envolvente, más "
              "100 m de margen, define el área de interpolación, y el contorno recorta la cuadrícula "
              "final después del cálculo de las medias. Si hay "
              "entidades seleccionadas, se pueden usar solo ellas (por ejemplo, un lote de una "
              "capa con varios).<br><br>"
              "<b>Tolerancia:</b> distancia, en metros, más allá del contorno dentro de la cual los "
              "puntos aún se aceptan. Incluye muestras algo fuera del límite, por ejemplo en "
              "maniobras. También define qué capas de puntos aparecen en el siguiente paso.<br><br>"
              "<b>Cuadrícula vectorial:</b> cree una cuadrícula nueva eligiendo el tamaño de la celda (por "
              "ejemplo, 10 × 10 m) o use una creada antes. La nueva se guarda como "
              "<i>&lt;contorno&gt;_Grade Padrão_10x10.shp</i>, con celdas enteras, y puede reutilizarse. La "
              "interpolación cubre el rectángulo del lote con 100 m de margen; la media se calcula en cada "
              "celda entera y solo después la cuadrícula se recorta por el contorno, para que ninguna celda del "
              "borde quede sin valor.<br><br>"
              "<b>Carpeta de salida:</b> donde se guardan los ráster interpolados (GeoTIFF), la cuadrícula "
              "estándar y la cuadrícula final con las medias (Shapefile). Viene con la última carpeta usada o, la "
              "primera vez, con la subcarpeta AgriPrecisa dentro de la carpeta del proyecto, creada "
              "automáticamente.<br><br>"
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
    "p3_subtitle": {
        "pt": "Ajuste a potência e o tamanho do pixel; o ajuste automático escolhe também o número de vizinhas.",
        "en": "Set the power and the pixel size; the auto-fit also chooses the number of neighbours.",
        "es": "Ajuste la potencia y el tamaño del píxel; el ajuste automático elige también el número de vecinas."},
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
        "pt": "<b>Etapa 3: Parâmetros do IDW</b><br><br>O IDW (inverso da distância ponderada) estima cada pixel pela média das amostras vizinhas, dando mais peso às mais próximas.<br><br><b>Cada atributo tem seus próprios parâmetros</b>, porque a dependência espacial e a variabilidade mudam de um atributo para outro. Escolha o atributo no topo; os controles e a prévia passam a valer para ele. A tabela mostra os parâmetros de todos e a origem de cada um (padrão, automático ou manual).<br><br><b>Potência P</b> (barra de 0,5 a 5,0): quanto maior, mais rápido o peso cai com a distância e mais o pixel se parece com a amostra mais próxima.<br><b>Vizinhas por pixel:</b> cada pixel usa no mínimo 4 e no máximo 16 amostras (padrão), sempre as mais próximas. O <b>Ajuste automático</b> escolhe o máximo de cada atributo, entre 4 e 32, junto com o P. As barras mostram a fatia de cada vizinha num pixel típico.<br><b>Avançado: raio de busca</b> (recolhido; clique no título para abrir). O raio só economiza cálculo em amostragens muito densas. Se ele alcançar menos de 4 amostras, as 4 mais próximas são usadas mesmo fora dele, e um aviso em laranja mostra em quantos % do talhão isso acontece; se alcançar mais que o máximo, só as mais próximas entram. É dado em múltiplos da distância de cobertura (1× a 10×), e começa no valor que alcança o máximo de vizinhas em 95% do talhão e o mínimo em todo ele (o ajuste automático recalcula do mesmo modo). Mover a barra não muda o mapa enquanto o raio não limitar a busca.<br><b>Ajuste automático / para todos:</b> a validação cruzada testa combinações de P e máximo de vizinhas e indica, para cada atributo, a de menor erro.<br><b>Prévia do mapa:</b> ocupa a coluna da direita e muda a cada ajuste. <b>Mostrar amostras</b> liga ou desliga os pontos.<br><b>Tamanho do pixel:</b> lado de cada pixel da interpolação. Começa igual ao tamanho da célula da grade escolhido na Etapa 1 e não pode ser maior que ele, porque cada célula precisa conter pixels para o cálculo da média. Pixels menores deixam a média de cada célula mais representativa, mas o cálculo fica mais lento.",
        "en": "<b>Step 3: IDW parameters</b><br><br>IDW (Inverse Distance Weighting) estimates each pixel as the average of nearby samples, giving more weight to the closest ones.<br><br><b>Each attribute has its own parameters</b>, because spatial dependence and variability change from one attribute to another. Choose the attribute at the top; the controls and the preview then apply to it. The table shows the parameters of all attributes and where each came from (default, auto-fit or manual).<br><br><b>Power P</b> (slider from 0.5 to 5.0): the higher it is, the faster the weight falls with distance and the more the pixel resembles the nearest sample.<br><b>Neighbours per pixel:</b> each pixel uses at least 4 and at most 16 samples (default), always the nearest ones. <b>Auto-fit</b> chooses the maximum of each attribute, between 4 and 32, together with P. The bars show each neighbour's share in a typical pixel.<br><b>Advanced: search radius</b> (collapsed; click the title to open). The radius only saves computation in very dense sampling. If it reaches fewer than 4 samples, the 4 nearest are used even beyond it, and an orange warning shows in what % of the field this happens; if it reaches more than the maximum, only the nearest ones are used. It is given in multiples of the coverage distance (1× to 10×), and it starts at the value that reaches the maximum of neighbours in 95% of the field and the minimum in all of it (the auto-fit recomputes it the same way). Moving the slider does not change the map while the radius does not limit the search.<br><b>Auto-fit / Auto-fit all:</b> cross-validation tests combinations of P and maximum of neighbours and points out, for each attribute, the one with the lowest error.<br><b>Map preview:</b> fills the right column and changes with every adjustment. <b>Show samples</b> turns the points on or off.<br><b>Pixel size:</b> side of each interpolation pixel. It starts equal to the grid cell size chosen in step 1 and cannot be larger, because each cell must contain pixels to compute the mean. Smaller pixels make each cell's mean more representative, but processing is slower.",
        "es": "<b>Paso 3: Parámetros del IDW</b><br><br>El IDW (inverso de la distancia ponderada) estima cada píxel como el promedio de las muestras vecinas, dando más peso a las más cercanas.<br><br><b>Cada atributo tiene sus propios parámetros</b>, porque la dependencia espacial y la variabilidad cambian de un atributo a otro. Elija el atributo arriba; los controles y la vista previa pasan a valer para él. La tabla muestra los parámetros de todos y el origen de cada uno (por defecto, automático o manual).<br><br><b>Potencia P</b> (barra de 0,5 a 5,0): cuanto mayor, más rápido cae el peso con la distancia y más se parece el píxel a la muestra más cercana.<br><b>Vecinas por píxel:</b> cada píxel usa como mínimo 4 y como máximo 16 muestras (por defecto), siempre las más cercanas. El <b>Ajuste automático</b> elige el máximo de cada atributo, entre 4 y 32, junto con P. Las barras muestran la parte de cada vecina en un píxel típico.<br><b>Avanzado: radio de búsqueda</b> (plegado; haga clic en el título para abrirlo). El radio solo ahorra cálculo en muestreos muy densos. Si alcanza menos de 4 muestras, se usan las 4 más cercanas aunque estén fuera de él, y un aviso en naranja muestra en qué % del lote ocurre; si alcanza más que el máximo, solo entran las más cercanas. Se da en múltiplos de la distancia de cobertura (1× a 10×), y empieza en el valor que alcanza el máximo de vecinas en el 95% del lote y el mínimo en todo él (el ajuste automático lo recalcula igual). Mover la barra no cambia el mapa mientras el radio no limite la búsqueda.<br><b>Ajuste automático / para todos:</b> la validación cruzada prueba combinaciones de P y máximo de vecinas e indica, para cada atributo, la de menor error.<br><b>Vista previa del mapa:</b> ocupa la columna derecha y cambia con cada ajuste. <b>Mostrar muestras</b> enciende o apaga los puntos.<br><b>Tamaño del píxel:</b> lado de cada píxel de la interpolación. Empieza igual al tamaño de la celda elegido en el paso 1 y no puede ser mayor, porque cada celda debe contener píxeles para calcular la media. Píxeles menores hacen la media de cada celda más representativa, pero el cálculo es más lento."},
    "learn_more": {"pt": "Saiba mais", "en": "Learn more", "es": "Saber más"},
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
    "p3_spacing": {
        "pt": "Distância de cobertura: 95% do talhão fica a até {spacing} m de uma amostra "
              "({density} amostras/ha).",
        "en": "Coverage distance: 95% of the field is within {spacing} m of a sample "
              "({density} samples/ha).",
        "es": "Distancia de cobertura: el 95% del lote está a menos de {spacing} m de una muestra "
              "({density} muestras/ha)."},
    "p3_spacing_none": {
        "pt": "Não foi possível medir a distância de cobertura deste atributo; o raio fica fixo em 100 m. "
              "Verifique se há amostras dentro do talhão.",
        "en": "The coverage distance of this attribute could not be measured; the radius stays at 100 m. Check that there are samples inside the field.",
        "es": "No se pudo medir la distancia de cobertura de este atributo; el radio queda en 100 m. "
              "Verifique que haya muestras dentro del lote."},
    "p3_radius_value": {"pt": "Raio = {mult} × {spacing} m = {radius} m",
                        "en": "Radius = {mult} × {spacing} m = {radius} m",
                        "es": "Radio = {mult} × {spacing} m = {radius} m"},
    "p3_radius_gap": {
        "pt": "Em {pct}% do talhão este raio alcança menos de {k} amostras (vãos entre passadas ou amostras). Nesses pontos são usadas as {k} mais próximas, mesmo fora do raio, para o mapa não ficar com falhas.",
        "en": "In {pct}% of the field this radius reaches fewer than {k} samples (gaps between passes or samples). There the {k} nearest are used, even beyond the radius, so the map has no gaps.",
        "es": "En el {pct}% del lote este radio alcanza menos de {k} muestras (huecos entre pasadas o muestras). Allí se usan las {k} más cercanas, aunque estén fuera del radio, para que el mapa no tenga huecos."},
    "p3_radius_short": {
        "pt": "Raio curto: em parte do talhão ele não alcança o mínimo de {kmin} amostras, e a busca continua além dele até completar o mínimo.",
        "en": "Short radius: in part of the field it does not reach the minimum of {kmin} samples, and the search goes beyond it until the minimum is met.",
        "es": "Radio corto: en parte del lote no alcanza el mínimo de {kmin} muestras, y la búsqueda sigue más allá hasta completar el mínimo."},
    "p3_radius_ok": {
        "pt": "O raio não limita: quem decide quantas amostras entram é o máximo de {kmax} vizinhas. O raio só economiza cálculo em amostragens muito densas.",
        "en": "The radius does not limit: the maximum of {kmax} neighbours decides how many samples are used. The radius only saves computation in very dense sampling.",
        "es": "El radio no limita: quien decide cuántas muestras entran es el máximo de {kmax} vecinas. El radio solo ahorra cálculo en muestreos muy densos."},
    "p3_radius_more": {
        "pt": "<b>Raio de busca</b><br><br>O raio é um recurso para diminuir o cálculo quando a amostragem é muito densa: o programa só olha as amostras dentro dele. Quem decide quantas amostras entram em cada pixel são o <b>mínimo</b> e o <b>máximo de vizinhas</b>: se o raio alcançar menos que o mínimo, a busca continua além dele; se alcançar mais que o máximo, só as mais próximas entram.<br><br>A barra usa a <b>distância de cobertura</b>: mede-se, para os pixels do talhão, a distância até a amostra mais próxima, e 95% deles ficam a até essa distância. Ela funciona tanto para amostragem em grade quanto para sensores em passadas (como a CE), em que os pontos ficam muito próximos na linha e distantes entre as linhas.<br><br>O <b>Ajuste automático</b> calcula o raio para que ele alcance o máximo de vizinhas em 95% do talhão. Um aviso em laranja mostra em quantos % do talhão o raio não alcança o mínimo. Em pesquisa, o alcance do semivariograma é uma boa referência para o raio.",
        "en": "<b>Search radius</b><br><br>The radius is a way to reduce computation when sampling is very dense: the program only looks at samples inside it. How many samples each pixel uses is decided by the <b>minimum</b> and <b>maximum of neighbours</b>: if the radius reaches fewer than the minimum, the search goes beyond it; if it reaches more than the maximum, only the nearest ones are used.<br><br>The slider uses the <b>coverage distance</b>: for the field pixels, the distance to the nearest sample is measured, and 95% of them are within this distance. It works both for grid sampling and for sensor passes (such as EC), where points are very close along the line and far apart between lines.<br><br><b>Auto-fit</b> sets the radius so it reaches the maximum of neighbours in 95% of the field. An orange warning shows in what % of the field the radius does not reach the minimum. In research, the semivariogram range is a good reference for the radius.",
        "es": "<b>Radio de búsqueda</b><br><br>El radio es un recurso para reducir el cálculo cuando el muestreo es muy denso: el programa solo mira las muestras dentro de él. Cuántas muestras usa cada píxel lo deciden el <b>mínimo</b> y el <b>máximo de vecinas</b>: si el radio alcanza menos que el mínimo, la búsqueda sigue más allá; si alcanza más que el máximo, solo entran las más cercanas.<br><br>La barra usa la <b>distancia de cobertura</b>: se mide, para los píxeles del lote, la distancia a la muestra más cercana, y el 95% de ellos está a menos de esa distancia. Funciona tanto para muestreo en grilla como para sensores en pasadas (como la CE), donde los puntos están muy cerca en la línea y lejos entre líneas.<br><br>El <b>Ajuste automático</b> calcula el radio para que alcance el máximo de vecinas en el 95% del lote. Un aviso en naranja muestra en qué % del lote el radio no alcanza el mínimo. En investigación, el alcance del semivariograma es una buena referencia para el radio."},
    "p3_bars_tip": {
        "pt": "Parte de cada vizinha usada (λ = w / Σw) no valor de um pixel típico do talhão. As partes somam 100%.",
        "en": "Share of each neighbour used (λ = w / Σw) in the value of a typical pixel of the field. Shares add up to 100%.",
        "es": "Parte de cada vecina usada (λ = w / Σw) en el valor de un píxel típico del lote. Las partes suman 100%."},
    "p3_bars_title": {"pt": "Influência no pixel típico", "en": "Influence on a typical pixel",
                      "es": "Influencia en el píxel típico"},
    "p3_bars_row": {"pt": "{k}ª ({d} m)", "en": "#{k} ({d} m)", "es": "{k}.ª ({d} m)"},
    "p3_bars_rest": {"pt": "outras {n}", "en": "other {n}", "es": "otras {n}"},
    "p3_bars_total": {
        "pt": "{n} vizinhas usadas = 100%",
        "en": "{n} neighbours used = 100%",
        "es": "{n} vecinas usadas = 100%"},
    "p3_bars_empty": {
        "pt": "Sem amostras no pixel típico.",
        "en": "No samples at the typical pixel.",
        "es": "Sin muestras en el píxel típico."},
    "p3_weight_more": {
        "pt": "<b>Como o IDW calcula os pesos</b> (Shepard, 1968)<br><br>Cada vizinha i recebe o peso <b>w<sub>i</sub> = 1 / d<sub>i</sub><sup>P</sup></b>, em que d<sub>i</sub> é a distância entre o pixel e a amostra. O valor do pixel é a média ponderada <b>ẑ = Σ w<sub>i</sub> z<sub>i</sub> / Σ w<sub>i</sub></b>. Assim, o que conta é a fatia de cada vizinha, <b>λ<sub>i</sub> = w<sub>i</sub> / Σ w<sub>j</sub></b>, e as fatias somam 100%.<ul><li><b>Perto da amostra</b> o peso cresce sem limite: um pixel exatamente sobre uma amostra recebe o valor dela (o IDW é um interpolador exato).</li><li><b>As barras</b> mostram, num pixel típico do talhão, a fatia de cada vizinha que ele realmente usa (entre o mínimo e o máximo de vizinhas). Mova a barra do P e veja a influência se concentrar na mais próxima (P alto) ou se distribuir entre as vizinhas (P baixo).</li></ul>Referência: Shepard, D. (1968). A two-dimensional interpolation function for irregularly-spaced data. <i>Proceedings of the 23rd ACM National Conference</i>, 517-524.",
        "en": "<b>How IDW computes the weights</b> (Shepard, 1968)<br><br>Each neighbour i gets the weight <b>w<sub>i</sub> = 1 / d<sub>i</sub><sup>P</sup></b>, where d<sub>i</sub> is the distance between the pixel and the sample. The pixel value is the weighted mean <b>ẑ = Σ w<sub>i</sub> z<sub>i</sub> / Σ w<sub>i</sub></b>. So what matters is each neighbour's share, <b>λ<sub>i</sub> = w<sub>i</sub> / Σ w<sub>j</sub></b>, and the shares add up to 100%.<ul><li><b>Near the sample</b> the weight grows without limit: a pixel exactly on a sample takes its value (IDW is an exact interpolator).</li><li><b>The bars</b> show, for a typical pixel of the field, the share of each neighbour it really uses (between the minimum and the maximum of neighbours). Move the P slider and watch the influence concentrate on the nearest sample (high P) or spread among neighbours (low P).</li></ul>Reference: Shepard, D. (1968). A two-dimensional interpolation function for irregularly-spaced data. <i>Proceedings of the 23rd ACM National Conference</i>, 517-524.",
        "es": "<b>Cómo calcula el IDW los pesos</b> (Shepard, 1968)<br><br>Cada vecina i recibe el peso <b>w<sub>i</sub> = 1 / d<sub>i</sub><sup>P</sup></b>, donde d<sub>i</sub> es la distancia entre el píxel y la muestra. El valor del píxel es el promedio ponderado <b>ẑ = Σ w<sub>i</sub> z<sub>i</sub> / Σ w<sub>i</sub></b>. Así, lo que cuenta es la parte de cada vecina, <b>λ<sub>i</sub> = w<sub>i</sub> / Σ w<sub>j</sub></b>, y las partes suman 100%.<ul><li><b>Cerca de la muestra</b> el peso crece sin límite: un píxel exactamente sobre una muestra recibe su valor (el IDW es un interpolador exacto).</li><li><b>Las barras</b> muestran, en un píxel típico del lote, la parte de cada vecina que realmente usa (entre el mínimo y el máximo de vecinas). Mueva la barra de P y vea la influencia concentrarse en la más cercana (P alto) o repartirse entre las vecinas (P bajo).</li></ul>Referencia: Shepard, D. (1968). A two-dimensional interpolation function for irregularly-spaced data. <i>Proceedings of the 23rd ACM National Conference</i>, 517-524."},
    "p3_preview_group": {"pt": "Prévia do mapa", "en": "Map preview", "es": "Vista previa del mapa"},
    "p3_neigh_group": {
        "pt": "Vizinhas por pixel",
        "en": "Neighbours per pixel",
        "es": "Vecinas por píxel"},
    "p3_neigh_text": {
        "pt": "Cada pixel usa no mínimo <b>{kmin}</b> e no máximo <b>{kmax}</b> amostras, sempre as mais próximas.",
        "en": "Each pixel uses at least <b>{kmin}</b> and at most <b>{kmax}</b> samples, always the nearest ones.",
        "es": "Cada píxel usa como mínimo <b>{kmin}</b> y como máximo <b>{kmax}</b> muestras, siempre las más cercanas."},
    "p3_neigh_default": {
        "pt": "Valores padrão; o <b>Ajuste automático</b> escolhe o máximo de cada atributo.",
        "en": "Default values; <b>Auto-fit</b> chooses the maximum for each attribute.",
        "es": "Valores por defecto; el <b>Ajuste automático</b> elige el máximo de cada atributo."},
    "p3_neigh_cv": {
        "pt": "Máximo escolhido pelo ajuste automático (validação cruzada).",
        "en": "Maximum chosen by the auto-fit (cross-validation).",
        "es": "Máximo elegido por el ajuste automático (validación cruzada)."},
    "p3_neigh_more": {
        "pt": "<b>Mínimo e máximo de vizinhas</b><br><br>Os interpoladores dos programas de SIG não usam todas as amostras em cada pixel: escolhem as vizinhas por três regras, aplicadas nesta ordem.<ul><li><b>Raio de busca:</b> entram as amostras dentro dele. Serve para economizar cálculo quando a amostragem é muito densa (milhares de pontos de sensor).</li><li><b>Mínimo de vizinhas:</b> se o raio alcançar menos amostras que o mínimo, as mais próximas são buscadas mesmo fora dele. Assim nenhum pixel fica sem valor, por exemplo num vão maior entre passadas.</li><li><b>Máximo de vizinhas:</b> se o raio alcançar mais amostras que o máximo, só as mais próximas entram. O máximo limita o raio.</li></ul><b>Como o máximo muda o mapa:</b> poucas vizinhas deixam o mapa mais local, com mais detalhe e mais ruído; muitas vizinhas suavizam, porque cada pixel passa a ser uma média de uma área maior. O <b>Ajuste automático</b> testa máximos de 4 a 32 junto com o P e escolhe a combinação de menor erro para cada atributo. O mínimo fica em 4.<br><br>Nas barras, veja quantas vizinhas o pixel típico realmente usa e a fatia de cada uma.",
        "en": "<b>Minimum and maximum of neighbours</b><br><br>GIS interpolators do not use every sample at each pixel: they pick the neighbours with three rules, applied in this order.<ul><li><b>Search radius:</b> samples inside it are taken. It saves computation when sampling is very dense (thousands of sensor points).</li><li><b>Minimum of neighbours:</b> if the radius reaches fewer samples than the minimum, the nearest ones are taken even beyond it. So no pixel is left without value, for example in a wider gap between passes.</li><li><b>Maximum of neighbours:</b> if the radius reaches more samples than the maximum, only the nearest ones are used. The maximum limits the radius.</li></ul><b>How the maximum changes the map:</b> few neighbours make the map more local, with more detail and more noise; many neighbours smooth it, because each pixel becomes the mean of a larger area. <b>Auto-fit</b> tests maxima from 4 to 32 together with P and chooses the combination with the lowest error for each attribute. The minimum stays at 4.<br><br>In the bars, see how many neighbours the typical pixel really uses and each one's share.",
        "es": "<b>Mínimo y máximo de vecinas</b><br><br>Los interpoladores de los programas de SIG no usan todas las muestras en cada píxel: eligen las vecinas con tres reglas, aplicadas en este orden.<ul><li><b>Radio de búsqueda:</b> entran las muestras dentro de él. Sirve para ahorrar cálculo cuando el muestreo es muy denso (miles de puntos de sensor).</li><li><b>Mínimo de vecinas:</b> si el radio alcanza menos muestras que el mínimo, se buscan las más cercanas aunque estén fuera de él. Así ningún píxel queda sin valor, por ejemplo en un hueco mayor entre pasadas.</li><li><b>Máximo de vecinas:</b> si el radio alcanza más muestras que el máximo, solo entran las más cercanas. El máximo limita el radio.</li></ul><b>Cómo el máximo cambia el mapa:</b> pocas vecinas dejan el mapa más local, con más detalle y más ruido; muchas vecinas lo suavizan, porque cada píxel pasa a ser un promedio de un área mayor. El <b>Ajuste automático</b> prueba máximos de 4 a 32 junto con P y elige la combinación de menor error para cada atributo. El mínimo queda en 4.<br><br>En las barras, vea cuántas vecinas usa realmente el píxel típico y la parte de cada una."},
    "p3_advanced_group": {
        "pt": "Avançado: raio de busca",
        "en": "Advanced: search radius",
        "es": "Avanzado: radio de búsqueda"},
    "p3_radius_limits": {
        "pt": "O raio está limitando a busca: em {pct}% do talhão ele alcança menos de {kmax} amostras, e esses pixels usam só as que estão dentro dele (no mínimo {kmin}).",
        "en": "The radius is limiting the search: in {pct}% of the field it reaches fewer than {kmax} samples, and those pixels use only the ones inside it (at least {kmin}).",
        "es": "El radio está limitando la búsqueda: en el {pct}% del lote alcanza menos de {kmax} muestras, y esos píxeles usan solo las que están dentro de él (como mínimo {kmin})."},
    "sum_col_n": {
        "pt": "Vizinhas",
        "en": "Neighbours",
        "es": "Vecinas"},
    "sum_n_value": {
        "pt": "{kmin} a {kmax}",
        "en": "{kmin} to {kmax}",
        "es": "{kmin} a {kmax}"},
    "layer_neigh": {
        "pt": "V={kmin}-{kmax}",
        "en": "N={kmin}-{kmax}",
        "es": "V={kmin}-{kmax}"},
    "alg_p_min_n": {
        "pt": "Mínimo de vizinhas (usadas mesmo fora do raio)",
        "en": "Minimum of neighbours (used even beyond the radius)",
        "es": "Mínimo de vecinas (usadas aunque estén fuera del radio)"},
    "alg_p_max_n": {
        "pt": "Máximo de vizinhas (0 = sem limite)",
        "en": "Maximum of neighbours (0 = no limit)",
        "es": "Máximo de vecinas (0 = sin límite)"},
    "alg_err_neighbours": {
        "pt": "O máximo de vizinhas ({kmax}) não pode ser menor que o mínimo ({kmin}).",
        "en": "The maximum of neighbours ({kmax}) cannot be smaller than the minimum ({kmin}).",
        "es": "El máximo de vecinas ({kmax}) no puede ser menor que el mínimo ({kmin})."},
    "p3_preview_attr": {"pt": "Atributo:", "en": "Attribute:", "es": "Atributo:"},
    "p3_attribute": {"pt": "Atributo:", "en": "Attribute:", "es": "Atributo:"},
    "p3_summary_group": {"pt": "Parâmetros por atributo", "en": "Parameters per attribute",
                         "es": "Parámetros por atributo"},
    "sum_col_attr": {"pt": "Atributo", "en": "Attribute", "es": "Atributo"},
    "sum_col_p": {"pt": "P", "en": "P", "es": "P"},
    "sum_col_r": {"pt": "Raio", "en": "Radius", "es": "Radio"},
    "sum_col_origin": {"pt": "Origem", "en": "Origin", "es": "Origen"},
    "origin_default": {"pt": "padrão", "en": "default", "es": "por defecto"},
    "origin_cv": {"pt": "automático", "en": "auto-fit", "es": "automático"},
    "origin_manual": {"pt": "manual", "en": "manual", "es": "manual"},
    "origin_default_tip": {
        "pt": "Valor inicial: P = 2, de 4 a 16 vizinhas e raio calculado para alcançar as 16 vizinhas em 95% do talhão (e as 4 em todo ele).",
        "en": "Initial value: P = 2, 4 to 16 neighbours and a radius computed to reach the 16 neighbours in 95% of the field (and the 4 in all of it).",
        "es": "Valor inicial: P = 2, de 4 a 16 vecinas y radio calculado para alcanzar las 16 vecinas en el 95% del lote (y las 4 en todo él)."},
    "origin_cv_tip": {"pt": "Obtido pelo ajuste automático (validação cruzada deste atributo).",
                      "en": "Obtained by auto-fit (cross-validation of this attribute).",
                      "es": "Obtenido por el ajuste automático (validación cruzada de este atributo)."},
    "origin_manual_tip": {"pt": "Ajustado pelo usuário.", "en": "Set by the user.",
                          "es": "Ajustado por el usuario."},
    "cv_this": {"pt": "Ajuste automático", "en": "Auto-fit", "es": "Ajuste automático"},
    "cv_this_tip": {
        "pt": "Validação cruzada do atributo selecionado, com a tabela de erro por P e máximo de vizinhas.",
        "en": "Cross-validation of the selected attribute, with the error table by P and maximum of neighbours.",
        "es": "Validación cruzada del atributo seleccionado, con la tabla de error por P y máximo de vecinas."},
    "cv_all": {"pt": "Ajuste automático para todos", "en": "Auto-fit all", "es": "Ajuste automático para todos"},
    "cv_all_tip": {
        "pt": "Faz a validação cruzada de cada atributo e aplica P e máximo de vizinhas próprios a cada um.",
        "en": "Cross-validates each attribute and applies its own P and maximum of neighbours to each one.",
        "es": "Valida cada atributo y aplica a cada uno su propio P y máximo de vecinas."},
    "cv_all_progress": {"pt": "Validação cruzada: {label}...", "en": "Cross-validation: {label}...",
                        "es": "Validación cruzada: {label}..."},
    "cv_all_done": {"pt": "Parâmetros sugeridos e aplicados a cada atributo:\n\n{lines}",
                    "en": "Parameters suggested and applied to each attribute:\n\n{lines}",
                    "es": "Parámetros sugeridos y aplicados a cada atributo:\n\n{lines}"},
    "cv_all_line": {
        "pt": "{label}: P = {p}, até {kmax} vizinhas (raio {radius} m), RMSE = {rmse}",
        "en": "{label}: P = {p}, up to {kmax} neighbours (radius {radius} m), RMSE = {rmse}",
        "es": "{label}: P = {p}, hasta {kmax} vecinas (radio {radius} m), RMSE = {rmse}"},
    "cv_all_fail_line": {"pt": "{label}: não aplicado. {reason}", "en": "{label}: not applied. {reason}",
                         "es": "{label}: no aplicado. {reason}"},
    "cv_reason_cover": {"pt": "Não foi possível medir a distância de cobertura deste atributo.",
                        "en": "The coverage distance of this attribute could not be measured.",
                        "es": "No se pudo medir la distancia de cobertura de este atributo."},
    "p4_item": {
        "pt": "<li>{layer}: <b>{field}</b> · P = {p} · vizinhas {kmin} a {kmax} · raio = {r} ({origin})</li>",
        "en": "<li>{layer}: <b>{field}</b> · P = {p} · neighbours {kmin} to {kmax} · radius = {r} ({origin})</li>",
        "es": "<li>{layer}: <b>{field}</b> · P = {p} · vecinas {kmin} a {kmax} · radio = {r} ({origin})</li>"},
    "alg_p_auto": {
        "pt": "Escolher P e máximo de vizinhas de cada atributo por validação cruzada; o raio é calculado para não cortar o máximo (substitui os valores acima)",
        "en": "Choose P and maximum of neighbours of each attribute by cross-validation; the radius is computed so it does not cut the maximum (replaces the values above)",
        "es": "Elegir P y máximo de vecinas de cada atributo por validación cruzada; el radio se calcula para no cortar el máximo (reemplaza los valores de arriba)"},
    "alg_log_auto": {
        "pt": "{label}: P = {p}, até {kmax} vizinhas, raio = {r} m (validação cruzada, RMSE = {rmse})",
        "en": "{label}: P = {p}, up to {kmax} neighbours, radius = {r} m (cross-validation, RMSE = {rmse})",
        "es": "{label}: P = {p}, hasta {kmax} vecinas, radio = {r} m (validación cruzada, RMSE = {rmse})"},
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
        "pt": "<b>Atributo:</b> {attribute}<br><b>{n} amostras de validação</b>, espalhadas pelo talhão, longe da borda e sem valores discrepantes. Ao validar cada uma, as amostras a menos de {exclusion} m foram ignoradas (zona de exclusão). Mínimo de {kmin} vizinhas. Distância de cobertura: {spacing} m.",
        "en": "<b>Attribute:</b> {attribute}<br><b>{n} validation samples</b>, spread over the field, away from the border and without outliers. When validating each one, samples closer than {exclusion} m were ignored (exclusion zone). Minimum of {kmin} neighbours. Coverage distance: {spacing} m.",
        "es": "<b>Atributo:</b> {attribute}<br><b>{n} muestras de validación</b>, distribuidas en el lote, lejos del borde y sin valores atípicos. Al validar cada una, se ignoraron las muestras a menos de {exclusion} m (zona de exclusión). Mínimo de {kmin} vecinas. Distancia de cobertura: {spacing} m."},
    "cv_col": {
        "pt": "até {k}\nvizinhas",
        "en": "up to {k}\nneighbours",
        "es": "hasta {k}\nvecinas"},
    "cv_axes": {
        "pt": "Linhas: potência P  ·  Colunas: máximo de vizinhas (o mínimo fica em 4)",
        "en": "Rows: power P  ·  Columns: maximum of neighbours (the minimum stays at 4)",
        "es": "Filas: potencia P  ·  Columnas: máximo de vecinas (el mínimo queda en 4)"},
    "cv_na": {"pt": "n/d", "en": "n/a", "es": "n/d"},
    "cv_na_tip": {
        "pt": "Nenhuma amostra vizinha para estimar.",
        "en": "No neighbouring sample to estimate from.",
        "es": "Ninguna muestra vecina para estimar."},
    "cv_cell_tip": {"pt": "{cov}% das amostras de validação foram estimadas (em cinza quando abaixo de 95%).",
                    "en": "{cov}% of the validation samples were estimated (grey when below 95%).",
                    "es": "{cov}% de las muestras de validación fueron estimadas (en gris por debajo de 95%)."},
    "cv_best": {
        "pt": "<b>Melhor combinação: P = {p} e até {kmax} vizinhas.</b> Erro médio (RMSE) = {rmse}, cerca de {pct}% da média. O P foi refinado em passos de 0,1 para esse máximo. O raio de busca fica em {radius} m, para não cortar as {kmax} vizinhas em 95% do talhão.",
        "en": "<b>Best combination: P = {p} and up to {kmax} neighbours.</b> Mean error (RMSE) = {rmse}, about {pct}% of the mean. P was refined in 0.1 steps for this maximum. The search radius is set to {radius} m, so it does not cut the {kmax} neighbours in 95% of the field.",
        "es": "<b>Mejor combinación: P = {p} y hasta {kmax} vecinas.</b> Error medio (RMSE) = {rmse}, cerca del {pct}% de la media. P se refinó en pasos de 0,1 para ese máximo. El radio de búsqueda queda en {radius} m, para no cortar las {kmax} vecinas en el 95% del lote."},
    "cv_explain": {
        "pt": "Cada número da tabela é o erro médio ao estimar as amostras de validação como se elas não existissem. Quanto menor, melhor o mapa representa os dados. Compare as linhas (P) e as colunas (máximo de vizinhas): poucas vizinhas deixam o mapa mais local; muitas, mais suave.",
        "en": "Each number in the table is the average error when estimating the validation samples as if they did not exist. The lower, the better the map represents the data. Compare rows (P) and columns (maximum of neighbours): few neighbours make the map more local; many, smoother.",
        "es": "Cada número de la tabla es el error medio al estimar las muestras de validación como si no existieran. Cuanto menor, mejor representa el mapa los datos. Compare filas (P) y columnas (máximo de vecinas): pocas vecinas dejan el mapa más local; muchas, más suave."},
    "cv_apply": {"pt": "Aplicar", "en": "Apply", "es": "Aplicar"},
    "cv_close": {"pt": "Fechar", "en": "Close", "es": "Cerrar"},
    "cv_more": {
        "pt": "<b>Validação cruzada</b><br><br>Algumas amostras são retiradas uma de cada vez e estimadas pelas demais, com cada combinação de P e máximo de vizinhas. O erro (RMSE, raiz do erro quadrático médio) mostra qual combinação reproduz melhor os valores reais.<br><br><b>Escolha das amostras de validação</b> (até 60, sorteio reprodutível):<ul><li>espalhadas por todo o talhão (o talhão é dividido em blocos);</li><li>longe da borda, onde o IDW tem menos vizinhos;</li><li>sem valores discrepantes (fora de ±3 desvios padrão), que distorceriam o erro;</li><li>equilibradas entre valores baixos, médios e altos, para que o ajuste valha para toda a variabilidade, e não só para os valores próximos da média.</li></ul><b>Zona de exclusão:</b> dados de sensores (como a CE) têm pontos a 1 ou 2 m na mesma passada, quase iguais entre si. Se esses vizinhos fossem usados, o erro pareceria pequeno demais e o método escolheria sempre P alto e poucas vizinhas (Roberts et al., 2017, <i>Ecography</i> 40: 913-929). Por isso, ao validar cada amostra, as vizinhas mais próximas que a distância típica entre um pixel e a amostra mais próxima são ignoradas.<br><br>Para referência, Mueller et al. (2004, <i>Soil Science</i> 169: 841-851) obtiveram o melhor resultado com IDW de potência 1,7 em mapas de condutividade elétrica do solo.",
        "en": "<b>Cross-validation</b><br><br>Some samples are removed one at a time and estimated from the others with each combination of P and maximum of neighbours. The error (RMSE, root mean square error) shows which combination best reproduces the real values.<br><br><b>Choice of validation samples</b> (up to 60, reproducible draw):<ul><li>spread over the whole field (the field is split into blocks);</li><li>away from the border, where IDW has fewer neighbours;</li><li>without outliers (beyond ±3 standard deviations), which would distort the error;</li><li>balanced among low, medium and high values, so the fit holds for all the variability, not only for values near the mean.</li></ul><b>Exclusion zone:</b> sensor data (such as EC) have points 1 or 2 m apart on the same pass, almost identical. If those neighbours were used, the error would look too small and the method would always choose high P and few neighbours (Roberts et al., 2017, <i>Ecography</i> 40: 913-929). So, when validating each sample, neighbours closer than the typical distance between a pixel and its nearest sample are ignored.<br><br>For reference, Mueller et al. (2004, <i>Soil Science</i> 169: 841-851) obtained the best results with IDW power 1.7 for soil electrical conductivity maps.",
        "es": "<b>Validación cruzada</b><br><br>Algunas muestras se retiran una a una y se estiman con las demás, con cada combinación de P y máximo de vecinas. El error (RMSE, raíz del error cuadrático medio) muestra qué combinación reproduce mejor los valores reales.<br><br><b>Elección de las muestras de validación</b> (hasta 60, sorteo reproducible):<ul><li>distribuidas por todo el lote (el lote se divide en bloques);</li><li>lejos del borde, donde el IDW tiene menos vecinas;</li><li>sin valores atípicos (fuera de ±3 desviaciones estándar), que distorsionarían el error;</li><li>equilibradas entre valores bajos, medios y altos, para que el ajuste valga para toda la variabilidad y no solo para los valores cercanos a la media.</li></ul><b>Zona de exclusión:</b> los datos de sensores (como la CE) tienen puntos a 1 o 2 m en la misma pasada, casi iguales. Si se usaran esas vecinas, el error parecería demasiado pequeño y el método elegiría siempre P alto y pocas vecinas (Roberts et al., 2017, <i>Ecography</i> 40: 913-929). Por eso, al validar cada muestra, se ignoran las vecinas más cercanas que la distancia típica entre un píxel y su muestra más próxima.<br><br>Como referencia, Mueller et al. (2004, <i>Soil Science</i> 169: 841-851) obtuvieron el mejor resultado con IDW de potencia 1,7 en mapas de conductividad eléctrica del suelo."},
    "p3_preview_n": {"pt": "{n} amostras", "en": "{n} samples", "es": "{n} muestras"},
    "p3_preview_note": {
        "pt": "Prévia em baixa resolução, só para comparar parâmetros. Vermelho = valores baixos, "
              "verde = valores altos. Pontos pretos = amostras.",
        "en": "Low-resolution preview, only to compare parameters. Red = low values, green = high "
              "values. Black dots = samples.",
        "es": "Vista previa de baja resolución, solo para comparar parámetros. Rojo = valores bajos, "
              "verde = valores altos. Puntos negros = muestras."},
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
              "<b>Pixel:</b> {pixel} m<br><b>Grade vetorial:</b> {grid}<br>"
              "<b>Estilo:</b> graduado, {classes} classes, quebras naturais (Jenks), {ramp}",
        "en": "<b>Boundary:</b> {boundary} ({crs}), {area} ha<br><b>Tolerance:</b> {tol} m<br>"
              "<b>Output folder:</b> {folder}<br><br><b>Attributes and IDW parameters ({n}):</b><ul>{items}</ul>"
              "<b>Pixel:</b> {pixel} m<br><b>Vector grid:</b> {grid}<br>"
              "<b>Style:</b> graduated, {classes} classes, natural breaks (Jenks), {ramp}",
        "es": "<b>Contorno:</b> {boundary} ({crs}), {area} ha<br><b>Tolerancia:</b> {tol} m<br>"
              "<b>Carpeta de salida:</b> {folder}<br><br><b>Atributos y parámetros del IDW ({n}):</b><ul>{items}</ul>"
              "<b>Píxel:</b> {pixel} m<br><b>Cuadrícula vectorial:</b> {grid}<br>"
              "<b>Estilo:</b> graduado, {classes} clases, cortes naturales (Jenks), {ramp}"},
    "help_page4": {
        "pt": "<b>Etapa 4: Resumo</b><br><br>Ao clicar em <b>Executar</b>:<br>"
              "1. cada atributo é interpolado por IDW e salvo como GeoTIFF;<br>"
              "2. é criada (ou reutilizada) a grade com as células inteiras que tocam o talhão;<br>"
              "3. calcula-se a média dos pixels de cada atributo em cada célula inteira (estatística zonal);<br>"
              "4. a grade é recortada pelo contorno, salva em Shapefile e carregada uma vez por atributo no grupo "
              "'Interpolados', com estilo graduado.<br><br>Use <b>Voltar</b> para corrigir.",
        "en": "<b>Step 4: Summary</b><br><br>When you click <b>Run</b>:<br>"
              "1. each field is interpolated by IDW and saved as GeoTIFF;<br>"
              "2. the grid with the whole cells touching the field is created (or reused);<br>"
              "3. the mean of each field's pixels is computed per whole cell (zonal statistics);<br>"
              "4. the grid is clipped by the boundary, saved as Shapefile and loaded once per field in the "
              "'Interpolated' group, with a graduated style.<br><br>Use <b>Back</b> to make changes.",
        "es": "<b>Paso 4: Resumen</b><br><br>Al hacer clic en <b>Ejecutar</b>:<br>"
              "1. cada atributo se interpola por IDW y se guarda como GeoTIFF;<br>"
              "2. se crea (o reutiliza) la cuadrícula con las celdas enteras que tocan el lote;<br>"
              "3. se calcula el promedio de los píxeles de cada atributo en cada celda entera (estadística zonal);<br>"
              "4. la cuadrícula se recorta por el contorno, se guarda en Shapefile y se carga una vez por atributo en el grupo "
              "'Interpolados', con estilo graduado.<br><br>Use <b>Atrás</b> para corregir."},

    # ---------------------------------------------------------------- pipeline
    "log_interpolating": {"pt": "Interpolando {label}...", "en": "Interpolating {label}...",
                          "es": "Interpolando {label}..."},
    "log_params": {
        "pt": "  {label}: P = {p}, vizinhas {kmin} a {kmax}, raio = {r}",
        "en": "  {label}: P = {p}, neighbours {kmin} to {kmax}, radius = {r}",
        "es": "  {label}: P = {p}, vecinas {kmin} a {kmax}, radio = {r}"},
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
    "warn_fallback": {
        "pt": "{label}: em {pct}% do talhão o raio de busca alcançou menos de {k} amostras; nesses pontos foram usadas as {k} mais próximas, mesmo fora do raio (mínimo de vizinhas).",
        "en": "{label}: in {pct}% of the field the search radius reached fewer than {k} samples; there the {k} nearest were used, even beyond the radius (minimum of neighbours).",
        "es": "{label}: en el {pct}% del lote el radio de búsqueda alcanzó menos de {k} muestras; allí se usaron las {k} más cercanas, aunque estuvieran fuera del radio (mínimo de vecinas)."},
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
    "alg_p_radius": {
        "pt": "Raio de busca (m, 0 = sem raio; só economiza cálculo)",
        "en": "Search radius (m, 0 = no radius; only saves computation)",
        "es": "Radio de búsqueda (m, 0 = sin radio; solo ahorra cálculo)"},
    "alg_p_pixel": {"pt": "Tamanho do pixel (m)", "en": "Pixel size (m)", "es": "Tamaño del píxel (m)"},
    "alg_p_folder": {"pt": "Pasta para os rasters interpolados", "en": "Folder for interpolated rasters",
                     "es": "Carpeta para los ráster interpolados"},
    "alg_p_output": {"pt": "Grade vetorial com médias", "en": "Vector grid with means",
                     "es": "Cuadrícula vectorial con promedios"},
    "alg_err_crs": {"pt": "A camada '{name}' está em {crs}. Reprojete para um sistema projetado em metros.",
                    "en": "Layer '{name}' is in {crs}. Reproject it to a projected CRS in metres.",
                    "es": "La capa '{name}' está en {crs}. Reproyéctela a un SRC proyectado en metros."},
    "alg_help": {
        "pt": "Interpola por IDW os atributos escolhidos de uma camada de pontos e calcula, por estatística zonal, a média de cada atributo em cada célula de uma grade vetorial (gerada com o tamanho de célula informado ou uma grade existente).\n\nA interpolação cobre o retângulo do contorno com 100 m de margem, sem recorte. A média é calculada nas células inteiras que tocam o talhão e só depois a grade é recortada pelo contorno. A grade gerada é salva na pasta dos rasters como [contorno]_Grade Padrão_[célula]x[célula].shp e reutilizada se já existir. As colunas recebem o nome do atributo (até 10 caracteres).\n\nA tolerância aceita pontos um pouco fora do contorno.\n\nVizinhas: cada pixel usa no mínimo [mínimo] e no máximo [máximo] amostras, as mais próximas (padrão 4 e 16; máximo 0 = sem limite). O raio de busca só economiza cálculo: se alcançar menos que o mínimo, as mais próximas são usadas mesmo fora dele; se alcançar mais que o máximo, só as mais próximas entram. Raio 0 = sem raio.\n\nOpção: escolher P e máximo de vizinhas de cada atributo por validação cruzada; o raio é calculado para não cortar o máximo.\n\nAs camadas devem estar em um sistema projetado em metros. A saída é carregada com estilo graduado (5 classes, Jenks, RdYlGn) do primeiro atributo. Para uma camada estilizada por atributo, use o assistente em Vetor > AgriPrecisa.",
        "en": "Interpolates the chosen fields of a point layer by IDW and computes, by zonal statistics, the mean of each field in each cell of a vector grid (created with the given cell size or an existing grid).\n\nInterpolation covers the boundary rectangle plus a 100 m margin, without clipping. The mean is computed in the whole cells touching the field and only then the grid is clipped by the boundary. The created grid is saved in the raster folder as [boundary]_Grade Padrão_[cell]x[cell].shp and reused if it already exists. Columns are named after the attributes (up to 10 characters).\n\nThe tolerance accepts points slightly outside the boundary.\n\nNeighbours: each pixel uses at least [minimum] and at most [maximum] samples, the nearest ones (default 4 and 16; maximum 0 = no limit). The search radius only saves computation: if it reaches fewer than the minimum, the nearest ones are used even beyond it; if it reaches more than the maximum, only the nearest ones are used. Radius 0 = no radius.\n\nOption: choose P and maximum of neighbours of each attribute by cross-validation; the radius is computed so it does not cut the maximum.\n\nLayers must be in a projected CRS in metres. The output is loaded with a graduated style (5 classes, Jenks, RdYlGn) on the first field. For one styled layer per field, use the wizard in Vector > AgriPrecisa.",
        "es": "Interpola por IDW los atributos elegidos de una capa de puntos y calcula, por estadística zonal, el promedio de cada atributo en cada celda de una cuadrícula vectorial (creada con el tamaño de celda indicado o una existente).\n\nLa interpolación cubre el rectángulo del contorno con 100 m de margen, sin recorte. La media se calcula en las celdas enteras que tocan el lote y solo después se recorta por el contorno. La cuadrícula creada se guarda en la carpeta de los ráster como [contorno]_Grade Padrão_[celda]x[celda].shp y se reutiliza si ya existe. Las columnas llevan el nombre del atributo (hasta 10 caracteres).\n\nLa tolerancia acepta puntos algo fuera del contorno.\n\nVecinas: cada píxel usa como mínimo [mínimo] y como máximo [máximo] muestras, las más cercanas (por defecto 4 y 16; máximo 0 = sin límite). El radio de búsqueda solo ahorra cálculo: si alcanza menos que el mínimo, se usan las más cercanas aunque estén fuera de él; si alcanza más que el máximo, solo entran las más cercanas. Radio 0 = sin radio.\n\nOpción: elegir P y máximo de vecinas de cada atributo por validación cruzada; el radio se calcula para no cortar el máximo.\n\nLas capas deben estar en un SRC proyectado en metros. La salida se carga con estilo graduado (5 clases, Jenks, RdYlGn) del primer atributo. Para una capa con estilo por atributo, use el asistente en Vectorial > AgriPrecisa."},
}
