# 定性图稿规格 0.1.0

## 调用

需要 Python 3.9+。生成 SVG 只依赖标准库。SVG 内含原生可编辑文本、路径、矩形和命名图层。导出子命令使用环境已有的 PyMuPDF（本地验证版本 1.27.2）。也可使用已有的 Inkscape 或 Chromium 渲染。渲染器和字体以运行环境实际发现的为准。

```bash
python scripts/pathway.py draw graph.json figure.svg
python scripts/pathway.py export figure.svg --dpi 192
```

`export` 在 SVG 同目录写同名的 PDF 和 RGB PNG，返回实测大小、页数、字体、分辨率和渲染器版本。PDF 为矢量输出，PNG 由同一页栅格化。交付前仍需视觉检查。PyMuPDF 可能漏绘外部 SVG 的 `stroke-dasharray`。本工具的 SVG 使用显式路径保留虚线。若已有原稿使用这类属性，或环境缺 PyMuPDF，选已有的渲染工具，例如 `inkscape figure.svg --export-filename=figure.pdf`，再使用 `pdftoppm -r 192 -png -singlefile figure.pdf figure` 生成检查图。只有用户授权安装时才添加软件依赖。

如果使用环境中的 Chromium，可将 SVG 嵌入本地 HTML。将打印页面的宽高设为 SVG 的物理宽高，页边距为 0，等字体就绪后带背景导出 PDF，再按要求分辨率渲染 PDF。此方式仍需检查分页、字体、边和颜色。

修订本工具生成的节点标题时可运行 `python scripts/pathway.py relabel figure.svg revised.svg a "New label"`。多行标签按行分别传参。该命令保留区室、其余图元、节点标题字体和末行基线。同步 JSON 中的标签并复核换行及边界后重新导出。

## 字段

| 字段 | 用法 |
|---|---|
| `title`、`subtitle`、`canvas` | 图题、可选副标题、`[宽, 高]`。坐标以 SVG 用户单位表示，PDF 的目标物理尺寸按 96 单位每英寸换算成 pt。上下留出约 100 和 160 单位给标题、图例和说明。 |
| `sources` | 以稳定 ID 为键的材料表。每项写 `title` 和 `version`，建议另存文件路径及 SHA-256，或 DOI/URL。 |
| `evidence` | 以稳定 ID 为键的定位表。每项有 `source`（材料 ID）、`locator`（页、分面、表或记录标识）、`claim`（原文支持的声明）、`context`（物种/条件或教学假设）。 |
| `regions` | 从背景到前景排列。项内有 `id, label, box, kind`，可选 `label_at, fill, refs`。矩形 `box=[x,y,宽,高]`，坐标从左上向下。区室用 `area`，横截膜带用 `membrane`，抽象读数等外置分组用 `panel`。 |
| `nodes` | 每项有 `id, label, box, region, placement, refs`，可选 `detail`、`type`。默认按区室内节点的 `inside` 处理，跨水平膜带用 `spans`。在胞质面上的外周实体可用胞质子区室。每个 `refs` 指向已有的证据 ID。 |
| `edges` | 每项有 `id, from, to, kind, points, action, label_at, refs`。折线的第一点压在源节点边界，最后一点压在目标节点边界，中间可经若干转折。动作文字左对齐，`label_at` 是第一行基线。标签可用换行分行。可选 `certainty` 为 `supported` 或 `inferred`，后者需要 `rationale`。 |
| `notes`、`uncertainties`、`data_mapping` | `notes` 是最多三行图下说明。把需复查的推断、缺失材料或未画机制记入 `uncertainties`。定量信息在 `data_mapping` 中记录原始值、单位、条件、定位和图形映射。脚本只呈现定性符号，定量映射由调用者核对并用所需的矢量工具实现。 |

边的图例由实际关系生成。

| `kind` | 图面语义 |
|---|---|
| `activate` | 实心箭头表示促进、增加或使能。 |
| `inhibit` | 端部 T 形表示减少或抑制。用动作文字区分降解、消耗、抑制活性等不同原因。 |
| `associate` | 无方向虚线表示关联或读数对应。 |
| `bind` | 无方向实线表示结合。 |
| `modify` | 空心箭头表示状态转化或修饰。标明具体动作。 |
| `transport` | 双箭翼表示转运方向。标明转运物。 |

推断的方向边保留端点形状，并加虚线。证据不足的无方向边可记录到不确定性。证据 ID 随每个 SVG 图元的 `<title>` 和 `data-evidence` 写入，完整定位在配套 JSON。SVG 的层级为背景/区室/连线/节点/图注，节点以 `node-ID` 命名，内有 `label-node-ID` 文字组，边以 `edge-ID` 命名。直接修改 SVG 时同步模型或记录差异，以实际交付的 SVG 为准。更换字体或长标签后检查图面。本工具接受手工路由的简单反馈或分支，拥挤时可分图或使用已有布局工具。

## 最小调用示例

以下为虚构的教学符号 A、B，用来演示输入接口。

```json
{
  "title": "Illustrative relation",
  "canvas": [800, 450],
  "sources": {"demo": {"title": "Synthetic notation example", "version": "1"}},
  "evidence": {"e1": {"source": "demo", "locator": "Example statement 1", "claim": "In this invented example, A enables B.", "context": "Synthetic"}},
  "regions": [{"id": "cell", "label": "Example area", "box": [42, 116, 716, 160], "kind": "area", "refs": ["e1"]}],
  "nodes": [
    {"id": "a", "label": "A", "box": [126, 179, 136, 56], "region": "cell", "refs": ["e1"]},
    {"id": "b", "label": "B", "box": [538, 179, 136, 56], "region": "cell", "refs": ["e1"]}
  ],
  "edges": [{"id": "a-enables-b", "from": "a", "to": "b", "kind": "activate", "points": [[262, 207], [538, 207]], "action": "enables", "label_at": [365, 191], "refs": ["e1"]}],
  "notes": ["Synthetic notation example"]
}
```

将示例存为 `graph.json`，按上面的两条命令运行。示意输出为区室中的 `A → B`、同样式的促进图例、可编辑的 `node-a` 和 `edge-a-enables-b`，以及对应的 PDF 和 PNG。
