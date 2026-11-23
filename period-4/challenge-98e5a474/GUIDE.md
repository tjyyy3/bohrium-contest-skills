# 调用指南

版本 0.1.0。脚本为本技能原创。生成与文字修订需要 Python 3.9+ 标准库。导出脚本额外需要 Playwright Python、Chromium 和 PyMuPDF。先用案例环境现成的工具。独立环境可在授权的项目虚拟环境中安装 `python -m pip install playwright pymupdf`，再执行 `python -m playwright install chromium`，或用 `--chromium` 指向已有 Chrome/Chromium/Edge 可执行文件。日常执行无网络依赖。可修改字体族以匹配本机已安装且覆盖全部字形的字体。

## 最小示例

在本技能目录旁的工作目录保存下面的演示输入为 `graph.json`。来源定位在演示语句“信号从 A 传给 B”。

```json
{
  "canvas_mm": [90, 60],
  "title": "Signal path",
  "nodes": [
    {"id": "a", "label": "A", "box": [36, 97, 100, 54], "source": "demo-sentence:1"},
    {"id": "b", "label": "B", "box": [223, 97, 100, 54], "source": "demo-sentence:1"}
  ],
  "edges": [{"id": "a-b", "from": "a", "to": "b", "kind": "flow", "source": "demo-sentence:1"}],
  "styles": {"flow": {"label": "Signal", "color": "#276371", "dashed": false}}
}
```

从保存输入的工作目录运行。把下面的技能路径换成实际安装位置。

```sh
python /skills/weekly-skill/schematic.py create graph.json figure.svg
python /skills/weekly-skill/export_svg.py figure.svg exports --dpi 300
```

示意输出为 `label-a` 和 `label-b` 两个可选文字，`edge-a-b` 从 A 的右侧指向 B 的左侧，图例显示 “Signal”。`exports/figure.pdf` 与 `exports/figure.png` 由同一份图生成。脚本用 JSON 写出文件、PDF 实测尺寸、PNG 像素和字体名。

## 输入字段与局部修订

- `canvas_mm` 为物理宽高。`box` 为 `[x,y,width,height]`，坐标原点在左上，4 个 SVG 用户单位对应 1 mm。每个节点有唯一的小写字母开头 ID、`label`、矩形范围和 `source`。可选 `detail` 为节点第二行，`subtitle` 为标题注记，`font_family` 为 CSS 字体族。给标题和下部图例留出空间。
- `edges` 中 `from`、`to` 指向节点 ID，`kind` 指向样式。可选 `via` 是从起点到终点的中间坐标列表。路径贴到两个节点边界，箭头画在终点。加入 `label` 时给出文字基线位置 `label_at: [x,y]`。样式使用 `#RRGGBB` 和可选的 `dashed`，图例从实际使用的样式生成。长标签、多图例项及跨节点的路径需复核图面，按需调整坐标。
- `source` 填实际可定位的文件与段落、页码、对象 ID 等。图例条目按 `data-kind` 对应到关系。来源有效性和科学语义由调用者对实际材料复核。

修订命令接受一个 JSON 数组。每项给出原 SVG `<text>` 的 ID、解析出的旧文本、新文本和新值的证据定位。比如用户要求将示例中的 “B” 展开，且材料有该全称时，`changes.json` 可以写为 `[{"id":"label-b","expect":"B","replace":"Receiver B","source":"approved-revision:1"}]`。命令为 `python /skills/weekly-skill/schematic.py edit figure.svg changes.json revised.svg`，再以 `revised.svg` 调用导出。编辑目标须有唯一原生 `id`，正文为单行文本。输入与输出使用不同路径。旧值不符、ID 缺失或文本含子节点时失败，终端回执记录前后 SVG 哈希及实际改动。

## 导出边界

导出脚本处理自包含单页 SVG。缺物理尺寸时用 `--size-mm WIDTH HEIGHT`，保持原始纵横比。Chromium 打印时在右侧和底部多留 1 mm，再设定 PDF 纸张边界以抵消尺寸量化。回执列出 PDF 实测尺寸。PNG 从同一 PDF 渲染，且包含分辨率元数据。默认目标为 RGB，交付前可用 PDF 检查工具确认字体和图元，用图像工具验证像素尺寸与颜色。针对 CMYK、EPS、TIFF 或复杂格式，按案例选择支持对应规格的渲染器和检查工具。

若环境已有 Inkscape，也可用 `inkscape figure.svg --export-filename=figure.pdf` 及 `inkscape figure.svg --export-dpi=300 --export-filename=figure.png`。对该途径输出重复检查。渲染器无法启动时保留 SVG 并在结果中记录失败和错误。正文含嵌套文字、外链资产、滤镜或特殊字体时，检查采用的渲染器对相应图形的实际支持。
