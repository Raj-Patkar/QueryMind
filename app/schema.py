# Keep this schema synchronized with the actual College_2 PostgreSQL schema.
COLLEGE_SCHEMA_TEXT = (
    "student(ID, name, dept_name, tot_cred); "
    "instructor(ID, name, dept_name, salary); "
    "department(dept_name, building, budget); "
    "course(course_id, title, dept_name, credits); "
    "section(course_id, sec_id, semester, year, building, room_number, time_slot_id); "
    "takes(ID, course_id, sec_id, semester, year, grade); "
    "teaches(ID, course_id, sec_id, semester, year); "
    "classroom(building, room_number, capacity); "
    "advisor(s_ID, i_ID); prereq(course_id, prereq_id); "
    "time_slot(time_slot_id, day, start_hr, start_min, end_hr, end_min)"
)

SCHEMA_COLUMNS = {
    "student": {"id", "name", "dept_name", "tot_cred"},
    "instructor": {"id", "name", "dept_name", "salary"},
    "department": {"dept_name", "building", "budget"},
    "course": {"course_id", "title", "dept_name", "credits"},
    "section": {"course_id", "sec_id", "semester", "year", "building", "room_number", "time_slot_id"},
    "takes": {"id", "course_id", "sec_id", "semester", "year", "grade"},
    "teaches": {"id", "course_id", "sec_id", "semester", "year"},
    "classroom": {"building", "room_number", "capacity"},
    "advisor": {"s_id", "i_id"},
    "prereq": {"course_id", "prereq_id"},
    "time_slot": {"time_slot_id", "day", "start_hr", "start_min", "end_hr", "end_min"},
}
