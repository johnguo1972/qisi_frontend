"""Views for knowledge points management."""
import logging
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from apps.knowledge.models import KnowledgePoint

logger = logging.getLogger(__name__)


@require_GET
def tree_data(request):
    """Return hierarchical tree data for the left sidebar.

    Structure: subject -> stage -> grade -> term -> chapters
    """
    values = KnowledgePoint.objects.values(
        'subject', 'stage', 'grade_index', 'grade_name', 'term', 'chapter'
    ).distinct().order_by('subject', 'stage', 'grade_index', 'term', 'chapter')

    tree = {}
    for row in values:
        subj = row['subject']
        stage = row['stage']
        gi = row['grade_index']
        gn = row['grade_name']
        term = row['term']
        chapter = row['chapter']

        stage_key = f'{subj}_{stage}'

        if subj not in tree:
            tree[subj] = {
                'id': subj,
                'label': dict(KnowledgePoint.SUBJECT_CHOICES).get(subj, subj),
                'children': {},
            }
        subj_node = tree[subj]

        if stage not in subj_node['children']:
            subj_node['children'][stage] = {
                'id': stage_key,
                'label': KnowledgePoint.STAGE_LABELS.get(stage, stage),
                'children': {},
            }
        stage_node = subj_node['children'][stage]

        grade_key_full = f'{gi}_{term}'
        if grade_key_full not in stage_node['children']:
            grade_label = KnowledgePoint.GRADE_LABELS.get(gi, gn)
            term_label = KnowledgePoint.TERM_LABELS.get(term, term)
            stage_node['children'][grade_key_full] = {
                'id': f'{stage_key}_{gi}_{term}',
                'label': f'{grade_label}{term_label}',
                'chapters': [],
                'chapter_set': set(),
                '_grade_index': gi,
                '_term': term,
            }
        grade_node = stage_node['children'][grade_key_full]

        if chapter not in grade_node['chapter_set']:
            grade_node['chapter_set'].add(chapter)
            grade_node['chapters'].append({
                'name': chapter,
                'grade_index': gi,
                'term': term,
            })

    result = []
    for subj_node in tree.values():
        children = []
        for stage_node in subj_node['children'].values():
            grade_children = []
            for grade_node in stage_node['children'].values():
                chapter_list = grade_node.pop('chapters')
                grade_node.pop('chapter_set')
                grade_node.pop('_grade_index', None)
                grade_node.pop('_term', None)
                grade_node['chapters'] = chapter_list
                grade_children.append(grade_node)
            stage_node['children'] = grade_children
            children.append(stage_node)
        subj_node['children'] = children
        result.append(subj_node)

    return JsonResponse(result, safe=False, json_dumps_params={'ensure_ascii': False})


def knowledge_list(request):
    """Main knowledge points management page."""
    return render(request, 'knowledge/list.html')
