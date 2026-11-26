# AgriPrecisa

**Precision agriculture tools for QGIS** · Ferramentas de agricultura de precisão para o QGIS · Herramientas de agricultura de precisión para QGIS

Developed by Gustavo Di Chiacchio Faulin at Fatec Pompeia "Shunji Nishimura" (Centro Paula Souza, Brazil).

![QGIS](https://img.shields.io/badge/QGIS-3.22%20to%204.x-589632) ![License](https://img.shields.io/badge/license-GPL--2.0--or--later-blue)

---

## English

### Tools

| Tool | Where | What it does |
|---|---|---|
| **IDW vector grid** | *Vector > AgriPrecisa* (wizard) and *Processing Toolbox > AgriPrecisa > Interpolation* | Interpolates sample points by IDW over the field, builds a pixel-sized polygon grid clipped by the field boundary and stores the mean of each interpolated attribute in every cell (zonal statistics). Results are styled as graduated maps (5 classes, Jenks, RdYlGn). |
| **DTM and plant height in row crops** | *Raster > AgriPrecisa* (wizard), toolbar and *Processing Toolbox > AgriPrecisa > Elevation models* | From a drone DSM of crops planted in rows, finds the soil visible in the inter-rows (morphological opening with a window wider than the inter-row, with slope correction), interpolates the terrain under the plants and delivers the DTM, the plant height (DSM minus DTM), a plant mask (1 = plant, 0 = soil) and plant polygons. |

### Workflow of *IDW vector grid*

1. **Boundary and output folder.** The bounding box of the field boundary defines the interpolation area. A tolerance (default 50 m) keeps samples slightly outside the boundary (e.g. machine turns). Selected features only can be used.
2. **Points and fields.** Only point layers with samples near the field are listed; expand each layer and tick the numeric fields to interpolate.
3. **IDW parameters, per attribute** (each attribute has its own spatial dependence, so each gets its own *P* and radius; a summary table shows all of them). Sliders for the power *P* (0.5 to 5) and the search radius (multiples of the coverage distance, which works for grids and sensor passes), with explanations, the IDW weight curve (1/d^P, Shepard 1968), bars with the share of each neighbouring sample in a typical pixel, a live map preview and **"Auto-fit" / "Auto-fit all"** buttons that run a spatial cross-validation per attribute and show the error (RMSE) for each combination. The Processing algorithm has the same option for batch runs. Pixel size default 5 m.
4. **Outputs.** One GeoTIFF per field (boundary rectangle + 100 m, never clipped), the reusable standard grid `<boundary>_Grade Padrão_<cell>x<cell>.shp`, and the final Shapefile grid with one column per attribute (zonal mean on whole cells, clipped by the boundary afterwards), loaded once per field in the *Interpolated* group.

IDW estimate at each pixel centre:

$$\hat{z}_0 = \frac{\sum_i z_i\, d_i^{-P}}{\sum_i d_i^{-P}}, \quad d_i \le \text{radius}$$

All layers must be in a **projected CRS in metres** (e.g. SIRGAS 2000 / UTM 22S, EPSG:31982). The tool checks this and warns you.

### *DTM and plant height in row crops*

Works when the soil is visible between the rows: perennials with open inter-rows (coffee, citrus, grapevine, eucalyptus) and annual crops before canopy closure (maize, soybean, young sugarcane).

| Crop | Row spacing | Resolution | Soil tolerance |
|---|---|---|---|
| Coffee | 3.6 m | 0.25 m | 0.25 m |
| Citrus | 6.5 m | 0.25 m | 0.30 m |
| Maize | 0.8 m | 0.10 m | 0.15 m |
| Soybean | 0.5 m | 0.10 m | 0.10 m |
| Sugarcane | 1.5 m | 0.15 m | 0.20 m |
| Grapevine | 2.5 m | 0.20 m | 0.20 m |
| Eucalyptus | 3.0 m | 0.25 m | 0.30 m |

The wizard has four steps: (1) DSM, optional RGB image, working resolution (starts at the DSM pixel) and row spacing, measured by clicking on several rows of a 30 x 30 m window or detected automatically; (2) DTM preview with a profile across the rows and sliders for the window factor, soil tolerance and slope (0 = automatic); (3) plant mask over the RGB image with sliders for the minimum plant height and transparency; (4) output layers, each with its own path and file name.

In the Processing algorithm, a crop list fills in the suggested values (table below); leave a field at 0 to use the crop value, or type your own value (for example, the spacing measured on the orthomosaic). *Custom* needs at least the spacing. The log reports the window size, the soil percentage and the plant height (mean, 95th percentile, maximum) and warns when the resolution is too coarse or the soil share looks wrong. If an output file is open in QGIS, the result is saved under a free name (e.g. `MDT_2.tif`).

### Installation

From QGIS: *Plugins > Manage and Install Plugins > All*, search for **AgriPrecisa**.
Manually: *Plugins > Manage and Install Plugins > Install from ZIP*.

### Interface language

Portuguese, English or Spanish, following the QGIS interface language (*Settings > Options > General*).

---

## Português

**IDW em grade vetorial** (*Vetor > AgriPrecisa* ou *Caixa de Ferramentas de Processamento > AgriPrecisa*): interpola por IDW os pontos amostrais, cria uma grade de polígonos do tamanho do pixel recortada pelo contorno do talhão e grava em cada célula a média de cada atributo (estatística zonal). Os mapas saem com estilo graduado de 5 classes, quebras naturais (Jenks) e rampa RdYlGn, uma camada por atributo no grupo *Interpolados*. As camadas precisam estar em sistema projetado em metros.

**MDT e altura de plantas em culturas em linhas** (*Raster > AgriPrecisa*, assistente em 4 etapas, barra de ferramentas ou *Caixa de Ferramentas > AgriPrecisa > Modelos de elevação*): a partir do MDS do drone (e, opcionalmente, da imagem RGB), o aluno mede o espaçamento entre linhas na imagem ou detecta automaticamente, ajusta o MDT vendo um perfil entre as linhas (fator da janela, tolerância de solo e declividade) e a máscara de planta sobre a imagem (altura mínima e transparência). Saídas: MDT, altura das plantas, máscara de planta (1 = planta, 0 = solo) e polígonos de planta.

## Español

**IDW en cuadrícula vectorial** (*Vectorial > AgriPrecisa* o *Caja de herramientas de Procesos > AgriPrecisa*): interpola por IDW los puntos de muestreo, crea una cuadrícula de polígonos del tamaño del píxel recortada por el contorno del lote y guarda en cada celda el promedio de cada atributo (estadística zonal). Los mapas usan estilo graduado de 5 clases, cortes naturales (Jenks) y rampa RdYlGn. Las capas deben estar en un SRC proyectado en metros.

**MDT y altura de plantas en cultivos en hileras** (*Ráster > AgriPrecisa*, asistente en 4 pasos, barra de herramientas o *Caja de herramientas > AgriPrecisa > Modelos de elevación*): a partir del MDS del dron (y, opcionalmente, de la imagen RGB), se mide el espaciamiento entre hileras en la imagen o se detecta automáticamente, se ajusta el MDT viendo un perfil entre las hileras (factor de la ventana, tolerancia de suelo y pendiente) y la máscara de planta sobre la imagen (altura mínima y transparencia). Salidas: MDT, altura de las plantas, máscara de planta (1 = planta, 0 = suelo) y polígonos de planta.

---

## Development

```
agriprecisa/              plugin folder (this is what goes into the ZIP)
  core/idw_math.py        IDW and grid maths, no QGIS imports (unit-tested)
  core/pipeline.py        IDW -> grid -> zonal statistics workflow
  gui/idw_wizard.py       step-by-step wizard
  processing_provider/    Processing provider and algorithm
  i18n.py                 Portuguese, English and Spanish texts
tests/                    pytest unit tests (no QGIS needed)
tests/integration/        end-to-end test that needs QGIS
scripts/build_zip.py      builds the ZIP for upload
```

Run tests: `python -m pytest tests` and, with QGIS installed, `python tests/integration/run_qgis_integration.py`.
Build the package: `python scripts/build_zip.py`.

Bug reports and suggestions: [issues](https://github.com/gdfaulin/AgriPrecisa/issues).

## License

GNU General Public License v2 or later. See [LICENSE](LICENSE).
