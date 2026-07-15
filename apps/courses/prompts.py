"""Prompt templates for variant question generation and verification."""


VARIANT_SYSTEM_PROMPT = """你是一个专业的中小学数学题目设计专家。你的任务是根据给定的原题，生成一道变式题。

变式题的要求：
1. 保持原题的核心知识点和解题方法
2. 改变题目中的具体数值、情境或表述方式
3. 难度与原题相当或略有变化
4. 生成的题目必须符合指定的题型（单选题、多选题、填空题、简答题、计算题、证明题）
5. 如果是选择题，选项要有区分度，干扰项要合理
6. 题目内容要完整、准确、无歧义

请以严格的 JSON 格式输出，不要包含任何其他文字。JSON 格式如下：
{
    "stem": "题干内容（支持 LaTeX 公式，使用 $$ 包裹行内公式）",
    "question_type": "题型，与原题一致",
    "options": [
        {"label": "A", "content": "选项A内容"},
        {"label": "B", "content": "选项B内容"},
        {"label": "C", "content": "选项C内容"},
        {"label": "D", "content": "选项D内容"}
    ],
    "answer": "答案（选择题为正确选项字母，如 A；非选择题为具体答案）",
    "analysis": "简要分析",
    "solution": "详细解题过程",
    "difficulty": 3,
    "knowledge_points": [{"module": "知识点模块", "full_label": "知识点完整标签"}],
    "variant_mode": "变式模式描述",
    "changes_from_original": "说明与原题的主要变化点"
}

注意事项：
- 单选题（single_choice）只有一个正确答案，选项 A/B/C/D 内容必须互不相同
- 多选题（multiple_choice）有2-4个正确答案，answer 用逗号分隔如 "A,C"
- 填空题（fill_blank）和计算题（computation）的 answer 为具体数值或表达式
- 难度范围 1-5，1为最简单，5为最难
- 所有 LaTeX 公式使用 $$ 包裹，如 $$x^2 + 2x + 1 = 0$$"""


VERIFIER_SYSTEM_PROMPT = """你是一个严格的题目校验专家。你的任务是校验 AI 生成的变式题是否符合要求。

校验维度：
1. JSON 结构完整性 — 所有必填字段是否存在
2. 题型一致性 — question_type 是否与要求的题型一致
3. 答案数量正确性 — 选择题的选项数量和答案匹配
4. 值域合理性 — 数值是否在合理范围内
5. 单选题唯一性 — 单选题只能有一个正确答案
6. 题目完整性 — 题干是否完整、无截断
7. 知识点相关性 — 知识点是否与原题相关

请以严格的 JSON 格式输出校验结果：
{
    "passed": true,
    "issues": [],
    "score": 0.95,
    "summary": "校验通过，题目质量良好"
}

如果校验不通过：
{
    "passed": false,
    "issues": ["问题1描述", "问题2描述"],
    "score": 0.6,
    "summary": "存在以下问题：..."
}"""


def build_variant_user_prompt(question_data: dict, variant_mode: str) -> str:
    """构建变式题生成的 User Prompt。

    Args:
        question_data: 原题数据，包含 stem, question_type, answer, analysis,
                       solution, difficulty, knowledge_points, options 等
        variant_mode: 变式模式描述（如 "数值变化"、"情境变化"、"逆向思维"）

    Returns:
        完整的 User Prompt 字符串
    """
    q = question_data

    # 构建原题信息
    parts = []
    parts.append("## 原题信息\n")
    parts.append(f"**题干**：{q.get('stem', '')}")
    parts.append(f"**题型**：{q.get('question_type', 'unknown')}")
    parts.append(f"**答案**：{q.get('answer', '')}")
    parts.append(f"**难度**：{q.get('difficulty', 3)}")

    if q.get('analysis'):
        parts.append(f"**分析**：{q['analysis']}")
    if q.get('solution'):
        parts.append(f"**详解**：{q['solution']}")

    if q.get('knowledge_points'):
        kp_list = ", ".join(
            kp.get('module', '') or kp.get('full_label', '')
            for kp in q['knowledge_points'] if kp
        )
        parts.append(f"**知识点**：{kp_list}")

    if q.get('options'):
        parts.append("\n**选项**：")
        for opt in q['options']:
            parts.append(f"  {opt.get('label', '?')}: {opt.get('content', '')}")

    parts.append(f"\n## 变式要求\n")
    parts.append(f"变式模式：{variant_mode}")
    parts.append(f"请根据上述原题，生成一道{variant_mode}的变式题。")
    parts.append(f"题型保持为：{q.get('question_type', 'unknown')}")
    parts.append(f"\n请直接输出 JSON，不要包含任何其他说明文字。")

    return "\n".join(parts)


def build_verifier_user_prompt(variant_json: dict, original_question_data: dict) -> str:
    """构建校验器的 User Prompt。

    Args:
        variant_json: AI 生成的变式题 JSON
        original_question_data: 原题数据

    Returns:
        完整的 User Prompt 字符串
    """
    parts = []
    parts.append("## 待校验的变式题\n")
    parts.append(f"```json\n{variant_json}\n```")

    parts.append("\n## 原题信息（用于对比）\n")
    parts.append(f"**题干**：{original_question_data.get('stem', '')}")
    parts.append(f"**题型**：{original_question_data.get('question_type', 'unknown')}")
    parts.append(f"**答案**：{original_question_data.get('answer', '')}")

    if original_question_data.get('knowledge_points'):
        kp_list = ", ".join(
            kp.get('module', '') or kp.get('full_label', '')
            for kp in original_question_data['knowledge_points'] if kp
        )
        parts.append(f"**知识点**：{kp_list}")

    parts.append("\n请校验上述变式题是否符合要求。")
    parts.append("请直接输出 JSON，不要包含任何其他说明文字。")

    return "\n".join(parts)
