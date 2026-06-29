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


class TestTodoItemDefaults:
    """TodoItemのデフォルト値テスト"""

    def test_completedのデフォルトはFalse(self):
        item = TodoItem(id=1, title="タスク")
        assert item.completed is False

    def test_idとtitleが正しくセットされる(self):
        item = TodoItem(id=42, title="テストタスク")
        assert item.id == 42
        assert item.title == "テストタスク"


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

    def test_空文字タイトルでも追加できる(self):
        tl = TodoList()
        item = tl.add("")
        assert item.title == ""
        assert item.id == 1


class TestTodoListAddId:
    """TodoList.add()のID自動採番テスト"""

    def test_最初のIDは1(self):
        tl = TodoList()
        item = tl.add("タスク")
        assert item.id == 1

    def test_IDが連番になる(self):
        tl = TodoList()
        item1 = tl.add("タスク1")
        item2 = tl.add("タスク2")
        item3 = tl.add("タスク3")
        assert item1.id == 1
        assert item2.id == 2
        assert item3.id == 3

    def test_削除後もIDがリセットされない(self):
        tl = TodoList()
        item1 = tl.add("タスク1")
        tl.delete(item1.id)
        item2 = tl.add("タスク2")
        assert item2.id == 2


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

    def test_1件のカテゴリから1件返す(self):
        tl = TodoList()
        tl.add("仕事タスク", category="仕事")
        results = tl.list_by_category("仕事")
        assert len(results) == 1
        assert results[0].category == "仕事"


class TestTodoListListAll:
    """TodoList.list_all()のテスト"""

    def test_空リストは空リストを返す(self):
        tl = TodoList()
        assert tl.list_all() == []

    def test_1件追加後に1件返る(self):
        tl = TodoList()
        tl.add("タスク")
        assert len(tl.list_all()) == 1

    def test_複数件追加後に全件返す(self):
        tl = TodoList()
        tl.add("タスク1")
        tl.add("タスク2")
        tl.add("タスク3")
        assert len(tl.list_all()) == 3

    def test_返り値はリストのコピー(self):
        tl = TodoList()
        tl.add("タスク")
        result = tl.list_all()
        result.clear()
        assert len(tl.list_all()) == 1

    def test_削除後は削除アイテムが含まれない(self):
        tl = TodoList()
        item = tl.add("削除タスク")
        tl.delete(item.id)
        assert item not in tl.list_all()


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

    def test_完了済みアイテムにチェックマークが表示される(self):
        tl = TodoList()
        item = tl.add("タスク")
        tl.complete(item.id)
        assert "✔︎" in str(tl)

    def test_件数が正しく表示される(self):
        tl = TodoList()
        tl.add("タスク1")
        tl.add("タスク2")
        assert "2件" in str(tl)


class TestTodoListDelete:
    """TodoList.delete()のテスト"""

    def test_削除は削除したアイテムを返す(self):
        tl = TodoList()
        item = tl.add("削除タスク")
        result = tl.delete(item.id)
        assert result is not None
        assert result.id == item.id

    def test_存在しないIDはNoneを返す(self):
        tl = TodoList()
        assert tl.delete(999) is None

    def test_中間アイテムを削除しても残りが保持される(self):
        tl = TodoList()
        item1 = tl.add("タスク1")
        item2 = tl.add("タスク2")
        item3 = tl.add("タスク3")
        tl.delete(item2.id)
        remaining = tl.list_all()
        assert len(remaining) == 2
        assert any(i.id == item1.id for i in remaining)
        assert any(i.id == item3.id for i in remaining)

    def test_空リストからdeleteしてもNoneを返す(self):
        tl = TodoList()
        assert tl.delete(1) is None


class TestTodoCore:
    """正常系3ケース・異常系2ケースの基本動作テスト"""

    # 正常系
    def test_正常系_タスク追加後にlist_allに含まれる(self):
        tl = TodoList()
        item = tl.add("買い物", category="プライベート")
        all_items = tl.list_all()
        assert len(all_items) == 1
        assert all_items[0].title == "買い物"
        assert all_items[0].category == "プライベート"

    def test_正常系_完了操作後にcompletedがTrueになる(self):
        tl = TodoList()
        item = tl.add("報告書作成")
        result = tl.complete(item.id)
        assert result is not None
        assert result.completed is True

    def test_正常系_削除後にlist_allから消える(self):
        tl = TodoList()
        item = tl.add("不要タスク")
        deleted = tl.delete(item.id)
        assert deleted is not None
        assert item not in tl.list_all()

    # 異常系
    def test_異常系_存在しないIDのcompleteはNoneを返す(self):
        tl = TodoList()
        tl.add("タスク")
        result = tl.complete(9999)
        assert result is None

    def test_異常系_存在しないIDのdeleteはNoneを返す(self):
        tl = TodoList()
        tl.add("タスク")
        result = tl.delete(9999)
        assert result is None


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

    def test_存在しないIDのcompleteはNoneを返す(self):
        tl = TodoList()
        assert tl.complete(999) is None

    def test_完了済みアイテムを再度completeしてもTrueのまま(self):
        tl = TodoList()
        item = tl.add("タスク")
        tl.complete(item.id)
        tl.complete(item.id)
        assert item.completed is True

    def test_complete後に戻り値がそのアイテム(self):
        tl = TodoList()
        item = tl.add("タスク")
        result = tl.complete(item.id)
        assert result is item

    def test_複数中の特定IDのみ完了状態が変わる(self):
        tl = TodoList()
        item1 = tl.add("タスク1")
        item2 = tl.add("タスク2")
        tl.complete(item1.id)
        assert item1.completed is True
        assert item2.completed is False
