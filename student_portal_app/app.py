from flask import Flask, render_template, request, redirect, url_for, session, flash
from database import get_db, init_db, seed_data
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'student_portal_secret_key_2026'


# ─── Helpers ───────────────────────────────────────────────

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        if session.get('role') != 'admin':
            flash('Доступ запрещён. Требуются права администратора.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return wrapper


def get_current_user():
    if 'user_id' not in session:
        return None
    db = get_db()
    user = db.execute(
        "SELECT u.*, g.name as group_name FROM users u LEFT JOIN groups g ON u.group_id = g.id WHERE u.id = ?",
        (session['user_id'],)
    ).fetchone()
    db.close()
    return user


ROLE_LABELS = {
    'student': 'Студент',
    'teacher': 'Преподаватель',
    'admin': 'Администратор'
}


@app.context_processor
def inject_globals():
    user = get_current_user()
    pending_count = 0
    if user and user['role'] == 'admin':
        db = get_db()
        pending_count = db.execute(
            "SELECT COUNT(*) FROM grade_edit_requests WHERE status = 'pending'"
        ).fetchone()[0]
        db.close()
    return {
        'current_user': user,
        'role_labels': ROLE_LABELS,
        'pending_requests_count': pending_count
    }


# ─── Auth ──────────────────────────────────────────────────

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        db = get_db()
        user = db.execute(
            "SELECT * FROM users WHERE username = ? AND password = ?",
            (username, password)
        ).fetchone()
        db.close()

        if user:
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = user['role']
            flash(f'Добро пожаловать, {user["full_name"]}!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Неверный логин или пароль.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('dashboard'))

    db = get_db()
    groups = db.execute("SELECT * FROM groups ORDER BY name").fetchall()

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        group_id = request.form.get('group_id')
        role = 'student'

        if not username or not password or not full_name:
            flash('Заполните все обязательные поля.', 'error')
        else:
            try:
                db.execute(
                    "INSERT INTO users (username, password, full_name, role, group_id, email) VALUES (?,?,?,?,?,?)",
                    (username, password, full_name, role, group_id or None, email or None)
                )
                db.commit()

                user = db.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['full_name'] = user['full_name']
                session['role'] = user['role']

                flash('Регистрация прошла успешно!', 'success')
                db.close()
                return redirect(url_for('dashboard'))
            except Exception as e:
                flash(f'Ошибка регистрации: пользователь с таким логином уже существует.', 'error')

    db.close()
    return render_template('register.html', groups=groups)


@app.route('/logout')
def logout():
    session.clear()
    flash('Вы вышли из системы.', 'info')
    return redirect(url_for('login'))


# ─── Dashboard ─────────────────────────────────────────────

@app.route('/')
@login_required
def dashboard():
    db = get_db()
    user = get_current_user()

    stats = {}
    if session['role'] == 'student':
        stats['courses_count'] = db.execute(
            "SELECT COUNT(*) FROM enrollments WHERE student_id = ?", (session['user_id'],)
        ).fetchone()[0]

        avg = db.execute(
            "SELECT AVG(grade) FROM grades WHERE student_id = ?", (session['user_id'],)
        ).fetchone()[0]
        stats['avg_grade'] = round(avg, 2) if avg else 0

        stats['total_grades'] = db.execute(
            "SELECT COUNT(*) FROM grades WHERE student_id = ?", (session['user_id'],)
        ).fetchone()[0]

        stats['recent_grades'] = db.execute(
            "SELECT g.*, c.name as course_name FROM grades g "
            "JOIN courses c ON g.course_id = c.id "
            "WHERE g.student_id = ? ORDER BY g.date DESC LIMIT 5",
            (session['user_id'],)
        ).fetchall()

    elif session['role'] == 'teacher':
        stats['courses_count'] = db.execute(
            "SELECT COUNT(*) FROM courses WHERE teacher_id = ?", (session['user_id'],)
        ).fetchone()[0]
        stats['students_count'] = db.execute(
            "SELECT COUNT(DISTINCT e.student_id) FROM enrollments e "
            "JOIN courses c ON e.course_id = c.id WHERE c.teacher_id = ?",
            (session['user_id'],)
        ).fetchone()[0]
        stats['grades_given'] = db.execute(
            "SELECT COUNT(*) FROM grades g "
            "JOIN courses c ON g.course_id = c.id WHERE c.teacher_id = ?",
            (session['user_id'],)
        ).fetchone()[0]

    elif session['role'] == 'admin':
        stats['users_count'] = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        stats['courses_count'] = db.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        stats['groups_count'] = db.execute("SELECT COUNT(*) FROM groups").fetchone()[0]
        stats['enrollments_count'] = db.execute("SELECT COUNT(*) FROM enrollments").fetchone()[0]

    db.close()
    return render_template('dashboard.html', user=user, stats=stats)


# ─── Courses ───────────────────────────────────────────────

@app.route('/courses')
@login_required
def courses():
    db = get_db()
    my_only = request.args.get('my')

    base_query = (
        "SELECT c.*, u.full_name as teacher_name, g.name as group_name "
        "FROM courses c "
        "LEFT JOIN users u ON c.teacher_id = u.id "
        "LEFT JOIN groups g ON c.group_id = g.id "
    )

    if my_only and session['role'] == 'teacher':
        all_courses = db.execute(
            base_query + "WHERE c.teacher_id = ? ORDER BY c.name",
            (session['user_id'],)
        ).fetchall()
    elif my_only and session['role'] == 'student':
        all_courses = db.execute(
            base_query +
            "JOIN enrollments e ON c.id = e.course_id "
            "WHERE e.student_id = ? ORDER BY c.name",
            (session['user_id'],)
        ).fetchall()
    else:
        all_courses = db.execute(base_query + "ORDER BY c.name").fetchall()

    enrolled_ids = set()
    if session['role'] == 'student':
        rows = db.execute(
            "SELECT course_id FROM enrollments WHERE student_id = ?", (session['user_id'],)
        ).fetchall()
        enrolled_ids = {r['course_id'] for r in rows}

    enrollment_counts = {}
    for c in all_courses:
        cnt = db.execute(
            "SELECT COUNT(*) FROM enrollments WHERE course_id = ?", (c['id'],)
        ).fetchone()[0]
        enrollment_counts[c['id']] = cnt

    db.close()
    return render_template('courses.html', courses=all_courses,
                           enrolled_ids=enrolled_ids, enrollment_counts=enrollment_counts)


@app.route('/courses/enroll/<int:course_id>', methods=['POST'])
@login_required
def enroll(course_id):
    if session['role'] != 'student':
        flash('Только студенты могут записываться на курсы.', 'error')
        return redirect(url_for('courses'))

    db = get_db()
    try:
        db.execute(
            "INSERT INTO enrollments (student_id, course_id) VALUES (?,?)",
            (session['user_id'], course_id)
        )
        db.commit()
        course = db.execute("SELECT name FROM courses WHERE id = ?", (course_id,)).fetchone()
        flash(f'Вы записаны на курс «{course["name"]}».', 'success')
    except Exception:
        flash('Вы уже записаны на этот курс.', 'warning')
    db.close()
    return redirect(url_for('courses'))


@app.route('/courses/unenroll/<int:course_id>', methods=['POST'])
@login_required
def unenroll(course_id):
    db = get_db()
    db.execute(
        "DELETE FROM enrollments WHERE student_id = ? AND course_id = ?",
        (session['user_id'], course_id)
    )
    db.commit()
    course = db.execute("SELECT name FROM courses WHERE id = ?", (course_id,)).fetchone()
    flash(f'Вы отписались от курса «{course["name"]}».', 'success')
    db.close()
    return redirect(url_for('courses'))


# ─── Course Journal ────────────────────────────────────────

@app.route('/courses/<int:course_id>/journal')
@login_required
def course_journal(course_id):
    db = get_db()
    course = db.execute(
        "SELECT c.*, u.full_name as teacher_name, g.name as group_name "
        "FROM courses c "
        "LEFT JOIN users u ON c.teacher_id = u.id "
        "LEFT JOIN groups g ON c.group_id = g.id "
        "WHERE c.id = ?", (course_id,)
    ).fetchone()

    if not course:
        flash('Курс не найден.', 'error')
        db.close()
        return redirect(url_for('courses'))

    # Права: кто что может
    role = session['role']
    uid = session['user_id']
    is_owner = (role == 'teacher' and course['teacher_id'] == uid)
    can_add_grades = (role == 'admin' or is_owner)
    can_direct_edit = (role == 'admin')
    can_request_edit = is_owner  # учитель курса может запросить изменение

    # Записанные студенты (видят все)
    students = db.execute(
        "SELECT u.id, u.full_name, gr.name as group_name "
        "FROM users u "
        "JOIN enrollments e ON u.id = e.student_id "
        "LEFT JOIN groups gr ON u.group_id = gr.id "
        "WHERE e.course_id = ? ORDER BY gr.name, u.full_name",
        (course_id,)
    ).fetchall()

    # Все оценки по курсу
    all_grades = db.execute(
        "SELECT g.*, u.full_name as student_name "
        "FROM grades g "
        "JOIN users u ON g.student_id = u.id "
        "WHERE g.course_id = ? ORDER BY u.full_name, g.date DESC",
        (course_id,)
    ).fetchall()

    # Группировка по студентам
    grades_by_student = {}
    for g in all_grades:
        sid = g['student_id']
        if sid not in grades_by_student:
            grades_by_student[sid] = []
        grades_by_student[sid].append(g)

    avgs = {}
    for sid, gs in grades_by_student.items():
        vals = [g['grade'] for g in gs]
        avgs[sid] = round(sum(vals) / len(vals), 2) if vals else None

    # ID оценок с активным pending-запросом
    pending_rows = db.execute(
        "SELECT grade_id FROM grade_edit_requests WHERE course_id = ? AND status = 'pending'",
        (course_id,)
    ).fetchall()
    pending_grade_ids = {r['grade_id'] for r in pending_rows}

    db.close()
    return render_template('course_journal.html',
                           course=course,
                           students=students,
                           grades_by_student=grades_by_student,
                           avgs=avgs,
                           can_add_grades=can_add_grades,
                           can_direct_edit=can_direct_edit,
                           can_request_edit=can_request_edit,
                           pending_grade_ids=pending_grade_ids)


@app.route('/courses/<int:course_id>/grades/add', methods=['POST'])
@login_required
def add_grade_course(course_id):
    if session['role'] == 'student':
        flash('Нет доступа.', 'error')
        return redirect(url_for('course_journal', course_id=course_id))

    db = get_db()
    course = db.execute("SELECT * FROM courses WHERE id = ?", (course_id,)).fetchone()
    if not course or (session['role'] == 'teacher' and course['teacher_id'] != session['user_id']):
        flash('Нет доступа.', 'error')
        db.close()
        return redirect(url_for('courses'))

    student_id = request.form.get('student_id')
    grade = request.form.get('grade')
    date = request.form.get('date', '2026-06-11')
    comment = request.form.get('comment', '').strip()

    if not student_id or not grade:
        flash('Укажите студента и оценку.', 'error')
    else:
        db.execute(
            "INSERT INTO grades (student_id, course_id, grade, date, comment) VALUES (?,?,?,?,?)",
            (int(student_id), course_id, int(grade), date, comment)
        )
        db.commit()
        flash('Оценка выставлена.', 'success')

    db.close()
    return redirect(url_for('course_journal', course_id=course_id))


@app.route('/grades/<int:grade_id>/edit', methods=['POST'])
@admin_required
def edit_grade(grade_id):
    """Прямое редактирование — только для администратора."""
    db = get_db()
    row = db.execute(
        "SELECT g.*, c.id as cid FROM grades g "
        "JOIN courses c ON g.course_id = c.id WHERE g.id = ?",
        (grade_id,)
    ).fetchone()

    if not row:
        flash('Оценка не найдена.', 'error')
        db.close()
        return redirect(url_for('admin'))

    new_grade = request.form.get('grade')
    new_comment = request.form.get('comment', '').strip()
    course_id = row['cid']

    if not new_comment:
        flash('Укажите комментарий.', 'error')
    else:
        db.execute(
            "UPDATE grades SET grade = ?, comment = ? WHERE id = ?",
            (int(new_grade), new_comment, grade_id)
        )
        db.commit()
        flash('Оценка обновлена администратором.', 'success')

    db.close()
    return redirect(url_for('course_journal', course_id=course_id))


@app.route('/grades/<int:grade_id>/request-edit', methods=['POST'])
@login_required
def request_grade_edit(grade_id):
    """Учитель запрашивает изменение существующей оценки."""
    if session['role'] != 'teacher':
        flash('Только преподаватели используют систему запросов.', 'error')
        return redirect(url_for('courses'))

    db = get_db()
    row = db.execute(
        "SELECT g.*, c.teacher_id, c.id as cid FROM grades g "
        "JOIN courses c ON g.course_id = c.id WHERE g.id = ?",
        (grade_id,)
    ).fetchone()

    if not row or row['teacher_id'] != session['user_id']:
        flash('Нет доступа к этой оценке.', 'error')
        db.close()
        return redirect(url_for('courses'))

    # Проверяем нет ли уже активного запроса
    existing = db.execute(
        "SELECT id FROM grade_edit_requests WHERE grade_id = ? AND status = 'pending'",
        (grade_id,)
    ).fetchone()
    if existing:
        flash('Запрос на изменение уже отправлен и ожидает рассмотрения.', 'warning')
        db.close()
        return redirect(url_for('course_journal', course_id=row['cid']))

    requested_grade = request.form.get('grade')
    requested_comment = request.form.get('comment', '').strip()
    reason = request.form.get('reason', '').strip()
    course_id = row['cid']

    if not reason:
        flash('Укажите причину изменения оценки.', 'error')
        db.close()
        return redirect(url_for('course_journal', course_id=course_id))

    db.execute(
        "INSERT INTO grade_edit_requests "
        "(grade_id, course_id, teacher_id, old_grade, requested_grade, requested_comment, reason) "
        "VALUES (?,?,?,?,?,?,?)",
        (grade_id, course_id, session['user_id'],
         row['grade'], int(requested_grade), requested_comment, reason)
    )
    db.commit()
    db.close()
    flash('Запрос на изменение оценки отправлен администратору.', 'success')
    return redirect(url_for('course_journal', course_id=course_id))


@app.route('/grades/<int:grade_id>/delete', methods=['POST'])
@admin_required
def delete_grade(grade_id):
    """Удаление оценки — только администратор."""
    db = get_db()
    row = db.execute(
        "SELECT g.*, c.id as cid FROM grades g "
        "JOIN courses c ON g.course_id = c.id WHERE g.id = ?",
        (grade_id,)
    ).fetchone()

    if not row:
        flash('Оценка не найдена.', 'error')
        db.close()
        return redirect(url_for('admin'))

    course_id = row['cid']
    db.execute("DELETE FROM grades WHERE id = ?", (grade_id,))
    db.commit()
    db.close()
    flash('Оценка удалена.', 'success')
    return redirect(url_for('course_journal', course_id=course_id))


@app.route('/admin/grade-requests/<int:req_id>/approve', methods=['POST'])
@admin_required
def approve_grade_request(req_id):
    db = get_db()
    req = db.execute(
        "SELECT r.*, u.full_name as teacher_name "
        "FROM grade_edit_requests r "
        "JOIN users u ON r.teacher_id = u.id WHERE r.id = ?",
        (req_id,)
    ).fetchone()
    if not req:
        flash('Запрос не найден.', 'error')
        db.close()
        return redirect(url_for('admin'))

    admin_note = request.form.get('admin_note', '').strip()
    db.execute(
        "UPDATE grades SET grade = ?, comment = ? WHERE id = ?",
        (req['requested_grade'],
         req['requested_comment'] or '',
         req['grade_id'])
    )
    db.execute(
        "UPDATE grade_edit_requests SET status = 'approved', admin_note = ? WHERE id = ?",
        (admin_note, req_id)
    )
    db.commit()
    db.close()
    flash(f'Запрос одобрен. Оценка обновлена.', 'success')
    return redirect(url_for('admin') + '#section-requests')


@app.route('/admin/grade-requests/<int:req_id>/reject', methods=['POST'])
@admin_required
def reject_grade_request(req_id):
    db = get_db()
    req = db.execute(
        "SELECT * FROM grade_edit_requests WHERE id = ?", (req_id,)
    ).fetchone()
    if not req:
        flash('Запрос не найден.', 'error')
        db.close()
        return redirect(url_for('admin'))

    admin_note = request.form.get('admin_note', '').strip()
    db.execute(
        "UPDATE grade_edit_requests SET status = 'rejected', admin_note = ? WHERE id = ?",
        (admin_note, req_id)
    )
    db.commit()
    db.close()
    flash('Запрос отклонён.', 'info')
    return redirect(url_for('admin') + '#section-requests')



@app.route('/gradebook')
@login_required
def gradebook():
    db = get_db()

    # Фильтры из query-строки (для учителей и админов)
    filter_group_id = request.args.get('group_id', type=int)
    filter_course_id = request.args.get('course_id', type=int)

    # Все группы и курсы для фильтров
    all_groups = db.execute("SELECT * FROM groups ORDER BY name").fetchall()

    avg = None
    course_avgs = []

    if session['role'] == 'student':
        grades = db.execute(
            "SELECT g.*, c.name as course_name FROM grades g "
            "JOIN courses c ON g.course_id = c.id "
            "WHERE g.student_id = ? ORDER BY g.date DESC",
            (session['user_id'],)
        ).fetchall()
        avg = db.execute(
            "SELECT AVG(grade) FROM grades WHERE student_id = ?",
            (session['user_id'],)
        ).fetchone()[0]
        course_avgs = db.execute(
            "SELECT c.name, AVG(g.grade) as avg_grade, COUNT(g.id) as cnt "
            "FROM grades g JOIN courses c ON g.course_id = c.id "
            "WHERE g.student_id = ? GROUP BY c.id ORDER BY c.name",
            (session['user_id'],)
        ).fetchall()
        all_groups = []

    else:
        # Строим WHERE динамически
        where_parts = []
        params = []

        if session['role'] == 'teacher':
            where_parts.append("c.teacher_id = ?")
            params.append(session['user_id'])

        if filter_group_id:
            where_parts.append("u.group_id = ?")
            params.append(filter_group_id)

        if filter_course_id:
            where_parts.append("g.course_id = ?")
            params.append(filter_course_id)

        where_sql = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""

        grades = db.execute(
            "SELECT g.*, c.name as course_name, u.full_name as student_name, "
            "gr.name as group_name "
            "FROM grades g "
            "JOIN courses c ON g.course_id = c.id "
            "JOIN users u ON g.student_id = u.id "
            "LEFT JOIN groups gr ON u.group_id = gr.id "
            f"{where_sql} ORDER BY gr.name, u.full_name, g.date DESC",
            params
        ).fetchall()

        # Курсы для фильтра
        if session['role'] == 'teacher':
            all_courses_filter = db.execute(
                "SELECT * FROM courses WHERE teacher_id = ? ORDER BY name",
                (session['user_id'],)
            ).fetchall()
        else:
            all_courses_filter = db.execute(
                "SELECT * FROM courses ORDER BY name"
            ).fetchall()

    db.close()
    return render_template('gradebook.html', grades=grades,
                           avg_grade=round(avg, 2) if avg else None,
                           course_avgs=course_avgs,
                           all_groups=all_groups,
                           all_courses_filter=locals().get('all_courses_filter', []),
                           filter_group_id=filter_group_id,
                           filter_course_id=filter_course_id)


# ─── Reports ──────────────────────────────────────────────

def _get_report_context(db):
    """Вспомогательный контекст для страницы отчётов."""
    students_list = db.execute(
        "SELECT u.id, u.full_name, g.name as group_name FROM users u "
        "LEFT JOIN groups g ON u.group_id = g.id "
        "WHERE u.role = 'student' ORDER BY g.name, u.full_name"
    ).fetchall()
    groups_list = db.execute("SELECT * FROM groups ORDER BY name").fetchall()
    return students_list, groups_list


@app.route('/reports')
@login_required
def reports():
    db = get_db()
    # GET-параметр: сразу открыть нужный тип
    quick_type = request.args.get('type')
    students_list, groups_list = _get_report_context(db)
    db.close()
    return render_template('reports.html', report=None,
                           students_list=students_list,
                           groups_list=groups_list,
                           quick_type=quick_type)


@app.route('/reports/generate', methods=['POST'])
@login_required
def generate_report():
    report_type = request.form.get('report_type', 'academic')
    db = get_db()
    students_list, groups_list = _get_report_context(db)

    report = {'type': report_type}

    if report_type == 'academic':
        if session['role'] == 'student':
            target_id = session['user_id']
        else:
            target_id = request.form.get('student_id')
            if not target_id:
                flash('Выберите студента для формирования справки.', 'error')
                db.close()
                return render_template('reports.html', report=None,
                                       students_list=students_list,
                                       groups_list=groups_list,
                                       quick_type='academic')

        student = db.execute(
            "SELECT u.*, g.name as group_name FROM users u "
            "LEFT JOIN groups g ON u.group_id = g.id WHERE u.id = ?",
            (target_id,)
        ).fetchone()

        courses_data = db.execute(
            "SELECT c.name, AVG(gr.grade) as avg_grade, COUNT(gr.id) as grades_count "
            "FROM enrollments e "
            "JOIN courses c ON e.course_id = c.id "
            "LEFT JOIN grades gr ON gr.student_id = e.student_id AND gr.course_id = c.id "
            "WHERE e.student_id = ? GROUP BY c.id ORDER BY c.name",
            (target_id,)
        ).fetchall()

        overall_avg = db.execute(
            "SELECT AVG(grade) FROM grades WHERE student_id = ?", (target_id,)
        ).fetchone()[0]

        report['student'] = student
        report['courses'] = courses_data
        report['overall_avg'] = round(overall_avg, 2) if overall_avg else 0

    elif report_type == 'rating':
        filter_group = request.form.get('filter_group_id')
        params = []
        group_where = ""
        if filter_group:
            group_where = "AND u.group_id = ?"
            params.append(filter_group)

        students = db.execute(
            "SELECT u.full_name, g.name as group_name, "
            "AVG(gr.grade) as avg_grade, COUNT(gr.id) as grades_count "
            "FROM users u "
            "LEFT JOIN groups g ON u.group_id = g.id "
            "LEFT JOIN grades gr ON gr.student_id = u.id "
            f"WHERE u.role = 'student' {group_where} "
            "GROUP BY u.id ORDER BY avg_grade DESC",
            params
        ).fetchall()
        report['students'] = students
        report['filter_group_id'] = filter_group

    db.close()
    return render_template('reports.html', report=report,
                           students_list=students_list,
                           groups_list=groups_list,
                           quick_type=report_type)


# ─── Admin ────────────────────────────────────────────────

@app.route('/admin')
@admin_required
def admin():
    db = get_db()
    groups = db.execute("SELECT * FROM groups ORDER BY name").fetchall()
    courses_list = db.execute(
        "SELECT c.*, u.full_name as teacher_name FROM courses c "
        "LEFT JOIN users u ON c.teacher_id = u.id ORDER BY c.name"
    ).fetchall()
    students = db.execute(
        "SELECT u.*, g.name as group_name FROM users u "
        "LEFT JOIN groups g ON u.group_id = g.id "
        "WHERE u.role = 'student' ORDER BY u.full_name"
    ).fetchall()
    teachers = db.execute(
        "SELECT * FROM users WHERE role = 'teacher' ORDER BY full_name"
    ).fetchall()
    all_users = db.execute(
        "SELECT u.*, g.name as group_name FROM users u "
        "LEFT JOIN groups g ON u.group_id = g.id ORDER BY u.role, u.full_name"
    ).fetchall()
    
    pending_requests = db.execute(
        "SELECT r.*, c.name as course_name, u.full_name as teacher_name, "
        "stud.full_name as student_name "
        "FROM grade_edit_requests r "
        "JOIN courses c ON r.course_id = c.id "
        "JOIN users u ON r.teacher_id = u.id "
        "JOIN grades g ON r.grade_id = g.id "
        "JOIN users stud ON g.student_id = stud.id "
        "WHERE r.status = 'pending' "
        "ORDER BY r.created_at ASC"
    ).fetchall()
    
    db.close()
    return render_template('admin.html', groups=groups, courses=courses_list,
                           students=students, teachers=teachers, all_users=all_users,
                           pending_requests=pending_requests)


@app.route('/admin/groups', methods=['POST'])
@admin_required
def add_group():
    name = request.form.get('group_name', '').strip()
    if not name:
        flash('Введите название группы.', 'error')
    else:
        db = get_db()
        try:
            db.execute("INSERT INTO groups (name) VALUES (?)", (name,))
            db.commit()
            flash(f'Группа «{name}» создана.', 'success')
        except Exception:
            flash('Группа с таким названием уже существует.', 'error')
        db.close()
    return redirect(url_for('admin'))


@app.route('/admin/courses', methods=['POST'])
@admin_required
def add_course():
    name = request.form.get('course_name', '').strip()
    description = request.form.get('course_desc', '').strip()
    teacher_id = request.form.get('teacher_id')

    if not name:
        flash('Введите название курса.', 'error')
    else:
        db = get_db()
        db.execute(
            "INSERT INTO courses (name, description, teacher_id) VALUES (?,?,?)",
            (name, description, teacher_id or None)
        )
        db.commit()
        flash(f'Курс «{name}» создан.', 'success')
        db.close()
    return redirect(url_for('admin'))


@app.route('/admin/grades', methods=['POST'])
@admin_required
def add_grade():
    student_id = request.form.get('student_id')
    course_id = request.form.get('course_id')
    grade = request.form.get('grade')
    date = request.form.get('date', '2026-01-01')
    comment = request.form.get('comment', '').strip()

    if not student_id or not course_id or not grade:
        flash('Заполните все обязательные поля.', 'error')
    else:
        db = get_db()
        db.execute(
            "INSERT INTO grades (student_id, course_id, grade, date, comment) VALUES (?,?,?,?,?)",
            (student_id, course_id, int(grade), date, comment)
        )
        db.commit()
        flash('Оценка выставлена.', 'success')
        db.close()
    return redirect(url_for('admin'))


@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@admin_required
def delete_user(user_id):
    if user_id == session['user_id']:
        flash('Нельзя удалить собственную учётную запись.', 'error')
    else:
        db = get_db()
        user = db.execute("SELECT full_name FROM users WHERE id = ?", (user_id,)).fetchone()
        db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        db.commit()
        flash(f'Пользователь «{user["full_name"]}» удалён.', 'success')
        db.close()
    return redirect(url_for('admin'))


@app.route('/admin/courses/delete/<int:course_id>', methods=['POST'])
@admin_required
def delete_course(course_id):
    db = get_db()
    course = db.execute("SELECT name FROM courses WHERE id = ?", (course_id,)).fetchone()
    db.execute("DELETE FROM courses WHERE id = ?", (course_id,))
    db.commit()
    flash(f'Курс «{course["name"]}» удалён.', 'success')
    db.close()
    return redirect(url_for('admin'))


@app.route('/admin/groups/delete/<int:group_id>', methods=['POST'])
@admin_required
def delete_group(group_id):
    db = get_db()
    group = db.execute("SELECT name FROM groups WHERE id = ?", (group_id,)).fetchone()
    db.execute("DELETE FROM groups WHERE id = ?", (group_id,))
    db.commit()
    flash(f'Группа «{group["name"]}» удалена.', 'success')
    db.close()
    return redirect(url_for('admin'))


# ─── Init & Run ───────────────────────────────────────────

if __name__ == '__main__':
    init_db()
    seed_data()
    app.run(debug=True, port=5000)
