
import csv
from pathlib import Path
from typing import List, Optional

from sqlalchemy import Integer, String, create_engine, func, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column


CSV_PATH = Path(__file__).with_name("students.csv")
DB_URL = f"sqlite:///{Path(__file__).with_name('students.db')}"


class Base(DeclarativeBase):
    pass


class Student(Base):
    """Одна строка таблицы: оценка студента по курсу"""

    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_name: Mapped[str] = mapped_column(String(100))
    first_name: Mapped[str] = mapped_column(String(100))
    faculty: Mapped[str] = mapped_column(String(50), index=True)
    course: Mapped[str] = mapped_column(String(100), index=True)
    grade: Mapped[int] = mapped_column(Integer)

    def __repr__(self) -> str:
        return (
            f"Student({self.last_name} {self.first_name}, {self.faculty}, "
            f"{self.course}, {self.grade})"
        )


class StudentRepository:
    """INSERT и SELECT для модели Student"""

    def __init__(self, db_url: str = DB_URL) -> None:
        self.engine = create_engine(db_url)
        Base.metadata.create_all(self.engine)

    # --- INSERT ---

    def insert(
        self,
        last_name: str,
        first_name: str,
        faculty: str,
        course: str,
        grade: int,
    ) -> Student:
        student = Student(
            last_name=last_name,
            first_name=first_name,
            faculty=faculty,
            course=course,
            grade=grade,
        )
        with Session(self.engine, expire_on_commit=False) as session:
            session.add(student)
            session.commit()
        return student

    def insert_many(self, students: List[Student]) -> None:
        with Session(self.engine) as session:
            session.add_all(students)
            session.commit()

    def load_from_csv(self, path: Path = CSV_PATH) -> int:
        """Заполняет таблицу данными из CSV (старые записи удаляются)"""
        with open(path, encoding="utf-8") as f:
            rows = [
                Student(
                    last_name=row["Фамилия"],
                    first_name=row["Имя"],
                    faculty=row["Факультет"],
                    course=row["Курс"],
                    grade=int(row["Оценка"]),
                )
                for row in csv.DictReader(f)
            ]
        Base.metadata.drop_all(self.engine)
        Base.metadata.create_all(self.engine)
        self.insert_many(rows)
        return len(rows)

    # --- SELECT ---

    def select_all(self) -> List[Student]:
        with Session(self.engine) as session:
            return list(session.scalars(select(Student)))

    def get_students_by_faculty(self, faculty: str) -> List[Student]:
        stmt = (
            select(Student)
            .where(Student.faculty == faculty)
            .order_by(Student.last_name, Student.first_name)
        )
        with Session(self.engine) as session:
            return list(session.scalars(stmt))

    def get_unique_courses(self) -> List[str]:
        stmt = select(Student.course).distinct().order_by(Student.course)
        with Session(self.engine) as session:
            return list(session.scalars(stmt))

    def get_low_grade_students(
        self, course: str, threshold: int = 30
    ) -> List[Student]:
        """Студенты выбранного курса с оценкой ниже threshold баллов"""
        stmt = (
            select(Student)
            .where(Student.course == course, Student.grade < threshold)
            .order_by(Student.grade)
        )
        with Session(self.engine) as session:
            return list(session.scalars(stmt))

    def get_average_grade_by_faculty(self, faculty: str) -> Optional[float]:
        stmt = select(func.avg(Student.grade)).where(Student.faculty == faculty)
        with Session(self.engine) as session:
            avg = session.scalar(stmt)
        return round(avg, 2) if avg is not None else None


if __name__ == "__main__":
    repo = StudentRepository()
    print(f"Загружено записей: {repo.load_from_csv()}")

    print("\nСтуденты факультета ФПМИ:")
    for s in repo.get_students_by_faculty("ФПМИ"):
        print(" ", s)

    print("\nУникальные курсы:", repo.get_unique_courses())

    print("\nМат. Анализ, оценка ниже 30:")
    for s in repo.get_low_grade_students("Мат. Анализ"):
        print(" ", s)

    print("\nСредний балл по факультету ФПМИ:",
          repo.get_average_grade_by_faculty("ФПМИ"))
