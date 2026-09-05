# Agent 工作流

本仓库的协作入口是 [AGENTS.md](../AGENTS.md)，Claude 入口只引用同一约定。
技能按任务加载：跨模块检索使用 graft，官方分发的安装状态与生命周期操作使用安装技能。
没有 GitHub Actions workflow；本地验证由 `scripts/checks.sh` 和 `scripts/checks-fast.sh` 承担。

## GPT-6 Astra 对齐依据

2026-09-05 核对了 [OpenAI GPT-6 Astra 官方模型指导](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-6-astra)。
该文档建议主动完成已授权工作、明确技能与用户指令的关系，并按任务调整沟通、委派和验证。
以下是针对本仓库的应用，不是模型性能基准：

| 审计发现 | 当前处理 |
|---|---|
| AGENTS 只有图缓存规则，缺少任务范围与仓库入口 | 增加必要的执行、组件和验证信息；保留 Graft 必需门禁 |
| CLAUDE 与 graft 强制所有任务先查图，禁止必要的源码复核 | 按问题选检索工具；弱命中直接读源码或用 `rg` |
| graft 声称始终新鲜、固定延迟，并强制汇报估算节省 | 删除无条件性能承诺和无关汇报要求；交付仍检查图新鲜度 |
| graft 的“不需要 build”与 AGENTS 冲突 | 统一为最后修改后 build、交付前 check |
| 安装技能入口混入全部命令和发行验收细节 | 将原 505 行入口改为操作路由；11 个 Bash 命令块原样移入按需参考文件 |
| 检查操作前先注册 marketplace，扩大只读任务范围 | 按操作选择命令；仅授权安装或注册更新才准备 marketplace |
| 仅注册更新仍被操作文档引向 runtime 安装 | 注册使用独立命令顺序，不执行 installer；隔离测试实际执行文档中的注册步骤，检查未创建 runtime 或 receipt |
| 安装等待 Blender 时未明确注册收尾顺序 | 等待前完成 trust cleanup 和注册验证；后续 verify 重建 trust，不重复注册或安装 |
| 已有授权、启动或关闭证据仍触发重复确认 | 复用授权和当前宿主证据；仅缺少必要状态或确需用户操作时暂停 |
| 普通验证、发行验证和正式现场证据混用 | 开发时最小检查、提交前完整检查；runtime 发行和现场验收分别触发 |

保留固定版本、提交真实性、四项显式授权标志、Blender 生命周期保护和 receipt 回滚。
历史验收方案只在对应任务需要时读取，不把旧条款升级为当前通用流程。

## 维护与验证

修改入口时检查这些实际场景：已知文件的小改动能直接开始；仅检查安装状态不会注册插件；
仅注册插件不会安装 Blender 扩展或 runtime；
安装请求复用四项已有授权；已运行的 Blender 可直接 verify；仍在运行时回滚会要求用户保存并退出；
缺少第二台 Mac 不阻止普通安装；中途补充要求不会丢失原任务。

安装命令位于 [workflow.md](../plugins/blender-mcp-installer/skills/install-official-blender-mcp/references/workflow.md)，
`tests/distribution/test_plugin_contract.py` 按文档的 operation recipes 执行首次 inspect 和注册操作，
并直接提取其中的信任、runner 和注册代码，
覆盖不可信 Git 配置、脏索引、路径重定向、注册回滚和清理后持久性。不要为措辞本身新增测试。
技能入口需通过 skill-creator 的 `quick_validate.py`；完整验证和分发要求见 [验证说明](validation.md)。

仓库没有模型 API 请求或推理参数配置。本轮优化作用于指令与工作流，不把更高 reasoning effort、
异步工具或多代理设为通用强制项，也不声称未经端到端测量的速度或质量提升。
