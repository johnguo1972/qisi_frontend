import pytest


@pytest.mark.django_db
def test_controlled_topic_keeps_stable_path_and_standard_module_names():
    from apps.knowledge.models import KnowledgeTopic, KnowledgeTopicModule

    topic = KnowledgeTopic.objects.create(
        id="junior-physics-mechanics",
        subject="physics",
        stage="junior",
        name="力学",
        sort_order=10,
    )
    link = KnowledgeTopicModule.objects.create(
        topic=topic,
        module="内能",
        sort_order=1,
    )

    assert link.module == "内能"
    assert topic.path_ids == ["junior-physics-mechanics"]


@pytest.mark.django_db
def test_controlled_topic_builds_path_from_parent():
    from apps.knowledge.models import KnowledgeTopic

    root = KnowledgeTopic.objects.create(
        id="junior-physics-mechanics",
        subject="physics",
        stage="junior",
        name="力学",
        sort_order=10,
    )
    child = KnowledgeTopic.objects.create(
        id="junior-physics-mechanics-motion",
        subject="physics",
        stage="junior",
        parent=root,
        name="运动与力",
        sort_order=10,
    )

    assert child.path_ids == [
        "junior-physics-mechanics",
        "junior-physics-mechanics-motion",
    ]
