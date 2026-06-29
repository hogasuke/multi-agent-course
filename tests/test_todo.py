"""TodoItemおよびTodoListのテスト"""
from src.todo import TodoItem, TodoList


class TestTodoItemCategory:
    """TodoItemのカテゴリフィールドテスト"""

    def test_デフォルトカテゴリはNone(self):
        item = TodoItem(id=1, title="タスク")
        assert item.category is None

    def test_カテゴリを指定して作成できる(self):
        item = TodoItem(id=1, title="タスク", category="仕事")
        assert item.category == "仕事"


class TestTodoListAdd:
    """TodoList.add()のカテゴリ対応テスト"""

    def test_カテゴリなしでadd(self):
        tl = TodoList()
        item = tl.add("タスクA")
        assert item.category is None

    def test_カテゴリありでadd(self):
        tl = TodoList()
        item = tl.add("タスクB", category="プライベート")
        assert item.category == "プライベート"


class TestTodoListByCategory:
    """TodoList.list_by_category()のテスト"""

    def test_一致するカテゴリのみ返す(self):
        tl = TodoList()
        tl.add("仕事A", category="仕事")
        tl.add("プライベートA", category="プライベート")
        tl.add("仕事B", category="仕事")
        results = tl.list_by_category("仕事")
        assert len(results) == 2
        assert all(i.category == "仕事" for i in results)

    def test_存在しないカテゴリは空リスト(self):
        tl = TodoList()
        tl.add("タスク", category="仕事")
        assert tl.list_by_category("趣味") == []

    def test_カテゴリなしアイテムは除外(self):
        tl = TodoList()
        tl.add("カテゴリなし")
        tl.add("仕事タスク", category="仕事")
        results = tl.list_by_category("仕事")
        assert len(results) == 1

    def test_空リストから検索(self):
        tl = TodoList()
        assert tl.list_by_category("仕事") == []


class TestTodoListStr:
    """TodoList.__str__()のカテゴリ表示テスト"""

    def test_カテゴリが表示される(self):
        tl = TodoList()
        tl.add("仕事タスク", category="仕事")
        assert "[仕事]" in str(tl)

    def test_カテゴリなしはNone表示しない(self):
        tl = TodoList()
        tl.add("タスクX")
        assert "None" not in str(tl)

    def test_空リスト表示(self):
        tl = TodoList()
        assert str(tl) == "TodoList: (空)"


class TestTodoListRegression:
    """既存機能のリグレッションテスト"""

    def test_complete後にcompletedがTrue(self):
        tl = TodoList()
        item = tl.add("タスク", category="仕事")
        result = tl.complete(item.id)
        assert result is not None
        assert result.completed is True

    def test_delete後にlist_allから消える(self):
        tl = TodoList()
        item = tl.add("削除タスク", category="仕事")
        tl.delete(item.id)
        assert len(tl.list_all()) == 0

    def test_list_allは全件返す(self):
        tl = TodoList()
        tl.add("タスク1", category="仕事")
        tl.add("タスク2")
        assert len(tl.list_all()) == 2
