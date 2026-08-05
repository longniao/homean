# Kawu — Technical Architecture v1.1

## Vertical-Agnostic Core, Real Estate as First Vertical Pack

> 原则：**产品定位、营销叙事、目标用户，100% 锁定地产买方经纪。**
> **只有底层数据模型和 AI Pipeline 做通用化设计**，这样以后要扩展时，改的是配置和 Prompt，不是推倒重来。
> 现阶段不实现任何非地产功能。
>
> v1.1 更新：采纳外部技术评审中低成本、高价值的改进——User/Workspace 分层、
> `Site` 改名为 `Subject`、`contact_id` 允许为空、为 Observation 增加溯源链
> （Evidence Chain）、明确 JSONB 使用边界、领域层命名约定。**这些都是字段/命名
> 层面的调整，不涉及新建任何管理界面或多行业功能，MVP 范围不变。**

------------------------------------------------------------------------

# 核心思路

把产品拆成两层：

```
+-------------------------------------------+
|         Vertical Pack (可替换层)           |
|   地产 / 汽车 / 酒店 / 餐饮 / ...            |
|   - 分区分类词表 (Zone Taxonomy)            |
|   - 观察维度定义 (Observation Schema)        |
|   - AI Prompt 模板                          |
|   - 报告排版模板                            |
|   - 客户/联系人角色命名                      |
+-------------------------------------------+
                    ^ 读取配置
+-------------------------------------------+
|          Core Platform (通用层)             |
|   - 录制 / 转写 / 媒体管理                   |
|   - 结构化提取引擎                          |
|   - 报告生成引擎                            |
|   - 客户工作台 / 账户体系                    |
|   - 数据库 Schema (通用实体)                 |
+-------------------------------------------+
```

**现阶段只做一个 Vertical Pack：real_estate。** 其他行业不写代码，只是架构上预留了插槽。

------------------------------------------------------------------------

# 数据模型（通用实体命名，v1.1）

用行业中立的命名，地产是第一个"实例化"：

```
Vertical
  id: "real_estate"
  display_name_en: "Real Estate"
  display_name_zh: "房产"
  zone_taxonomy: [...]        # 见下方
  observation_schema: [...]   # 见下方
  report_template_id: "real_estate_v1"

User (身份，与角色分离)
  id
  email / phone
  name

Workspace (组织/工作空间，MVP 阶段等同于单人经纪自己)
  id
  name
  # Phase 1: 每个 User 自动拥有一个默认 Workspace，不涉及团队 UI
  # Phase 2: 团队协作时，Workspace 可容纳多个 Membership

Membership
  id
  user_id -> User
  workspace_id -> Workspace

ProfessionalProfile
  id
  membership_id -> Membership
  vertical_id -> Vertical
  role: "buyers_agent"        # 地产垂直下的角色，不同垂直角色名不同

Contact (原来叫 Client / Buyer)
  id
  workspace_id -> Workspace
  name, contact_info
  # 地产：买家客户；汽车：潜在购车人；酒店：验房委托方

Subject (原来叫 Site / Property)
  id
  vertical_id -> Vertical
  subject_type: "property"    # 未来: "vehicle" / "hotel_room" / "equipment"
  display_name
  location (可为空，非地点类主体不需要)
  attributes: JSONB           # 地产专属字段（户型、面积等）放这里，不进核心表结构

Visit
  id
  workspace_id -> Workspace
  subject_id -> Subject
  created_by -> User
  contact_id -> Contact (nullable)      # 允许无客户关联：内部留档/自用/质检
  professional_profile_id -> ProfessionalProfile
  started_at, ended_at
  status: draft / confirmed / sent_to_client

Zone (原来叫 Room)
  id
  visit_id -> Visit
  zone_type: 由 Vertical.zone_taxonomy 决定
  # 地产：kitchen / bedroom / basement...
  # 未来汽车：engine_bay / interior / trunk...

Observation (核心结构 + 溯源链)
  id
  visit_id -> Visit
  zone_id -> Zone (可为空，允许 visit 级别的整体观察)
  category: 由 Vertical.observation_schema 决定
  # 地产：pro / con / concern / follow_up / noise / light...
  content: text
  source_type: ai_generated / professional_edited
  source_transcript_segment_id -> TranscriptSegment (nullable)
  source_media_id -> RawMedia (nullable)
  timestamp_start / timestamp_end (nullable)
  ai_model
  prompt_version
  confidence: float
  review_status: pending / confirmed / edited
  reviewed_by -> User (nullable)
  reviewed_at (nullable)

RawMedia
  id
  visit_id -> Visit
  type: audio / photo / video
  storage_url
  timestamp_offset

TranscriptSegment
  id
  visit_id -> Visit
  raw_media_id -> RawMedia
  text
  timestamp_start / timestamp_end

Report
  id
  visit_id -> Visit
  template_id: 由 Vertical.report_template_id 决定
  content: JSONB (结构化) + rendered_html/pdf
  status
```

**JSONB 使用边界**：`Subject.attributes`、`Zone.zone_type` 的取值范围、`Observation.category` 的取值范围，走 JSONB + 配置表，因为这些字段行业专属、易变。但 `workspace_id`、`created_by`、`contact_id`、`visit.status`、`observation.review_status` 这类**高频查询、需要筛选/统计的字段，一律用普通列，不塞进 JSONB**——这条边界现在定好，能省掉以后做数据分析和迁移时的大量麻烦。

**Evidence Chain 的价值**：每条 Observation 都能回溯到具体的转写片段、原始媒体、时间戳。这不只是工程上的严谨，直接服务于产品文档里提过的法律风险顾虑——经纪或客户对某条 AI 生成的观察有疑问时，可以直接点开查看原始录音/照片依据，这对信任建立和潜在的法律免责都有实际价值。

------------------------------------------------------------------------

# 领域层命名约定（保持开发者可读性）

数据库层用通用命名（Subject、Zone、Observation），但代码服务层/类型层用地产专属命名，两者不冲突：

```python
# 数据库表: subjects, zones, observations (通用)
# 服务层: 地产专属命名，读起来像地产产品，不是"某个通用平台"

class RealEstateShowingService:
    """基于通用 Visit 核心，封装地产带看专属逻辑"""
    def start_showing(self, property_id, buyer_contact_id=None): ...
    def generate_showing_report(self, visit_id): ...

class RealEstateZoneTaxonomy:
    ROOM_TYPES = ["kitchen", "living_room", "primary_bedroom", "basement", ...]

class RealEstateReportSchema:
    SECTIONS = ["executive_summary", "room_by_room", "pros", "cons", "follow_up"]
```

这样团队内部读代码时，看到的是"地产带看服务"，不是抽象的"垂直无关平台"，避免为了通用性牺牲现在的开发效率和可读性。

------------------------------------------------------------------------

# AI Pipeline：Prompt 参数化，不是代码分支

现在的 Pipeline：

```
录音 -> 转写 -> 转写分段 -> 分区识别 -> 结构化提取(含溯源) -> 报告生成
```

每一步的 Prompt 都从 Vertical 配置里读取参数，而不是写死在代码里：

```python
# 伪代码示意
def generate_zone_detection_prompt(vertical: Vertical, transcript: str) -> str:
    return f"""
    你正在分析一段 {vertical.display_name_zh} 场景的实地走查录音。
    请将以下内容按照这些分区类型归类：{vertical.zone_taxonomy}
    转写内容：{transcript}
    """

def generate_observation_extraction_prompt(vertical: Vertical, zone_content: str) -> str:
    return f"""
    请将以下观察内容归类到这些维度：{vertical.observation_schema}
    内容：{zone_content}
    请在输出中标注每条观察对应的原始转写片段位置，用于溯源。
    """
```

**现阶段 vertical.zone_taxonomy 和 vertical.observation_schema 只填一份地产的配置**，存在数据库配置表或者一个 YAML/JSON 配置文件里即可，不需要做管理后台。

**设计提醒（不是现在要做的事）**：未来行业如果处理流程本身不同（不只是分类词表不同），Prompt 参数化可能不够用，届时 Pipeline 需要支持可配置的处理步骤。现在 MVP 只需要实现地产这一套固定流程，这个提醒只是记录在案，不需要现在设计"可配置步骤"这个机制本身。

------------------------------------------------------------------------

# 报告生成：模板引擎，不是硬编码页面

报告排版（客户看到的最终 PDF/链接）用模板系统，template_id 决定字段顺序、视觉风格、品牌位。

技术实现上，Next.js 前端用一个通用的 `<ReportRenderer template={templateId} data={reportContent} />` 组件，模板本身是数据驱动的 JSON 配置 + 少量 React 组件变体。**不做通用的可视化报告设计器**——地产报告应该做得足够"手工打磨"，保证专业感和产品体验，不为了通用性牺牲这一点。

------------------------------------------------------------------------

# App 策略：一个 App，还是多个 App？

**建议：现阶段一个 App、一个代码库、一套地产用户体验、一个后端、只激活一个 Vertical Pack。MVP 阶段不做行业选择器。**

如果未来验证出第二个行业，两条路都可行，到时候看情况选：

- **同一个 App 内加行业选择**：用户群体有重叠、Kawu 品牌能跨行业成立、工作流明显共享时选这条。
- **新 App、共用同一套后端 API**：两个行业用户画像/获客渠道差异大、需要独立品牌定位时选这条。

现在不用做这个决策，架构已经支持两条路都走得通。

------------------------------------------------------------------------

# 工作流架构：核心状态机通用，UI 语言按行业变化

```
创建 Visit -> 采集 -> 处理 -> 审核 -> 确认 -> 交付 -> 归档
```

地产 Vertical Pack 呈现为：

```
开始带看 -> 录制房间与评论 -> 生成带看报告 -> 经纪审核 -> 发送给买家
```

后端状态机保持不变，UI 文案和行业规则由 Vertical Pack 决定。

------------------------------------------------------------------------

# 现阶段具体要做 / 不做

## 现在就做（成本很低，属于工程规范，不是新功能）

- User / Workspace / Membership / ProfessionalProfile 分层，避免"人"与"角色"焊死
- 数据库表用通用命名（Subject 不是 Property，Zone 不是 Room），加 vertical_id 外键
- Zone.zone_type、Observation.category 用可配置值，不用数据库层面写死的 enum
- Visit.contact_id 允许为空，支持无客户关联的带看记录
- Observation 增加溯源链字段（关联转写片段、原始媒体、时间戳）
- AI Prompt 做成可参数化模板，参数来自配置而非硬编码字符串
- 报告模板做成数据驱动，不是每个字段写死在前端组件里
- 高频查询字段用普通列，行业专属/易变字段才用 JSONB
- 代码服务层/类型层使用地产专属命名（RealEstateShowingService 等），保持开发者可读性

## 现在不做（即使架构支持，也不实现）

- 不建行业配置管理后台（现在手动改配置文件/数据库记录就够）
- 不做团队协作 UI 和完整 RBAC 系统（Workspace/Membership 表结构预留，但不做团队管理界面）
- 不做多行业账户切换逻辑，不做行业选择器
- 不设计第二个 Vertical 的具体 taxonomy
- 不做可配置的 Pipeline 处理步骤机制（只实现地产这一套固定流程）
- 不做通用可视化报告设计器
- 不做跨 Vertical 的数据分析/聚合功能
- 不做插件系统、不做外部开发者 API

------------------------------------------------------------------------

# 一句话总结

**这份架构让你半年后如果验证出要扩展到第二个行业时，工作量是"填一份配置 + 写一版 Prompt + 设计一版报告模板"（大概 1-2 周），而不是"重新设计数据库和 Pipeline"（大概 1-2 个月）。**

v1.1 在此基础上补齐了身份/角色分层、溯源链、JSONB 边界这几处原本会在后期造成返工成本的细节，代价是现在多花大概 2-3 天做这些字段和表结构设计，投入产出比合理，可以直接采用。产品范围、用户定位、营销叙事，继续 100% 聚焦地产买方经纪，不受这份架构影响。
