import json

import pytest
from django.db import connection
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.knowledge.models import KnowledgeTopic, KnowledgeTopicModule


@pytest.mark.django_db
def test_import_catalog_rejects_unknown_standard_knowledge_point(tmp_path):
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
    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(
        json.dumps(
            {
                "catalog_version": "test-v1",
                "topics": [
                    {
                        "id": "junior-physics-thermal",
                        "subject": "physics",
                        "stage": "junior",
                        "name": "热学",
                        "sort_order": 10,
                        "modules": ["unknown-module"],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CommandError, match="unknown standard knowledge point"):
        call_command("import_controlled_topic_catalog", path=str(catalog_file))


@pytest.mark.django_db
def test_import_catalog_prefers_specific_and_earlier_chapter_keywords(tmp_path):
    """Catch broad mechanics keywords stealing thermal or electricity chapters."""
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
        cursor.execute("DELETE FROM knowledge_points WHERE id IN (991101, 991102)")
        cursor.execute(
            """
            INSERT INTO knowledge_points
            (id, subject, stage, grade_index, grade_name, term, chapter, module,
             node_type, content, created_at)
            VALUES
            (991101, 'physics', 'junior', 9, '九年级', 'up',
             '第十三章 内能', '分子动理论', 'general', 'fixture', CURRENT_TIMESTAMP),
            (991102, 'physics', 'junior', 9, '九年级', 'up',
             '第十八章 电功率', '电功率的计算', 'general', 'fixture', CURRENT_TIMESTAMP)
            """
        )

    catalog_file = tmp_path / "catalog.json"
    catalog_file.write_text(
        json.dumps(
            {
                "catalog_version": "test-v2",
                "topics": [
                    {
                        "id": "junior-physics-mechanics",
                        "subject": "physics",
                        "stage": "junior",
                        "name": "力学",
                        "chapter_keywords": ["力", "能"],
                    },
                    {
                        "id": "junior-physics-thermal",
                        "subject": "physics",
                        "stage": "junior",
                        "name": "热学",
                        "chapter_keywords": ["热", "内能"],
                    },
                    {
                        "id": "junior-physics-electricity",
                        "subject": "physics",
                        "stage": "junior",
                        "name": "电学",
                        "chapter_keywords": ["电"],
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    mechanics = KnowledgeTopic.objects.create(
        id="junior-physics-mechanics",
        subject="physics",
        stage="junior",
        name="力学",
        catalog_version="old-v1",
    )
    stale_leaf = KnowledgeTopic.objects.create(
        id="stale-mechanics-internal-energy",
        subject="physics",
        stage="junior",
        parent=mechanics,
        name="第十三章 内能",
        catalog_version="old-v1",
    )
    KnowledgeTopicModule.objects.create(topic=stale_leaf, module="分子动理论")

    call_command("import_controlled_topic_catalog", path=str(catalog_file))

    thermal_leaf = KnowledgeTopic.objects.get(
        parent_id="junior-physics-thermal", name="第十三章 内能"
    )
    electricity_leaf = KnowledgeTopic.objects.get(
        parent_id="junior-physics-electricity", name="第十八章 电功率"
    )
    assert list(
        KnowledgeTopicModule.objects.filter(topic=thermal_leaf).values_list(
            "module", flat=True
        )
    ) == ["分子动理论"]
    assert list(
        KnowledgeTopicModule.objects.filter(topic=electricity_leaf).values_list(
            "module", flat=True
        )
    ) == ["电功率的计算"]
    assert not KnowledgeTopic.objects.filter(
        parent_id="junior-physics-mechanics",
        name__in=["第十三章 内能", "第十八章 电功率"],
    ).exists()
