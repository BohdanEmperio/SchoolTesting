import pytest

from src.services.classes_service import ClassesService


@pytest.mark.parametrize(
    ("input_name", "expected"),
    [
        ("5б", ("5Б", 5, "Б")),
        (" 11 A ", ("11A", 11, "A")),
    ],
)
def test_parse_class_name(input_name, expected):
    assert ClassesService.parse_class_name(input_name) == expected


@pytest.mark.parametrize("input_name", ["", "0А", "5", "5БВ", "Б5", "100А"])
def test_parse_class_name_rejects_invalid_format(input_name):
    with pytest.raises(ValueError):
        ClassesService.parse_class_name(input_name)


def test_update_class_updates_grade_and_letter():
    class FakeDatabase:
        def update_class(self, *args):
            self.updated_class = args

    database = FakeDatabase()
    service = ClassesService(database, actor_role="psychologist")

    service.update_class("class-id", " 7в ")

    assert database.updated_class == ("class-id", "7В", 7, "В")


class FakeDatabase:
    def __init__(self):
        self.calls = []

    def get_all_classes(self):
        self.calls.append(("get_all_classes",))
        return []

    def add_class(self, title, parallel, letter):
        self.calls.append(("add_class", title, parallel, letter))
        return "new-class-id"

    def update_class(self, *args):
        self.calls.append(("update_class", *args))

    def delete_class(self, class_id):
        self.calls.append(("delete_class", class_id))


def test_psychologist_can_view_create_and_rename_classes():
    database = FakeDatabase()
    service = ClassesService(database, actor_role="psychologist")

    assert service.get_all_classes() == []
    assert service.add_class("5Б", 5, "Б") == "new-class-id"
    service.update_class("class-id", "6В")

    assert [call[0] for call in database.calls] == [
        "get_all_classes",
        "add_class",
        "update_class",
    ]


def test_psychologist_cannot_delete_class():
    database = FakeDatabase()
    service = ClassesService(database, actor_role="psychologist")

    with pytest.raises(PermissionError, match="удаление класса"):
        service.delete_class("class-id")

    assert database.calls == []


@pytest.mark.parametrize(
    "operation",
    [
        lambda service: service.get_all_classes(),
        lambda service: service.add_class("5Б", 5, "Б"),
        lambda service: service.update_class("class-id", "6В"),
        lambda service: service.delete_class("class-id"),
    ],
)
def test_student_cannot_access_class_operations(operation):
    database = FakeDatabase()
    service = ClassesService(database, actor_role="student")

    with pytest.raises(PermissionError):
        operation(service)

    assert database.calls == []


def test_admin_can_delete_class():
    database = FakeDatabase()
    service = ClassesService(database, actor_role="admin")

    service.delete_class("class-id")

    assert database.calls == [("delete_class", "class-id")]
