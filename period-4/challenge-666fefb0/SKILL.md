---
name: evidence-library-sort
description: Organize and repair an actual research file library. Use for batch classification, consistent tags and filenames, exact duplicate aliases, evidence-backed version relations, searchable catalogs, and hash-verified recovery.
---

# 从原文件建立可恢复的研究资料库

当任务要求整理已有文件时，执行下面的盘点、判读、复制、检索和恢复步骤。优先完成工单点名的操作。每个检索问题、待修复关系、指定导出格式都有单独的验收结果。以用户要求的语言交付。

## 1. 读工单，划清资料范围

先读取实际的 `/input/case.json`、`task.md`、资源说明及工单引用的清单，逐项记下 case_id、原始资料根、元数据来源、分类方案、命名规则、权限、检索问题、恢复目标，以及 output_contract 的键和类型。查看实际目录。把资料文件、别名、管理日志、查询清单和业务附件分清。输入清单与磁盘按路径或已有 ID 双向匹配，分别列出清单缺件、磁盘多件和链接目标不可读的情况。一份清单可以是九份文件的索引，不应给它虚构第十篇论文。用户指定的源 ID 即使经改名也须保留。题面只允许读的地方在新树中写入成果。

随包 `library.py` 为原创 Python 3.9+ 标准库脚本。定位至当前 SKILL.md 所在目录，Harbor 安装位置通常是 `/skills/weekly-skill`。所有路径参数都显式传入，运行不需登录。下例中的 SRC 应替换为实际资料根；工单散落于多个目录时取其最近的共同只读祖先，把控制文件在目录表中标明。不同批次使用不同工作目录。

```sh
S=/skills/weekly-skill/library.py
SRC=/input/material
W=/app/work/repair
B=/app/output/library
python "$S" scan "$SRC" "$W"
```

`inventory.json` 每条含源路径、可获取的字节数、完整 SHA-256、文件模式和提取状态。模式描述磁盘位，成功读出哈希证明本次进程可读；许可证、所有者、分享权限要从独立来源取证。目录错误单列。读取 `passages.json` 查看行号、PDF 页码与正文；大库按批读取。PDF 使用本机可用的 Poppler pdftotext，不上传文件。原文是 HTML、Office、图片、扫描件时按当地已装工具实际打开或转写。乱码优先查编码，加密或损坏记录具体错误。大量材料先完成全量盘点、初步目录和部分结果，再逐步补全。

## 2. 依据证据作决定

在 W 下写 plan.json。先采纳工单已有文件夹/受控词表；没有指定时选择一个稳定的主轴（如资料类型），再加一个能区分归属的次轴（如项目）。其余跨主题信息进标签。根据资料本身的对象、方法、用途分别给标签，按同义词表统一拼写，保存原词及来源。避免仅凭引用列表、装订盒文字、文件名、文件夹名和检索问题给正文定类。无法确认的主类放 Review，备注缺哪项证据能解决。摘要仅提及对照方法时，不把它提升为主类。

每个源文件保留机器可读 ID、来源与访问状况；实际文件名由脚本记录。决定中的 `metadata` 可含 title、authors（字符串数组）、year、venue、doi、type、version、source_id、project 等；无法确定的字段列入 `missing`，来源冲突同时记录两个原值、出处和所选依据。针对每个重要字段、归属和标签，写明支持它的证据字段。年份按合同指定的出版/提交语义取值，文件修改时间单列。作者以署名为准。规范化 DOI 的外壳和大小写用于比对前保留原文；引用区的 DOI 不赋给当前文件。用资料正文/扉页核对元数据表的链接，若没有匹配锚点，保留待审。脚本对引用作字面定位校验，语义判读由执行 Agent 承担。

plan 最小示例（以下均为接口示意）：若 `batch/card.txt` 的第一行是 `Type: index card`，第二行是 `Creator: Mira`，可写

```json
{
  "records": {
    "batch/card.txt": {
      "folder": ["Catalog", "Cards"],
      "stem": "Mira-index-card",
      "metadata": {"type": "index card", "authors": ["Mira"]},
      "tags": ["catalog card"],
      "missing": ["title", "year", "doi"],
      "uncertainty": "No publication statement.",
      "evidence": [
        {"source": "batch/card.txt", "locator": "L1", "quote": "index card", "fields": ["type", "folder", "tags"]},
        {"source": "batch/card.txt", "locator": "L2", "quote": "Mira", "fields": ["authors"]}
      ]
    }
  },
  "relations": []
}
```

扫描件或辅助资料有可目视验证的证据但无可用文本时，在 plan 顶级 `observations` 数组记录 `source, sha256, method, locator, text`，例如方法为“pdftoppm 渲染后检查，第 2 页扉页作者行”，定位须具体到页/区域或表/单元格，附实际看见的短转录。证据的 locator 引用 `observed:` 加该定位。脚本将观察绑定盘点哈希，目录会保存方法和引文；该绑定不验证 OCR 或转录正确。材料在 SRC 之外时也保存原定位和来源，不得把转录冒充原件。无法访问的字段留缺，并说明原因。

按 SHA-256 检查完全相同的字节；相同哈希保留每个原路径，代表件可在一条记录中设 `preferred: true`，每组最多一个。别名特有标签或原位置说明保存在该路径自身的 plan 记录中。不同哈希的同 DOI、同名、同作者年份或近似标题只产生人工核查候选。检查扉页、正文差异、稿号、出版声明、补充材料标识或明确管理记录，在 plan.relations 写 `{"from":"相对源路径","to":"相对源路径","type":"revises","scope":"具体关系范围","evidence":[...]}`；方向为 from 修订 to。补充材料、译本和会议扩展版各自独立且关系命名准确。管理记录的本地修订不推出出版社修订。反证或匹配不足写 possible_relation 和待查依据，禁止作为已证实版本。每个不同哈希独立保存。

## 3. 执行与验收

```sh
python "$S" build "$SRC" "$W" "$W/plan.json" "$B"
python "$S" search "$B" "$W/hits.json" "index card"
python "$S" restore "$B" "$W/recovered" "$W/recovery.json"
```

示意成果含 `files/Catalog/Cards/Mira-index-card.txt`、`catalog.json`、`index.json`、`run.json`。实际路径按工单，目录需要叠加到既有库时先复制其原快照并在新的资料库下执行；按用户指定原生格式另行产生 BibTeX、RIS 或可编辑目录表。缺少 stem 时用首位作者、年份和标题，缺失时退至 unknown-author、undated 和原始 stem，后者仅作定位符。名称作 NFC 规范化、非法字符替换和 UTF-8 分量截断，重名的不同内容追加完整哈希。原路径始终保留在 catalog。build 复制到新库，不移动源文件。一次成功后重跑同一套盘点和 plan，校验已存在的目标，重用一致的副本。文件变化须重新盘点并使用新输出目录。操作有失败时读取具体行的 error 或 issues；修复读取条件后按原条件续跑。中途终止可用同一命令恢复，不能把部分目录报告为完成。

在 catalog 核对每个源路径的实际目标、哈希、字节角色、选用的代表件、引用和动作。关系及提取异常有独立字段。比对读前/读后原件，逐一复算已写目标哈希，在新空恢复目录执行 restore 并检查每个源路径与字节。恢复重建原逻辑路径和内容；ACL、时间戳、硬链接或私有软件状态需额外授权与工具，无法还原须明确。发生目标污染时保留原字节，恢复回执报错且退出码非零。

对工单的每个检索/知识问题实际执行查询，记下问题 ID、规范化词、字段范围、命中数、定位片段和判读。search 在每一行正文上做不区分大小写的字面 AND 检索；零命中仅指该条件和索引范围。逐题尝试同义词、变体或结构化字段，用 Python 读 catalog 按标签/年份/类型/人名/关系过滤，用 index 独立核对内容；涉及多个条件时按 source 或字节组求交。搜索日志标明原始路径数与去重文献数。引用文中提到的对象与文献自身分类要分开。不得将未读取到的文件写为否定答案。

最后写 `/app/output/result.json`，严格逐字段按实际 output_contract 输出，含原 case_id、状态、不确定性、来源锚点、真实动作与产物相对路径。把工单要求的检索结果、恢复回执放到交付目录，再从零复开每个引用的文件；确认原输入盘点数等于已处理、跳过、失败的路径数之和。未完成项说明如何接手。不得把工作目录里的临时文件当成交付。只记录本次操作实际验证的事实。

## 运用边界

适用于本地可读的混合资料树和单进程批次。脚本读取完整文本以定位证据和建索引；超大文件或多 GB 资料库按项目分批，并用全局哈希清单核对跨批次重复。目录符号链接及非普通文件跳过。第三方账户元数据、远端访问权限、OCR 引擎、内容级近似查重需依靠实际可以使用的来源或工具。无需网络安装本作品。
