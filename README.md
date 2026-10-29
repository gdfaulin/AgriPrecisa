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

### Workflow of *IDW vector grid*

1. **Boundary and output folder.** The bounding box of the field boundary defines the interpolation area. A tolerance (default 50 m) keeps samples slightly outside the boundary (e.g. machine turns). Selected features only can be used.
2. **Points and fields.** Only point layers with samples near the field are listed; expand each layer and tick the numeric fields to interpolate.
3. **IDW parameters.** Power *P* (default 2), search radius (default 100 m, 0 = no limit) and pixel size (default 5 m).
4. **Outputs.** One GeoTIFF per field, one GeoPackage polygon grid with `<field>_mean` columns, and one styled copy per field in the *Interpolated* group.

IDW estimate at each pixel centre:

$$\hat{z}_0 = \frac{\sum_i z_i\, d_i^{-P}}{\sum_i d_i^{-P}}, \quad d_i \le \text{radius}$$

All layers must be in a **projected CRS in metres** (e.g. SIRGAS 2000 / UTM 22S, EPSG:31982). The tool checks this and warns you.

### Installation

From QGIS: *Plugins > Manage and Install Plugins > All*, search for **AgriPrecisa**.
Manually: *Plugins > Manage and Install Plugins > Install from ZIP*.

### Interface language

Portuguese, English or Spanish, following the QGIS interface language (*Settings > Options > General*).

---

## Português

**IDW em grade vetorial** (*Vetor > AgriPrecisa* ou *Caixa de Ferramentas de Processamento > AgriPrecisa*): interpola por IDW os pontos amostrais, cria uma grade de polígonos do tamanho do pixel recortada pelo contorno do talhão e grava em cada célula a média de cada atributo (estatística zonal). Os mapas saem com estilo graduado de 5 classes, quebras naturais (Jenks) e rampa RdYlGn, uma camada por atributo no grupo *Interpolados*. As camadas precisam estar em sistema projetado em metros.

## Español

**IDW en cuadrícula vectorial** (*Vectorial > AgriPrecisa* o *Caja de herramientas de Procesos > AgriPrecisa*): interpola por IDW los puntos de muestreo, crea una cuadrícula de polígonos del tamaño del píxel recortada por el contorno del lote y guarda en cada celda el promedio de cada atributo (estadística zonal). Los mapas usan estilo graduado de 5 clases, cortes naturales (Jenks) y rampa RdYlGn. Las capas deben estar en un SRC proyectado en metros.

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
