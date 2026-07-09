from django.urls import path
from .student_views import (
    student_home, student_mission_detail, student_level_detail, growth_summary, export_pdf, upload_attempt_image
)
from .answer_views import submit_answer, retry_answer, get_mode_a
from .guidance_views import start_guidance, guidance_reply
from .knowledge_views import knowledge_mastery

app_name = 'student'
urlpatterns = [
    path('home', student_home, name='student-home'),
    path('missions/<int:mission_id>', student_mission_detail, name='student-mission'),
    path('levels/<int:level_id>', student_level_detail, name='student-level'),
    path('attempts', submit_answer, name='submit-answer'),
    path('attempts/<int:attempt_id>/retry', retry_answer, name='retry-answer'),
    path('guidance/sessions', start_guidance, name='start-guidance'),
    path('guidance/sessions/<int:session_id>/reply', guidance_reply, name='guidance-reply'),
    path('questions/<int:question_id>/mode-a', get_mode_a, name='mode-a'),
    path('growth', growth_summary, name='growth-summary'),
    path('export/pdf', export_pdf, name='export-pdf'),
    path('attempts/<int:attempt_id>/upload-image', upload_attempt_image, name='upload-attempt-image'),
    path('knowledge-mastery', knowledge_mastery, name='knowledge-mastery'),
]
