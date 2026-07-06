"""Status constants for the exam parser system."""

# ExamPaper statuses
PAPER_UPLOADED = 'uploaded'
PAPER_CONVERTING = 'converting'
PAPER_CONVERTED = 'converted'
PAPER_PARSING = 'parsing'
PAPER_POSTPROCESSING = 'postprocessing'
PAPER_CROPPING = 'cropping'
PAPER_REVIEWING = 'reviewing'
PAPER_FINISHED = 'finished'
PAPER_FAILED = 'failed'

# ParseTask statuses
TASK_PENDING = 'pending'
TASK_RUNNING = 'running'
TASK_SUCCESS = 'success'
TASK_FAILED = 'failed'
TASK_RETRYING = 'retrying'
TASK_CANCELLED = 'cancelled'

# ExamPage statuses
PAGE_PENDING = 'pending'
PAGE_CONVERTED = 'converted'
PAGE_PARSING = 'parsing'
PAGE_PARSED = 'parsed'
PAGE_PARSE_FAILED = 'parse_failed'
PAGE_NEED_REVIEW = 'need_review'

# ExamQuestion statuses
QUESTION_AUTO_PARSED = 'auto_parsed'
QUESTION_NEED_REVIEW = 'need_review'
QUESTION_CONFIRMED = 'confirmed'
QUESTION_MODIFIED = 'modified'
QUESTION_REJECTED = 'rejected'

# Question types
QT_SINGLE_CHOICE = 'single_choice'
QT_MULTIPLE_CHOICE = 'multiple_choice'
QT_FILL_BLANK = 'fill_blank'
QT_SHORT_ANSWER = 'short_answer'
QT_ESSAY = 'essay'
QT_TRUE_FALSE = 'true_false'
QT_COMPUTATION = 'computation'
QT_PROOF = 'proof'
QT_UNKNOWN = 'unknown'
