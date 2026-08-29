import pytest
from django.db import connection


@pytest.fixture
def topic_tree(db):
    from apps.knowledge.models import KnowledgeTopic, KnowledgeTopicModule

    with connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS knowledge_points (
                id BIGINT PRIMARY KEY,
                subject VARCHAR(50), stage VARCHAR(20), grade_index SMALLINT,
                grade_name VARCHAR(20), term VARCHAR(10), chapter VARCHAR(255),
                module VARCHAR(255), node_type VARCHAR(20), content TEXT,
                created_at TIMESTAMP
            )
            """
        )
        cursor.execute("DELETE FROM knowledge_points WHERE id = 990001")
        cursor.execute(
            """
            INSERT INTO knowledge_points
            (id, subject, stage, grade_index, grade_name, term, chapter, module, node_type, content)
            VALUES (990001, 'physics', 'junior', 8, '八年级', 'up', '第十三章 内能', '内能', 'general', '测试知识点')
            """
        )

    root = KnowledgeTopic.objects.create(
        id="junior-physics-thermal",
        subject="physics",
        stage="junior",
        name="热学",
    )
    leaf = KnowledgeTopic.objects.create(
        id="junior-physics-thermal-inner-energy",
        subject="physics",
        stage="junior",
        parent=root,
        name="第十三章 内能",
    )
    KnowledgeTopicModule.objects.create(topic=leaf, module="内能")
    return {"root": root, "leaf": leaf}


@pytest.mark.django_db
def test_leaf_candidates_are_limited_to_selected_topic_and_keep_standard_ids(topic_tree):
    from apps.knowledge.controlled_catalog import leaf_knowledge_candidates

    candidates = leaf_knowledge_candidates(topic_tree["leaf"].id)

    assert candidates == [{
        "id": "内能",
        "module": "内能",
        "chapter": "第十三章 内能",
        "full_label": "物理-初中-八年级上学期",
    }]


def test_validate_selected_ids_rejects_candidate_escape():
    from apps.knowledge.controlled_catalog import (
        ControlledCatalogSelectionError,
        validate_selected_ids,
    )

    with pytest.raises(ControlledCatalogSelectionError, match="outside"):
        validate_selected_ids(["kp-1"], ["kp-2"])
