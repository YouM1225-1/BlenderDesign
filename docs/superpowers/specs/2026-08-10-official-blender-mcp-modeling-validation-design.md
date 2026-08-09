# Official Blender MCP Modeling Validation Design

状态：approved for autonomous execution

日期：2026-08-10（Asia/Shanghai）

## 1. 目标

在 Blender 5.2.0、macOS Apple Silicon 和 Blender Lab 官方 MCP 的已安装环境中，
完成一次真实、隔离、可恢复的风格化台灯建模实测。实测必须尽可能覆盖当前 catalog
中的全部 26 个工具，记录各阶段和各工具的耗时、LLM 错误、工具错误与恢复动作；随后统一
分析根因，决定是否需要增加可复用文件防止 LLM 重犯，并通过独立修复计划、
Subagent-Driven Development、对抗性审计和重复实测闭环所有问题。

用户已明确要求自主连续执行并最终提交到 `main`。因此本设计不设置人工中途确认点；只有
无法从现有仓库、运行环境或安全边界推导的真正 blocker 才能停止。

## 2. 方案选择

采用“隔离基准场景 + 全工具矩阵”，并用临时失败探针补足可恢复性证据：

- 不采用只做视觉模型的方案，因为它无法覆盖 CLI、文档、missing-file、linked-library
  和 UI 导航通道；
- 不采用纯自动遍历方案，因为它不能证明 LLM 在真实建模过程中的分解、观察和纠错能力；
- 推荐方案把二者结合：先完成可目视验收的台灯，再对同一隔离 run 的 GUI 场景、CLI
  fixture、外部 library、受控 missing image 和渲染产物逐项调用 26 个工具。

## 3. 隔离边界与产物

### 3.1 当前 GUI 资格

只有同时满足以下条件的 Blender GUI 才可用于写入型 MCP 调用：

- 精确版本 `>=5.2`，本轮实测基线为 `5.2.0`；
- 当前文件未保存、`is_dirty=false`，场景只含 factory-startup 的 `Cube`、`Camera`、
  `Light`；
- 恰好一个 Blender GUI 进程监听 `127.0.0.1:9876`；
- 文件路径不是用户 `.blend`，且写入前后都由 `get_blendfile_summary_path_info` 复核。

不满足时，退出可疑 GUI 而不保存，重新启动专用 factory-startup 会话。不得打开、保存、
覆盖或清理任何用户 `.blend`。

### 3.2 Run root

每次实测创建一个 mode `0700` 的忽略目录：

```text
.superpowers/sdd/modeling-runs/<run-id>/
  library_source.blend
  lamp_fixture.blend
  assets/known-missing.png       # 路径存在于 datablock，但文件刻意不存在
  renders/thumbnail.png          # 从官方 Blender scratch 校验后复制的证据副本
  renders/viewport.png           # 从官方 Blender scratch 校验后复制的证据副本
  results.ndjson
  run-report.md
```

fixture 与证据副本路径必须词法位于 run root、父链无 symlink、目标不是用户文件。官方两个
render 工具只接受请求路径的 basename，并把真实输出解析到
`bpy.app.tempdir/blender_mcp`；实测必须校验返回路径位于该 Blender-owned scratch、basename
精确匹配、文件非空，再由外部只读验收步骤复制到 run root。不得把这一有意的 scratch
重定位误报为路径逃逸。二进制 `.blend` 和 PNG 不提交；最终只提交设计、计划、审计报告，
以及根因证明确实需要的最小代码/文档。

## 4. 台灯场景合同

GUI 场景创建 collection `MCP_Lamp_Isolated`，并至少包含：

- `Lamp_Base`：带 bevel 的圆柱底座；
- `Lamp_Stem`、`Lamp_Arm_Lower`、`Lamp_Arm_Upper`：父子连接的立柱和双段灯臂；
- `Lamp_Joint_Lower`、`Lamp_Joint_Upper`：关节几何；
- `Lamp_Shade`：截锥形灯罩，mesh data 名与 object 名可区分；
- `Lamp_Bulb`：带 emissive material 的 UV sphere；
- `Lamp_Cable`：bevelled Curve；
- `Lamp_Ground`：接收阴影的平面；
- `Lamp_Key`、`Lamp_Fill`：area lights；
- `Lamp_Camera`：可完整构图的 active camera；
- `Lamp_LinkedProp`：从 run root 的 `library_source.blend` link 的只读对象。

材质至少为 `Mat_Base`、`Mat_Metal`、`Mat_Shade`、`Mat_Bulb`、`Mat_Ground`。另外创建
一个未参与渲染的 image datablock，绝对路径指向受控的
`assets/known-missing.png`，用于 missing-file 工具验证。

建模分三次受控 `execute_blender_code` 调用完成，每次只修改上述隔离 collection：

1. 清除三个已确认的 factory-startup 对象，创建地面、底座、立柱和材质；
2. 创建关节、双段灯臂、灯罩、灯泡、线缆和父子层级；
3. 创建相机、灯光、linked object、missing image reference，设置低成本渲染并返回
   objects/materials/collections/world-bounds 的结构化验收数据。

每次调用前后检查 Object mode、active/selection、路径哨兵和目标 collection。不得调用
`read_factory_settings`、`save_*`、网络、删除非 factory-startup/非隔离对象或写 run root
之外的文件。

## 5. 26 工具覆盖

当前 catalog 必须先由真实 MCP handshake 证明恰好 26 个唯一名称。覆盖分组如下：

- 任意代码：`execute_blender_code`、`execute_blender_code_for_cli`；
- GUI/CLI summaries：datablocks、missing files、linked libraries、path info、usage guess
  的 10 个工具；
- 场景查询：`get_object_detail_summary`、`get_objects_summary`；
- 文档：`get_python_api_docs`、`search_api_docs`、`search_manual_docs`；
- 视觉：area screenshot、window screenshot、window JSON；
- 导航：tab by name、tab by space type、object by name、object data by name；
- 输出：`render_thumbnail_to_path`、`render_viewport_to_path`。

每个唯一工具至少有一个可判定结果。正常成功、受控预期失败、前置失败和意外失败必须分开
记录；“被调用”不能自动计为“稳定”。GUI/CLI 成对工具必须各自调用，不能以
`execute_blender_code_for_cli` 冒充没有 CLI 版本的 GUI 工具覆盖。

## 6. 计时与错误记录

每次工具调用记录：run id、phase、tool、case、mode、ISO-8601 开始/结束时间、monotonic
wall time、工具回传的 internal time（没有则为 `null`）、脱敏输入、预期结果、outcome、
result shape、artifact SHA-256、错误文本摘要和 recovery。

每个建模阶段另记录从 LLM 开始准备到验证结束的 wall-clock，包含思考、工具往返和纠错；
Blender 内部脚本另用 `time.perf_counter()` 返回操作耗时。两者不得混称。一次调用满足以下
任一条件就标记为“可能非正常耗时”：

- docs/summary/navigation `>5s`；
- screenshot `>10s`；
- thumbnail `>30s`；
- viewport render `>60s`；
- 同阶段耗时超过其成功重跑中位数的 `3x`；
- 工具在完成 Blender 端工作后仍长时间不返回。

所有 LLM 错误都记录原始症状、首次错误假设、实际根因、浪费时间、是否由文档/脚本/测试
可预防。只允许针对同一可恢复工具失败重试一次；第二次失败进入根因分析，不盲重试。

## 7. 执行阶段与验收

1. **Preflight**：catalog 26/26、GUI 路径/进程/listener、run root 安全；
2. **Fixture provision**：背景 Blender 创建 library 和 CLI fixture；
3. **Modeling**：三阶段创建台灯并逐阶段结构化验收；
4. **Structure/externality**：GUI/CLI summaries、object detail、linked/missing/path/usage；
5. **Docs**：API exact lookup、API search、manual search；
6. **UI/visual**：workspace、area、object/data 聚焦、JSON 和 PNG screenshots；
7. **Render**：低分辨率 thumbnail 和 viewport render，返回路径位于官方 Blender scratch，
   复制后的 run-root 证据非空，路径前后哨兵不变；
8. **Adversarial cases**：不存在对象、ignored/linked/missing edge、坏输出路径或受控 timeout
   中不破坏数据的子集；
9. **Closeout**：26/26 分类、耗时表、artifact hashes、根因分析，关闭 GUI 不保存或保留
   隔离 unsaved 会话供立即复测。

建模成功要求：所有合同对象/材质存在，父子层级、camera、lights、linked library、missing
reference 正确，两个 PNG 非空且视觉上是完整台灯构图，GUI 未保存到用户路径。

## 8. 根因、修复和防重复判定

完成 baseline 后统一分类：

- **LLM 计划错误**：顺序、名称、上下文或参数可以由稳定 checklist 防止；
- **手册缺口**：官方安装手册缺少运行后建模/渲染安全边界；
- **可重复自动化缺口**：相同 payload/验收需要多次人工重建，或错误只能靠记忆避免；
- **上游工具缺陷**：同一最小复现跨干净 session 重复出现；
- **环境抖动**：无法在同条件重复，且工具/Blender 端没有状态残留；
- **正常成本**：渲染、后台 Blender 启动或首次 docs index 的预期初始化。

只有当证据显示能消除重复错误时才新增文件。优先级是：修改独立操作手册或 audit checklist；
其次是小型、默认 dry-run/隔离的 smoke helper；最后才修改产品代码。不得修改冻结
`docs/install.md`、ROADMAP、历史 audit/evidence/attestation 或已批准 Plan。

修复必须另写 `writing-plans` 计划，按 Subagent-Driven Development 逐任务实现、提交和两阶段
复审。Critical/Important 全部修复并复审；Minor 记录在 durable ledger 并由最终审查裁定。

## 9. 最终审计、复测与 main

最终由高能力独立审查者对整个分支做对抗性审计，至少检查：路径逃逸、symlink、当前 GUI
误识别、任意 Python 范围、partial render、tool count 漂移、耗时误判、报告夸大、冻结文件
漂移和 rollback。所有发现一次性交给同一修复代理，修复后重新生成 review package。

最终门包括：

- 26 个唯一官方工具全部获得可判定 outcome，所有预期成功项通过；
- 台灯结构与两张 PNG 通过机器和视觉检查；
- adversarial cases 不写用户路径、不破坏 GUI/fixture；
- Ruff、Mypy、vendor、nested import、完整 `369` 测试通过；
- standalone manual 与计划嵌入副本保持精确一致；
- Git scope、diff、状态和冻结文件检查通过；
- 最新 whole-branch review 为 Ready，且无 Critical/Important。

全部门通过后，把功能分支以非交互方式合并到 `main`，在 main 上重跑最终覆盖门和 Git clean
检查；保留可追溯提交，不 squash、不改写历史。

## 10. 非目标

- 不把这次实测扩展为跨平台、Blender `<5.2`、性能基准产品或所有 26 工具的永久支持承诺；
- 不测试任意用户生产文件；
- 不把启发式 usage guess 的具体分数作为产品正确性；
- 不因一次不可复现的慢调用修改上游工具；
- 不提交 `.blend`、PNG、完整 Codex config、用户路径或隐私场景内容。
