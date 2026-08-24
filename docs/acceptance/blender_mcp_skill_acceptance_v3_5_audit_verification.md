# V3.5 审计报告验证结论

> 验证对象:`blender_mcp_skill_acceptance_optimized_v3_5_audit_report.md`(9 High / 8 Medium / 2 Low)
> 被审方案:`blender_mcp_skill_acceptance_optimized_v3_5.md`,SHA-256 `775f93a2fcd18acdee937958b9fc92e4ce40a68dd2141d21b0af9df812e6175d`
> 验证日期:2026-08-24;仓库基线 `bf63c89`
> 验证方式:对每条可实证指控独立复现(Blender 5.2.0 实测、几何计算、仓库配置读取、上游 API 查询);对判断类指控做逻辑复核

## 总判定

**19 项发现中,18 项成立、1 项部分成立(严重度可下调);审计报告自身有 1 处引用错误。**

审计报告的核心结论——**不接受 V3.5"自包含且可执行、实现者无需另行拍板"的声明**——**我确认成立**。V3.5 的六门结构、判定分层、N/A 合成机制、夹具分类等仍然有效,但它在"表与表之间的可计算性"上确有断裂,其中三处会直接导致**合法资产被误拒**。

## 一、实测复现结果

| 指控 | 实测命令/计算 | 结果 |
|---|---|---|
| H-07.1 额外换轴错误 | Blender 5.2 导出 GLB 再导入 | `SRC (1,2,3)` → `IMPORTED (1,2,3)`。**回环本身已保坐标**;再套 V3.5 的 `(x,-z,y)` 会得到 `(1,-3,2)` → 合法资产被误拒。**指控成立** |
| H-08 相机距离裁切 | 50mm/36mm → hFOV | hFOV = 39.598°;容纳半径 r 的包围球需 `r/sin(FOV/2)` = **2.952r**,V3.5 冻结 2.6r → **裁切。指控成立**(正交 2.2r > 2r,该项无误) |
| M-03 GPU 探测 | background 调用 `gpu.platform.*` | 未 `gpu.init()` 抛 `SystemError`;init 后 backend=`METAL`、vendor=**`Apple M4`**(V3.5 示例写 `apple`,且无归一化规则)。**指控成立** |
| H-09 门禁不覆盖新包 | 读 `pyproject.toml` / `checks.sh` | ruff 范围 `protocol bridge server tests scripts smoke plugins/…`、mypy `files=[protocol, bridge/core, server]`、wheel/sdist `only-include=[protocol,bridge,server]`、`[project.scripts]` 仅 `blender-codex-server` —— 新增 `acceptance/` **完全不被 ruff/mypy/Bandit/分发覆盖**。**指控成立** |
| H-01 摘要无规范化 | 全文检索 `JCS|RFC 8785|canonical` | **0 命中**。V3.1 曾冻结 RFC 8785 JCS,V3.5 收敛时丢失 → 回归。**指控成立** |
| H-02 R0/R5 记录无产生方 | 读 §7.3 | `result.json.stage` 枚举仅 `"r1"|"r2"|"r3"|"r4"`,而注册表有 **3 个 R0 + 3 个 R5** check,无产生方定义。**指控成立** |
| M-01 `accepted` 字段缺失 | 检索 | `accepted=true` 出现在 §2.5 与正向夹具,但 result/summary 的 `checks[]` 字段表中**无该字段**;summary 亦丢 `tool_id/tool_version`。**指控成立** |
| M-02 未声明 warning | 检索 | §7.6 产生 `non_triangle_primitive`,注册表 `r3.budget.within_limits` 仅声明 `budget_near_limit` → 按 §2.5 该 warning **永不可 allowlist**。**指控成立** |
| L-01 锚定规则自违 | 检索 | §9 写"有两个 2026 CVE"却无 ID/链接,违反同节自定的锚定原则。**指控成立** |

## 二、逐条判定

### High(9 项:8 成立、1 部分成立)

| ID | 判定 | 说明 |
|---|---|---|
| H-01 `contract_digest` 无规范化算法 | **成立** | 实测 0 命中;两个语义相同的合同可因键序/`1` vs `1.0`/Unicode 得到不同摘要,`r5.contract.digest_stable` 无唯一 oracle |
| H-02 evidence file 闭集不可推导 | **成立** | 放行条款 4 要求 file ID 集严格相等,却无 file registry;差异图数量/ID/路径未冻结;`output_truncated` 未映射到任何 check;R0/R5 记录无产生方(实测确认) |
| H-03 failure family 无法表达正常拒收 | **成立** | 14 个 family 全是基础设施类;mesh 非法、validator error、预算超限等**最常见的拒收无 family 可选**,而 `success=false` 强制填一个。且 glTF-Validator **error 时非零退出**会被我的 `tool_crashed` 定义误判为工具崩溃——真实冲突 |
| H-04 单 warning_code 丢消息 | **成立** | validator 输出 `issues.messages[]` 多条并带 `issues.truncated`;单值模型无法表达"一条已 allowlist + 一条未 allowlist"共存,复制 check ID 又触发集合不等 |
| H-05 schema 仍是字段草图 | **部分成立(建议降 Medium)** | 实质成立:`preset:{...}`、`metrics: object` 等开放占位,无 `additionalProperties`/格式/范围约束,导出 preset 未展开,`tools.sha256` 允许 null。但"工具版本值延后填死"是 V3.5 **显式声明的延迟绑定**,且上一轮审计明确判其为合规延迟——两轮审计在此标准不一致,不宜按 High 计 |
| H-06 深层 manifest 无机器协议 | **成立** | §4 只有概念清单,无 JSON 字段表、稳定路径语法、同名消歧、排序与量化 tie-breaking → `r2.*` 与 GLB 投影的 source 侧**没有共同 oracle** |
| H-07 投影含 1 实测错误 + 2 假绿 | **成立(最严重)** | ①换轴实测误拒(见上);②PNG 重编码只比尺寸/通道 → 换张同尺寸贴图假绿;③去 `.001` 后缀会把 `Cube` 与 `Cube.001` 折叠错配。附带:`projection` 数组存的是中文描述而非稳定 ID,"并集等于 13 行"机器无法校验 |
| H-08 视觉协议误视角/裁切/漏内容 | **成立** | 除 2.6r 裁切外:`dir` 语义自相矛盾(表头称"相机朝向目标",公式却置于 `C+dir·d` 再看向 C,实际视向为 `-dir`);bounds 只取可见 **mesh**,而 pilot 资产含 9 个 Curve + 1 个 Font,curve-only 资产会被判空场景;beauty 用黑 world + strength 0 且未冻结 evaluator lights → 可能全黑;`all_views_rendered` 只验存在性,裁切仍全绿 |
| H-09 "零既有文件修改"与仓库事实冲突 | **成立** | 实测确认。安全敏感的验收代码可完全逃过全部静态门禁而 `checks.sh` 仍全绿 |

### Medium(8 项:7 成立、1 需标注审计间冲突)

| ID | 判定 | 说明 |
|---|---|---|
| M-01 `accepted` 与 schema 不一致 | **成立** | 实测确认 |
| M-02 `non_triangle_primitive` 未声明 | **成立** | 实测确认 |
| M-03 GPU 未初始化 + key 无归一化 | **成立** | 实测确认(`SystemError`;`Apple M4` vs 示例 `apple`) |
| M-04 夹具未覆盖全部 family | **成立** | §8.1 自定"每个 family 至少一个夹具",但 `toolchain_mismatch`、`tool_crashed`、`evidence_missing`、`hash_mismatch`、`runner_internal_error` 无对应夹具;夹具表缺 `expected_failure_code` 列 |
| M-05 C2PA 论证不成立 | **成立** | 其反驳逻辑正确:若合同要求 manifest 必须存在,则"从未验收"与"被剥离"**都直接失败**,无需区分。我的排除**结论**可保留(成本/生态),但**理由**必须改写 |
| M-06 复制原语造成双份真相 | **成立,但与上一轮审计直接冲突** | 上一轮审计的 M-09 明确判定"P0 先提取共享函数不是必要前置",据此我改为复制;本轮判定复制会漂移。两位审计员在此**结论相反**。我的判断:本轮更有说服力——因为 H-09 已证明"零既有文件修改"这一前提本身不成立(必须改 `checks.sh`/`pyproject.toml`),该约束一旦解除,复制的唯一理由随之消失 |
| M-07 L1 仍是选项列表 | **成立** | 无冻结 runner/seccomp profile/网络证明/`achieved_isolation_grade` 测量算法。不阻断 L0,但 L1 完成定义无法据本文实现 |
| M-08 合同权属与 policy 下限缺失 | **成立** | allowlist、视觉阈值、预算、`projection.lost`、blocklist 均可放宽拒收边界,却无不可突破的 policy baseline,也未规定 L1 下合同必须由可信侧产生 |

### Low(2 项:均成立)

| ID | 判定 |
|---|---|
| L-01 外部证据段违反自定锚定规则 | **成立**(实测确认无 CVE ID) |
| L-02 `platform_key_unknown` 命名与 Pass 语义相反 | **成立**,建议改 `platform_key_known` |

## 三、审计报告自身的错误(1 处)

**L-01 建议引用的 CVE 编号有误。** 报告建议补引 `CVE-2026-10661` 与 **`CVE-2026-10688`**。实测解析两条 GHSA:

- `GHSA-qqw9-95ww-prfm` → **CVE-2026-10661**(2026-06-03,low)✓
- `GHSA-5hr7-6m56-f3rg` → **CVE-2026-10662**(2026-06-03,low)——**不是 10688**

L-01 的**指控本身成立**(V3.5 确实未给 ID),但采纳其建议时须用正确编号 `CVE-2026-10662`。

另附一处口径澄清:该仓库 GitHub"Security advisories"页显示无已发布公告——这两条公告位于**全局 GitHub Advisory Database**,非仓库自建。引用时应指向 advisory DB 或 NVD。

## 四、审计间冲突记录(供后续裁决)

| 议题 | 上一轮(V3.4 自包含路) | 本轮(V3.5) | 我的判断 |
|---|---|---|---|
| 共享原语:复制 vs 提取 | M-09:复制是对的,提取非必要前置 | M-06:复制造成双份真相,应先提取 | 采纳本轮。H-09 已证明"零既有文件修改"不成立,复制的前提消失 |
| 工具版本延后填死 | 判为合规的延迟绑定,不计缺陷 | H-05 计入 High | 取中:实质缺陷成立但归 Medium,并要求 P0 首个提交即填死而非"实施时" |

## 五、结论与建议下一步

审计报告**可信**,其"architecture-ready / implementation-spec-not-ready"的状态标签是准确的。三处会**误拒合法资产**的缺陷(H-07.1 换轴、H-08 相机距离、H-08 curve-only 空场景)优先级最高——它们不是"规范不够细",而是**冻结了错误的参数**,照此实现会在第一个真实资产上失败。

建议修复顺序:

1. **先修三处误拒**(H-07.1 / H-08 相机 / H-08 bounds 范围)——参数错误,改动小、风险高;
2. **补两份注册表与一份算法**:file registry(H-02)、manifest schema(H-06)、摘要规范化(H-01,可直接采用 RFC 8785 JCS);
3. **重构失败模型**:区分 `check_failed` 与基础设施失败、承载 `findings[]` 多消息(H-03/H-04),并修正 validator 非零退出的归类;
4. **解除"零既有文件修改"约束**,把 `acceptance/` 纳入 ruff/mypy/Bandit/pytest 范围,同时按本轮结论改回提取共享原语(H-09 + M-06 一并解决);
5. 其余 Medium/Low 随附。
