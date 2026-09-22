# 安装升级与旧版本自动清理设计

日期：2026-09-08

状态：整体方向已获用户认可并实施；长期行为包括 upgrade journal、使用锁、私有 Codex 注册 staging、条件发布与验证后清理。现场结果与限制见 [验证说明](../../validation.md#2026-09-23-安装升级当前现场结果)。

## 1. 目标与删除范围

每次升级先安装并验证新版，再自动清理本安装器能够证明归属的旧程序。完整安装必须通过 Blender 现场验证；仅更新 Codex 插件注册时，只要求注册验证通过。普通工作流自动执行清理，不再次请求已获得的删除授权。

允许删除：

- 历史托管安装的 runtime recovery 目录。
- 历史托管安装的 Blender 扩展 recovery 目录。
- `official-blender-mcp` marketplace 下 `blender-mcp-installer` 插件的历史版本缓存。

保留当前 runtime、扩展、插件缓存，用户偏好和 Codex 配置及其备份，历史受审 projection，安装 receipt、注册恢复证据和清理日志。其他 marketplace、插件、Blender profile、共享 uv 缓存和用户下载目录不在删除范围内。

验收结果必须区分“新版验证通过”“清理完成”和“仍有受保护旧目录待清理”。只要尚有候选未处理，就不能宣称旧版本已全部删除。

## 2. 设计时源码现状

下表保留 2026-09-08 实施前的基线与目标对照，不是当前缺口清单。

| 现状 | 目标行为 |
| --- | --- |
| runtime 与扩展使用固定目标路径；升级将旧镜像移入按 `install_id` 命名的 recovery。 | 继续复用现有原子替换和安装失败恢复；验证前不删除 recovery。 |
| 安装尾部验证配置后写入 `installed`、`live=not_run`，仅清理 bundle stage。 | 配置成功后保留回滚能力；现场验证成功后进入独立清理阶段。 |
| `install.py verify` 是只读检查。 | 保持只读；删除由显式 `finalize` 动作完成，常规工作流自动调用。 |
| 注册按 commit 保存 projection，调用 Codex 安装插件，再比较新缓存与 projection 的完整内容。 | 保留上述检查，增加已安装版本、启用状态及实际来源的精确核对。 |
| 注册恢复记录保存 before/after，但没有终态；恢复函数只恢复 marketplace source。 | 由升级 journal 记录注册阶段及恢复能力，不能将恢复 source 当作恢复了插件版本。 |

对应实现见 [安装路径模型](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/model.py)、[安装与回滚编排](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py)、[注册与缓存验证](../../../plugins/blender-mcp-installer/scripts/project_marketplace.py) 和 [当前工作流](../../../plugins/blender-mcp-installer/skills/install-official-blender-mcp/references/workflow.md)。

## 3. 组件与接口边界

现有 runtime、Blender、Codex adapter 继续负责安装和验证。新增一个安装生命周期模块，负责升级 journal、候选清单、受保护引用、清理执行和恢复；不引入后台服务、数据库或新的第三方依赖。

常规 `install` 与 `register` 工作流都必须在首次变更之前建立 journal，并将工作流 ID 传递到后续阶段。完整安装绑定注册恢复记录和安装 receipt；仅注册模式没有 runtime receipt。低层入口也必须接入同一生命周期，不能因绕过技能配方而遗漏 journal。独立的 inspect、verify 和 rollback 不创建清理任务。

增加 `finalize` 入口：完整安装入口能够调用现有 `verify_live`，仅注册入口不依赖 Blender。两者共用清理模块，并根据 journal 的模式拒绝不匹配的调用。实现计划确定命令参数，但不得将删除隐含加入 verify。

清理执行器来自本次受审的新副本或保留的新 projection，不能从待删旧缓存导入后续模块或启动子进程。注册与安装仍是可分别使用的能力，由同一工作流 ID 串联，避免把全部逻辑堆入现有大型 CLI。

## 4. 新版身份与候选归属

### 新版注册证据

从实际 Codex 已安装列表读取并逐项校验：

- `pluginId` 与 `name` 对应目标插件，`marketplaceName` 为 `official-blender-mcp`。
- `version` 与受审 plugin manifest 完全一致，`installed` 和 `enabled` 均为真。
- `source` 为本地来源，路径等于新 projection 下的 `plugins/blender-mcp-installer`。
- `marketplaceSource` 为本地来源，指向相同新 projection。
- 由精确 namespace 和 manifest 版本推导缓存路径；缓存内容摘要与新 projection 中的插件树一致。

这些检查证明新版已经持久化安装和启用，不能证明所有运行中的 Codex 任务都已重载新技能。未知字段可以保留为证据，但必需字段缺失、类型错误或不一致时不能通过验证。

### 历史候选

“旧版本”由已知安装、注册记录中的历史关系确定，不能以目录修改时间、字符串排序或“不是当前版本”判断。插件版本含构建元数据，比较优先级不能替代身份核对。

runtime 与扩展 recovery 必须具有有效 receipt、派生路径、托管来源和对应镜像证据。首次安装前已经存在但无法证明属于本安装器的程序，不能仅因被备份到 recovery 就自动删除。扩展产生的缓存只接受现有来源校验能够解释的内容。

插件缓存必须位于精确的 marketplace/plugin 目录下，manifest 名称与版本匹配路径，内容与保留的历史受审 projection 或此前记录的完整内容摘要吻合。只有目录名相似、存在未知文件、摘要漂移或历史来源缺失的条目保留并报告。

所有候选在清理前记录完整镜像。读取和删除使用受验证的目录边界、所有者检查、非符号链接检查及镜像条件删除；不能使用通配符递归删除。复用 [filesystem.py](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/filesystem.py) 的 `SafeRoot`、镜像捕获和可续删原语。

## 5. 流程与状态

完整安装顺序：发布前确认旧 runtime 可安全替换 → 建立 journal → 保存注册前态并注册新版 → 安装 runtime/扩展并绑定 receipt → 完成注册验证 → 启动选定 Blender → 只读现场验证 → finalize 重新核验 → 自动清理。

仅注册顺序：建立 journal → 保存注册前态并注册新版 → 完成注册验证 → finalize 重新核验 → 只清理历史插件缓存。不得要求 Blender 启动，也不得触碰 runtime 或扩展 recovery。

finalize 在锁内重新核对当前 active selector、安装/注册身份、目标镜像和模式所需的验证结果。完整安装调用现有验证函数，不在持锁时启动会再次获取同一把锁的 verify 子进程。此前命令输出中的“通过”不能独立授权当前删除。

| journal 状态 | 含义与允许动作 |
| --- | --- |
| `awaiting_verification` | 尚未越过删除边界；可继续安装/验证或使用现有恢复流程，不删除历史程序。 |
| `cleanup_pending` | 模式要求的验证已通过，清理意图已持久化；禁止依赖候选旧程序的本地回滚，允许重试清理。 |
| `complete` | 所有已证明归属的候选均已删除或本来不存在，且无受保护待清理项。重复 finalize 返回相同结论。 |
| `cancelled` | 在删除边界之前取消或恢复结束；不允许继续删除，保留证据。 |

候选状态为 `pending`、`deferred_in_use`、`conflict`、`removed`。未验证条目作为发现结果单独保留，不能伪装成已删除。存在 `deferred_in_use` 或 `conflict` 时，整体保持 `cleanup_pending` 并输出原因。

同版本、同内容重装保持安装 no-op，但仍检查已有清理 journal，处理可以安全恢复的未完成清理。不会为完全一致且没有待处理记录的安装重复创建清理代次。

## 6. Journal 格式、持久化与迁移

使用独立的 JSON schema v1，存放于安装器 state root 下的 `upgrades/<workflow-id>.json`，目录为 0700、文件为 0600。保留现有 receipt schema v1，不向旧 receipt 追加它不能解析的新字段。

journal 明确包含：schema 版本、UUID 工作流 ID、`install` 或 `register` 模式、阶段状态、经过校验的 home/Codex home/profile 身份、受审 commit、bundle/plugin 版本与摘要、当前 projection/cache、注册恢复记录引用、可选安装 receipt 引用、逐阶段结果、受影响回滚能力、候选相对路径和完整镜像、逐候选进度及失败原因。注册前态位置须在首次注册修改前绑定；安装 receipt ID 须在安装发布前绑定，禁止靠成功返回后补写关联。

候选路径采用“受支持的边界角色 + 相对路径”，从已验证的环境推导绝对根；解析时拒绝目录逃逸、未知角色和非规范 ID。未知 schema 不猜测、不清理，报告需由兼容版本处理。

首次删除前原子写入 `cleanup_pending` 和相关本地回滚失效标记，并同步文件与父目录。每次删除后同步所在目录，再记录进度。journal 写入失败时不得开始下一次删除。现有 marketplace `_atomic_write` 未同步父目录，不能直接作为清理边界的持久化实现；统一复用或扩展已有可靠写入原语。

旧 receipt 和旧注册证据保留原格式。迁移只为可重新证明身份与镜像的历史安装建立新 journal；缺少终态的旧注册记录先核对当前来源、before/after 和恢复引用，不能默认已完成。无法证明历史归属或是否仍需恢复的目录保留为明确的未处理结果。迁移不需要改写旧记录，不按文件年龄推断状态。

## 7. 活动引用、使用锁与并发

受保护集合包括当前 active 安装、新缓存与新 projection，其他未终结安装/注册事务的恢复引用，以及当前执行器的脚本、模块、解释器和工作目录所属树。本工作流自身的恢复引用，仅在验证完成且回滚失效标记持久化后，才解除对已登记候选的保护；其他事务仍引用同一候选时继续保留。历史 projection 始终保留，不因某条旧注册记录结束而连带删除。

未来所有受管脚本入口在使用版本目录之前持有共享使用锁；锁文件位于 state root 的稳定目录，不能放进待删树。清理需取得相应独占锁，失败则记录 `deferred_in_use`。当前 Codex 列表未提供运行任务的加载版本；旧入口没有使用锁时，不能用一次进程扫描或 `lsof` 空结果证明无人使用。不能证明空闲的候选延后，待宿主提供任务结束/重载证据，或受管入口已完成可验证的交接后重试。

变更锁的固定顺序为：Codex home 的 marketplace 锁 → 安装器 state 锁。清理持有这两把锁后，按规范路径排序尝试版本目录的独占使用锁；这些尝试必须非阻塞，失败即记为延后，不能持变更锁等待使用者退出。普通脚本在加载旧版本内容前持有共享使用锁，后续如需变更仍遵守 marketplace → state 顺序；清理不等待使用锁，避免与这样的运行入口形成循环等待。仅注册清理同样获取两把变更锁，以检查共享恢复引用。等待用户启动 Blender 时不持锁，恢复后重新验证状态。

这些锁只约束本安装器的协作入口。删除前后仍须核对实际配置与镜像，防止外部 Codex 操作改变目标；发现变化停止后续删除并记录冲突，不覆盖外部修改。

## 8. 故障与回滚语义

- 注册、安装或验证失败且尚未进入 `cleanup_pending`：不删旧；按现有安装恢复能力处理。注册 `_restore` 只恢复 marketplace source，结果不得声称旧插件版本已恢复。
- 删除期间失败或崩溃：保持新版 active；依据已记录镜像与合法删除前缀续删。文件已经删除但进度尚未写入时，验证缺失/合法剩余前缀后补记，不重建旧程序。
- 某候选被改动、替换或新增外来内容：停止处理该候选，保留内容和冲突证据；不把当前扫描结果重新采纳为可删除基线。
- 新版配置或身份在清理时改变：停止后续删除；不得因清理失败调用已依赖旧程序的回滚。
- `cleanup_pending` 或 `complete` 后请求受影响的本地回滚：在任何修改前明确失败，提示旧程序已进入自动清理阶段，不能从本地备份回滚；重新安装受审旧发行版属于新的安装流程。
- 用户偏好和 Codex 配置备份继续保留，但不因此宣称完整程序回滚仍可用。旧 `RESTORE.txt` 旁保留明确的能力失效记录，恢复入口必须先读该记录，不能继续照旧文本执行失效操作。

常规后续安装、注册和显式 finalize 会自动重试待清理记录；不新增定时任务。待处理记录关联的新版身份已不再 active 时，必须依据新的工作流重新确定受保护集合，不能直接沿用过期的验证结果。

## 9. 源码影响面

- [cli.py](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/cli.py)：安装生命周期关联、finalize 入口、回滚失效前置检查；verify 继续只读。
- [project_marketplace.py](../../../plugins/blender-mcp-installer/scripts/project_marketplace.py)：精确已安装身份核验、注册阶段 journal 关联、仅注册 finalize、锁序和恢复能力标记。
- [model.py](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/model.py) 与新增生命周期模块：新增独立 schema，沿用 receipt 和根边界定义，不重构无关协议或 adapter。
- [filesystem.py](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/filesystem.py)：复用安全捕获、持久化和可续删能力，只补缺失的直接需求。
- [runtime.py](../../../plugins/blender-mcp-installer/scripts/blender_mcp_installer/runtime.py)：启动前使用锁、托管树外的 bootstrap 解释器、active/installed receipt 屏障及跨 exec 的锁继承。
- [安装工作流](../../../plugins/blender-mcp-installer/skills/install-official-blender-mcp/references/workflow.md) 及安装技能：同步 install/register/finalize 的顺序、结果和失败语义，避免只改代码而留下旧回滚承诺。
- [分发测试](../../../tests/distribution/)：补充升级、引用、并发和崩溃用例；复用现有安装故障注入和注册假宿主。

维护时同时处理 V4 F20：将“固定受审发行版完整性重建”和“远端 main 最新性”作为独立检查并分别报告。固定旧版本与远端 main 不同不能推断完整性失败；受审新版本发布时原有最新性政策保持有效。此项属于分发验证语义调整，不增加清理范围。

## 10. 验收条件

| 类别 | 必须满足的条件 |
| --- | --- |
| 正向升级 | 使用内容和版本均不同的 A→B→C；每次完整安装现场验证通过后，旧托管 runtime/extension recovery 和可证明空闲的目标插件缓存消失，新版可继续使用。 |
| 仅注册 | 不调用 Blender/runtime 安装或验证；新插件身份、启用和来源验证通过后，只清目标历史插件缓存。 |
| 只读与幂等 | inspect/verify 不创建 journal、不改 receipt、不删除旧目录；重复 finalize 和同内容重装没有多余安装代次，能恢复已有待清理任务。 |
| 验证失败 | 注册字段、缓存内容、MCP catalog 或 Blender 现场探针任一失败，均不得进入首次删除。 |
| 边界保护 | 当前版本、其他插件、其他 marketplace、其他 profile、历史 projection、用户配置及其备份不变；外来文件、符号链接、错误所有者和路径逃逸被拒绝。 |
| 引用与使用者 | 待恢复引用、正在使用的版本锁和无法确认空闲的旧入口阻止对应删除，报告 pending；引用解除并重新核验后可自动继续。 |
| 并发 | 两个升级/清理进程没有反向锁依赖；同一候选不会并发删除；外部注册切换或镜像改变被识别，非目标配置保持不变。 |
| 崩溃 | 在清理意图写入前后、每个文件删除后、目录删除后和进度写入前后注入退出；验证无越界删除、无新版回滚、合法前缀可续删。 |
| 回滚 | 删除边界之前保留原有可验证恢复；边界之后，在任何目标修改之前明确拒绝受影响的本地回滚，不能仅报泛化 preflight conflict。 |
| 旧状态迁移 | receipt v1 可读；证据充分的历史目录可归入 journal；缺失、冲突或未知 schema 留存并说明，不能自动猜测归属。 |
| 分发验证 | 固定旧版完整性通过、远端 main 已更新时两项分别报告；新版本发布的最新性门禁没有被绕过。 |

开发先运行能覆盖改动的最小检查，提交前按仓库约定运行完整 checks；真实多版本升级验收在一次性受控 profile 中完成并保留证据。现场成功不得由假宿主测试替代，不能用“清理计划已生成”代替物理目录已删除。

## 11. 执行计划审计后的具体约束

2026-09-08 的计划原型进一步固定了以下实现细节，删除授权范围不变。完整任务及回归见[执行计划](../plans/2026-09-08-installer-upgrade-cleanup.md)。

- 使用锁按目录的 device/inode 建立，不能以 rename 后会变化的路径作为唯一键。launcher 必须先用托管 runtime 和目标插件缓存之外的 bootstrap Python 获取共享锁，再 exec 托管解释器；锁 FD 跨 exec 继承。bootstrap 边界使用实际 HOME/CODEX_HOME。
- rename 并不会让旧进程的 `__file__` 或 `sys.path` 自动指向 recovery。整个 runtime 替换之前必须取得旧目录的非阻塞排他锁；占用时，在首次注册/安装目标修改之前返回 `runtime_in_use`。
- 第一代无使用锁的旧 launcher，需要一次外部维护终端的停止交接：先记录受支持客户端的正向进程身份，停止后再核验。无法证明已停止则返回 `legacy_handoff_required`；这只覆盖合作的受管客户端，不宣称能够识别任意绕过入口的进程。
- launcher 在导入 runtime 业务模块之前核对 active、installed receipt 和当前目录 inode；PREPARED 或混合版本不可启动。
- 完整 finalize 持变更锁执行一次真实现场验证，随后逐候选复核绑定的注册、active、receipt、runtime/extension 镜像；任一漂移停止删除。等待用户启动 Blender 时释放锁，不对每个文件重复完整现场探针。
- 对精确目标插件 namespace 中完全缺少历史注册证据的旧目录，保留并列为未验证。不存在可删除候选不等于所有旧版本已清理；同内容重试可以建立清理迁移记录，但不制造新的安装代次。

## 12. 2026-09-23 真实 Codex 注册边界补充

现场确认 Codex `plugin add` 会提前删除同插件旧版本缓存且不遵守安装器使用锁。注册器现在仅在同一目标用户的 0700 私有事务 CODEX_HOME 中运行此命令，使用目标 config.toml 的 0600 配置快照，不复制登录文件、会话或继承凭据。当前一次性验收不复制或修改普通用户配置。配置快照可能敏感，不得写入日志；成功发布后移除临时配置，失败只保留受保护的恢复证据。

发布顺序为已验证的新版本 cache → 条件发布 config；不得重命名、替换或删除旧版本路径/inode。除精确目标 marketplace 项与目标插件 enabled 字段外，所有 TOML 值必须保持不变。外部配置漂移停止发布；cache 已发布而配置未发布时可 exact-match 复用，记录的配置交换通过原条件原语续作。只有原有 finalizer 完成规定验证并取得对应使用锁后才可删除旧缓存；占用状态继续返回 cleanup_pending。

敏感配置写入前必须持久绑定 native stage 的精确目录名和根身份。每次重试先清理前次已记录尝试，再创建下一次；删除镜像在删除前持久化，部分删除按既有条件删除原语续作。publication 绑定同一 stage 记录，成功不能绕过清理；记录缺失、目录替换或删除镜像漂移失败关闭并保留私有证据，不按通配符删除未知目录。
