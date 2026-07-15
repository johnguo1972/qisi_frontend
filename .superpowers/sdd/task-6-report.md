# Task 6 Report: 前端课程列表页 + 课程卡片组件

## Status: DONE

## Commit

`daea05e` feat(front): Task 6 课程列表页 + 课程卡片组件

## Files Created

### 1. `uniapp/src/components/CourseCard.vue`
- **Props**: `course` (id, name, description, subject, grade_level, material_count, question_count)
- **Events**: `click`, `materials`, `practice`, `delete`
- **Features**:
  - Subject-based gradient cover with emoji icon (9 subjects mapped)
  - Grade level badge on cover
  - Course name (truncated with ellipsis), description (truncated)
  - Stats row showing material count and question count
  - Action buttons: "课程资料", "课程练习", delete icon
  - Hover effect (lift + shadow)
  - `@click.stop` on action buttons to prevent card click propagation

### 2. `uniapp/src/pages/teacher/course-list.vue`
- **Layout**: TeacherSidebar (activeItem="course-list") + main content area
- **Features**:
  - Page header with "课程管理" title and "+ 新建课程" button
  - 3-column CSS grid card layout
  - Loading state, empty state with emoji
  - Create dialog with form validation: name (required), subject (picker), grade level (picker), description (textarea, optional)
  - Delete confirmation modal with course name display
  - Navigation fallbacks for future pages (course-detail, course-materials, course-practice) -- shows "开发中" toast if target page not yet registered
  - Auto-reload after create/delete

## Design Decisions

1. **Subject color mapping**: Each of 9 subjects has a unique gradient pair for visual differentiation on card covers
2. **rpx units**: All styles use uniapp's responsive px units consistent with existing pages (TeacherSidebar, bank.vue)
3. **Graceful navigation**: Card action buttons have fail callbacks with toast messages since detail/materials/practice pages are not yet built
4. **Form validation**: Client-side required-field checks before API call, with toast feedback
5. **API integration**: Uses existing `courseApi.list()`, `courseApi.create()`, `courseApi.remove()` from `@/api/courses`

## Concerns

- The `res.data` from `courseApi.list()` is assumed to return an array directly (matching the API signature `get<any[]>('/courses/')`). If the backend wraps data differently, adjustment may be needed.
- The `res.data` from `courseApi.create()` is not used for local insertion -- we reload the full list instead. This is consistent with the existing pattern in bank.vue.
- CourseCard uses emoji for subject icons -- if the project prefers SVG/CSS icons, this should be updated.
