"""
知识点种子数据初始化脚本
运行: python manage.py shell < word/sql/seed_knowledge_points.py
"""
from apps.knowledge.models import KnowledgePoint

# 初中物理知识点数据
PHYSICS_KNOWLEDGE_POINTS = [
    # 七年级
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "机械运动", "module": "长度和时间的测量", "node_type": "general", "content": "长度的单位及换算，时间的测量，误差与错误"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "机械运动", "module": "运动的描述", "node_type": "general", "content": "参照物，机械运动，运动和静止的相对性"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "机械运动", "module": "运动的快慢", "node_type": "general", "content": "速度公式v=s/t，匀速直线运动，变速运动"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "声现象", "module": "声音的产生与传播", "node_type": "general", "content": "声音的产生，声音的传播条件，声速"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "声现象", "module": "声音的特性", "node_type": "general", "content": "音调，响度，音色"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "物态变化", "module": "温度和温度计", "node_type": "general", "content": "温度概念，温度计的使用，摄氏温度"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "物态变化", "module": "熔化和凝固", "node_type": "general", "content": "晶体与非晶体，熔点，熔化吸热凝固放热"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "物态变化", "module": "汽化和液化", "node_type": "general", "content": "蒸发，沸腾，液化方法"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "物态变化", "module": "升华和凝华", "node_type": "general", "content": "升华吸热，凝华放热"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "光现象", "module": "光的直线传播", "node_type": "general", "content": "光源，光的直线传播，光线，影的形成"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "光现象", "module": "光的反射", "node_type": "general", "content": "反射定律，镜面反射，漫反射"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "光现象", "module": "平面镜成像", "node_type": "general", "content": "平面镜成像特点，虚像"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "透镜及其应用", "module": "透镜", "node_type": "general", "content": "凸透镜，凹透镜，焦点，焦距"},
    {"grade_index": 7, "grade_name": "七年级", "term": "up", "chapter": "透镜及其应用", "module": "凸透镜成像规律", "node_type": "general", "content": "物距像距关系，成像特点"},

    # 八年级
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "质量与密度", "module": "质量", "node_type": "general", "content": "质量概念，单位，测量工具"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "质量与密度", "module": "密度", "node_type": "general", "content": "密度公式ρ=m/V，密度是物质特性"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "力", "module": "力", "node_type": "general", "content": "力的概念，力的作用效果，力的三要素"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "力", "module": "弹力", "node_type": "general", "content": "弹性形变，弹簧测力计"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "力", "module": "重力", "node_type": "general", "content": "重力公式G=mg，重力方向"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "运动和力", "module": "牛顿第一定律", "node_type": "general", "content": "惯性，牛顿第一定律"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "运动和力", "module": "二力平衡", "node_type": "general", "content": "平衡状态，二力平衡条件"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "运动和力", "module": "摩擦力", "node_type": "general", "content": "摩擦力产生条件，影响摩擦力大小的因素"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "压强", "module": "压强", "node_type": "general", "content": "压强公式p=F/S，增大减小压强方法"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "压强", "module": "液体压强", "node_type": "general", "content": "液体压强公式p=ρgh，连通器"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "压强", "module": "大气压强", "node_type": "general", "content": "大气压存在，托里拆利实验"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "浮力", "module": "浮力", "node_type": "general", "content": "浮力产生原因，阿基米德原理F浮=ρ液gV排"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "浮力", "module": "物体的浮沉条件", "node_type": "general", "content": "浮沉条件，轮船，潜水艇，气球"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "功和机械能", "module": "功", "node_type": "general", "content": "功的公式W=Fs，做功必要因素"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "功和机械能", "module": "功率", "node_type": "general", "content": "功率公式P=W/t"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "功和机械能", "module": "动能和势能", "node_type": "general", "content": "动能，重力势能，弹性势能，机械能守恒"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "简单机械", "module": "杠杆", "node_type": "general", "content": "杠杆五要素，杠杆平衡条件F1L1=F2L2"},
    {"grade_index": 8, "grade_name": "八年级", "term": "up", "chapter": "简单机械", "module": "滑轮", "node_type": "general", "content": "定滑轮，动滑轮，滑轮组"},

    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "声现象", "module": "声音的产生与传播", "node_type": "general", "content": "声音的产生，传播介质，声速"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "光现象", "module": "光的反射和折射", "node_type": "general", "content": "反射定律，折射规律"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "透镜", "module": "凸透镜成像", "node_type": "general", "content": "成像规律，应用"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "物态变化", "module": "温度和物态变化", "node_type": "general", "content": "六种物态变化，吸放热"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电流和电路", "module": "电荷", "node_type": "general", "content": "摩擦起电，电荷间相互作用"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电流和电路", "module": "电路", "node_type": "general", "content": "电路组成，电路图，串联并联"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电流和电路", "module": "电流", "node_type": "general", "content": "电流方向，电流表使用"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电压电阻", "module": "电压", "node_type": "general", "content": "电压概念，电压表使用"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电压电阻", "module": "电阻", "node_type": "general", "content": "电阻概念，影响电阻大小的因素"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "欧姆定律", "module": "欧姆定律", "node_type": "general", "content": "欧姆定律I=U/R，伏安法测电阻"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电功率", "module": "电能和电功率", "node_type": "general", "content": "电功W=UIt，电功率P=UI"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电功率", "module": "焦耳定律", "node_type": "general", "content": "焦耳定律Q=I²Rt"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电与磁", "module": "磁现象", "node_type": "general", "content": "磁体，磁场，磁感线"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电与磁", "module": "电生磁", "node_type": "general", "content": "电流的磁效应，电磁铁"},
    {"grade_index": 8, "grade_name": "八年级", "term": "down", "chapter": "电与磁", "module": "电磁感应", "node_type": "general", "content": "电磁感应现象，发电机"},

    # 九年级
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "分子热运动", "module": "分子动理论", "node_type": "general", "content": "分子动理论，扩散现象，分子间作用力"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "内能", "module": "内能", "node_type": "general", "content": "内能概念，改变内能的方式"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "内能的利用", "module": "热机", "node_type": "general", "content": "热机工作原理，四冲程"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "电流和电路", "module": "电路基础", "node_type": "general", "content": "电路组成，串并联电路特点"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "电压电阻", "module": "电压和电阻", "node_type": "general", "content": "电压规律，电阻规律"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "欧姆定律", "module": "欧姆定律应用", "node_type": "general", "content": "欧姆定律，动态电路分析"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "电功率", "module": "电功率计算", "node_type": "general", "content": "电功率，额定功率，实际功率"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "电与磁", "module": "电磁现象", "node_type": "general", "content": "磁场对电流作用，电磁感应"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "信息的传递", "module": "电磁波", "node_type": "general", "content": "电磁波，波速波长频率关系"},
    {"grade_index": 9, "grade_name": "九年级", "term": "up", "chapter": "能源与可持续发展", "module": "能源", "node_type": "general", "content": "能源分类，新能源，能量转化"},

    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "力学综合", "module": "力和运动", "node_type": "general", "content": "力的合成，运动学公式"},
    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "力学综合", "module": "压强浮力综合", "node_type": "general", "content": "压强浮力综合计算"},
    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "力学综合", "module": "功和能综合", "node_type": "general", "content": "机械效率，能量转化"},
    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "电学综合", "module": "电路综合", "node_type": "general", "content": "复杂电路分析，动态电路"},
    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "电学综合", "module": "电功率综合", "node_type": "general", "content": "电功率综合计算，安全用电"},
    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "实验专题", "module": "力学实验", "node_type": "method", "content": "测量密度，探究摩擦力，探究浮力"},
    {"grade_index": 9, "grade_name": "九年级", "term": "down", "chapter": "实验专题", "module": "电学实验", "node_type": "method", "content": "伏安法测电阻，测小灯泡功率"},
]


def run():
    """执行种子数据导入"""
    print(f'当前知识点数量: {KnowledgePoint.objects.count()}')

    created_count = 0
    for kp_data in PHYSICS_KNOWLEDGE_POINTS:
        _, created = KnowledgePoint.objects.get_or_create(
            subject='physics',
            grade_index=kp_data['grade_index'],
            grade_name=kp_data['grade_name'],
            term=kp_data['term'],
            chapter=kp_data['chapter'],
            module=kp_data['module'],
            defaults={
                'node_type': kp_data['node_type'],
                'content': kp_data['content'],
            }
        )
        if created:
            created_count += 1

    print(f'新增知识点: {created_count}条')
    print(f'当前知识点总数: {KnowledgePoint.objects.count()}')

    # 验证
    for subject, label in KnowledgePoint.SUBJECT_CHOICES:
        count = KnowledgePoint.objects.filter(subject=subject).count()
        print(f'  {label} ({subject}): {count}条')


if __name__ == '__main__':
    run()
