"""Tests for knowledge app."""
from django.test import SimpleTestCase, TransactionTestCase
from apps.knowledge.models import KnowledgePoint


class KnowledgePointModelUnitTest(SimpleTestCase):
    """Test KnowledgePoint model logic without DB."""

    def test_str_representation(self):
        point = KnowledgePoint(
            id=1, subject='math', stage='primary',
            grade_index=1, grade_name='一年级', term='up',
            chapter='准备课', module='数的认识',
            node_type='formula', content='1+1=2',
        )
        self.assertEqual(str(point), '数学-准备课-数的认识')

    def test_full_label_property(self):
        point = KnowledgePoint(
            id=1, subject='math', stage='primary',
            grade_index=1, grade_name='一年级', term='up',
            chapter='准备课', module='数的认识',
            node_type='formula', content='1+1=2',
        )
        label = point.full_label
        self.assertEqual(label, '数学-小学-一年级上学期')

    def test_full_label_senior(self):
        point = KnowledgePoint(
            id=2, subject='physics', stage='senior',
            grade_index=10, grade_name='高一', term='down',
            chapter='力学', module='牛顿定律',
            node_type='property', content='F=ma',
        )
        self.assertEqual(point.full_label, '物理-高中-高一下学期')

    def test_choices_defined(self):
        """Verify all choice constants are properly defined."""
        self.assertEqual(len(KnowledgePoint.SUBJECT_CHOICES), 2)
        self.assertEqual(len(KnowledgePoint.STAGE_CHOICES), 3)
        self.assertEqual(len(KnowledgePoint.TERM_CHOICES), 2)
        self.assertEqual(len(KnowledgePoint.NODE_TYPE_CHOICES), 5)

    def test_meta_db_table(self):
        """Verify model maps to correct table."""
        self.assertEqual(KnowledgePoint._meta.db_table, 'knowledge_points')
        self.assertFalse(KnowledgePoint._meta.managed)


class KnowledgePointEndpointTest(TransactionTestCase):
    """Test knowledge endpoints via HTTP client with real DB.

    Uses TransactionTestCase because managed=False models can't use
    Django's test transaction rollback. The PostgreSQL test DB must have
    the knowledge_points table (copied from the main DB).
    """

    def setUp(self):
        """Ensure knowledge_points table exists in test DB."""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS knowledge_points CASCADE")
            cursor.execute("""
                CREATE TABLE knowledge_points (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    subject VARCHAR(50),
                    stage VARCHAR(20),
                    grade_index SMALLINT,
                    grade_name VARCHAR(20),
                    term VARCHAR(10),
                    chapter VARCHAR(255),
                    module VARCHAR(255),
                    node_type VARCHAR(20),
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Seed some test data
            cursor.execute("SELECT COUNT(*) FROM knowledge_points")
            if cursor.fetchone()[0] == 0:
                cursor.executemany(
                    "INSERT INTO knowledge_points (subject, stage, grade_index, grade_name, term, chapter, module, node_type, content) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    [
                        ('math', 'primary', 1, '一年级', 'up', '准备课', '数的认识', 'formula', '1+1=2'),
                        ('math', 'primary', 1, '一年级', 'up', '准备课', '数的组成', 'property', '5以内数的组成'),
                        ('physics', 'junior', 8, '八年级', 'up', '力学', '牛顿定律', 'formula', 'F=ma'),
                    ]
                )

    def tearDown(self):
        """Clean up test data."""
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM knowledge_points WHERE chapter='e2e_test_cp'")
            cursor.execute("DROP TABLE IF EXISTS knowledge_points CASCADE")

    def test_tree_data_returns_json(self):
        """Tree-data endpoint should return valid JSON array."""
        resp = self.client.get('/knowledge/tree-data/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)
        self.assertIn('id', data[0])
        self.assertIn('label', data[0])
        self.assertIn('children', data[0])

    def test_tree_data_has_correct_structure(self):
        """Tree should have math and physics at top level."""
        resp = self.client.get('/knowledge/tree-data/')
        data = resp.json()
        labels = {item['label'] for item in data}
        self.assertIn('数学', labels)
        self.assertIn('物理', labels)

    def test_chapter_points_returns_html(self):
        """Chapter points endpoint should return HTML table."""
        resp = self.client.get(
            '/knowledge/chapter/准备课/',
            {
                'subject': 'math',
                'stage': 'primary',
                'grade_index': '1',
                'term': 'up',
            }
        )
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'kp-table')

    def test_point_form_new_returns_form(self):
        """New point form should return valid HTML."""
        resp = self.client.get('/knowledge/point/new/', {
            'subject': 'math', 'stage': 'primary',
            'grade_index': '1', 'term': 'up',
            'chapter': '准备课', 'module': '', 'node_type': 'formula',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'kp-form')

    def test_point_create_and_delete(self):
        """Should create and then delete a knowledge point via HTTP."""
        # Create
        resp = self.client.post('/knowledge/point/new/submit/', {
            'subject': 'math', 'stage': 'primary',
            'grade_index': '1', 'grade_name': '小学1',
            'term': 'up', 'chapter': 'e2e_test_cp',
            'module': 'e2e_test_mod', 'node_type': 'formula',
            'content': 'e2e_test_ct',
        })
        self.assertEqual(resp.status_code, 200)

        # Find created point
        point = KnowledgePoint.objects.filter(
            chapter='e2e_test_cp', content='e2e_test_ct'
        ).first()
        self.assertIsNotNone(point, 'Expected to find created knowledge point')
        point_id = point.id

        # Delete
        resp = self.client.post(f'/knowledge/point/{point_id}/delete/')
        self.assertEqual(resp.status_code, 200)

        # Verify deleted
        self.assertFalse(
            KnowledgePoint.objects.filter(id=point_id).exists(),
            'Point should be deleted'
        )
