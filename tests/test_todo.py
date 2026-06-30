"""
src/todo.py の TodoList クラスに対するテスト。
各メソッドについて正常系・異常系を網羅する。
"""
import json
import pytest
from src.todo import TodoList


# ─────────────────────────────────────────────
# フィクスチャ
# ─────────────────────────────────────────────

@pytest.fixture
def todo_list(tmp_path):
    """一時ディレクトリにJSONファイルを作成してTodoListを初期化するフィクスチャ。"""
    filepath = str(tmp_path / "todos.json")
    return TodoList(filepath=filepath)


# ─────────────────────────────────────────────
# load メソッド
# ─────────────────────────────────────────────

class TestLoad:
    def test_ファイルが存在しない場合は初期状態になること(self, tmp_path):
        """存在しないファイルパスを渡してもFileNotFoundErrorが発生せず、空リストで初期化される。"""
        filepath = str(tmp_path / "nonexistent.json")
        tl = TodoList(filepath=filepath)
        assert tl.todos == []
        assert tl.next_id == 1

    def test_壊れたJSONファイルでも初期状態になること(self, tmp_path):
        """不正なJSONが書かれたファイルを読み込んでも例外が発生せず、空リストで初期化される。"""
        filepath = tmp_path / "broken.json"
        filepath.write_text("not valid json", encoding="utf-8")
        tl = TodoList(filepath=str(filepath))
        assert tl.todos == []
        assert tl.next_id == 1

    def test_キーが欠落したJSONでも初期状態になること(self, tmp_path):
        """必要なキーが存在しないJSONファイルを読み込んでも例外が発生せず、空リストで初期化される。"""
        filepath = tmp_path / "missing_key.json"
        filepath.write_text(json.dumps({"other": "data"}), encoding="utf-8")
        tl = TodoList(filepath=str(filepath))
        assert tl.todos == []
        assert tl.next_id == 1

    def test_正常なJSONファイルからデータを復元できること(self, tmp_path):
        """正しい形式のJSONファイルからtodosとnext_idが正しく読み込まれる。"""
        filepath = tmp_path / "todos.json"
        data = {
            "todos": [{"id": 1, "title": "タスク1", "done": False}],
            "next_id": 2,
        }
        filepath.write_text(json.dumps(data), encoding="utf-8")
        tl = TodoList(filepath=str(filepath))
        assert len(tl.todos) == 1
        assert tl.next_id == 2


# ─────────────────────────────────────────────
# add メソッド
# ─────────────────────────────────────────────

class TestAdd:
    def test_タスク追加でIDが連番になること(self, todo_list):
        """複数のタスクを追加したとき、IDが1から順番に採番される。"""
        t1 = todo_list.add("タスク1")
        t2 = todo_list.add("タスク2")
        t3 = todo_list.add("タスク3")
        assert t1["id"] == 1
        assert t2["id"] == 2
        assert t3["id"] == 3

    def test_タイトルが前後の空白をtrimされること(self, todo_list):
        """前後に空白を含むタイトルを渡すと、strip()が適用されて保存される。"""
        todo = todo_list.add("  テストタスク  ")
        assert todo["title"] == "テストタスク"

    def test_新規タスクはdone_Falseで初期化されること(self, todo_list):
        """追加直後のタスクのdoneフラグはFalseである。"""
        todo = todo_list.add("新規タスク")
        assert todo["done"] is False

    def test_空文字列はValueErrorになること(self, todo_list):
        """空文字列をタイトルに指定するとValueErrorが発生する。"""
        with pytest.raises(ValueError):
            todo_list.add("")

    def test_空白のみの文字列もValueErrorになること(self, todo_list):
        """空白のみの文字列をタイトルに指定するとValueErrorが発生する（strip後に空になるため）。"""
        with pytest.raises(ValueError):
            todo_list.add("   ")

    def test_NoneはTypeErrorになること(self, todo_list):
        """Noneをタイトルに指定するとTypeErrorが発生する。"""
        with pytest.raises(TypeError):
            todo_list.add(None)

    def test_200文字以内のタイトルは正常に追加されること(self, todo_list):
        """200文字のタイトルは正常に追加される。"""
        title = "あ" * 200
        todo = todo_list.add(title)
        assert todo["title"] == title

    def test_201文字のタイトルはValueErrorになること(self, todo_list):
        """201文字のタイトルを指定するとValueErrorが発生する。"""
        title = "あ" * 201
        with pytest.raises(ValueError):
            todo_list.add(title)


# ─────────────────────────────────────────────
# list_all メソッド
# ─────────────────────────────────────────────

class TestListAll:
    def test_空リストを返すこと(self, todo_list):
        """Todoが0件のとき、list_allは空リストを返す。"""
        assert todo_list.list_all() == []

    def test_複数件返すこと(self, todo_list):
        """追加したTodoの件数と一致するリストを返す。"""
        todo_list.add("タスク1")
        todo_list.add("タスク2")
        result = todo_list.list_all()
        assert len(result) == 2

    def test_コピーが返ること_内部リストと別オブジェクト(self, todo_list):
        """list_allの返却値は内部リストのコピーであり、同一オブジェクトではない。"""
        todo_list.add("タスク1")
        result = todo_list.list_all()
        assert result is not todo_list.todos

    def test_返却リストを変更しても内部状態が変わらないこと(self, todo_list):
        """list_allで取得したリストを変更しても、内部のtodosリストは影響を受けない。"""
        todo_list.add("タスク1")
        result = todo_list.list_all()
        result.clear()
        assert len(todo_list.todos) == 1

    def test_空でも例外が発生しないこと(self, todo_list):
        """Todoが空のとき、list_allは例外を発生させない。"""
        try:
            todo_list.list_all()
        except Exception as e:
            pytest.fail(f"予期しない例外が発生した: {e}")


# ─────────────────────────────────────────────
# complete メソッド
# ─────────────────────────────────────────────

class TestComplete:
    def test_完了フラグがTrueになること(self, todo_list):
        """completeを呼び出すと対象TodoのdoneがTrueになる。"""
        todo = todo_list.add("タスク1")
        todo_list.complete(todo["id"])
        assert todo_list.list_all()[0]["done"] is True

    def test_完了済みtodoを再度completeできること(self, todo_list):
        """既にdone=TrueのTodoをcompleteしてもエラーにならず、done=Trueのまま返る。"""
        todo = todo_list.add("タスク1")
        todo_list.complete(todo["id"])
        result = todo_list.complete(todo["id"])
        assert result["done"] is True

    def test_返却値が該当todoであること(self, todo_list):
        """completeの返却値は対象Todoの辞書である。"""
        todo = todo_list.add("タスク1")
        result = todo_list.complete(todo["id"])
        assert result["id"] == todo["id"]
        assert result["title"] == todo["title"]
        assert result["done"] is True

    def test_存在しないIDはNoneを返すこと(self, todo_list):
        """存在しないIDを指定するとNoneが返る。"""
        result = todo_list.complete(9999)
        assert result is None

    def test_負のIDはNoneを返すこと(self, todo_list):
        """負のIDを指定するとNoneが返る。"""
        result = todo_list.complete(-1)
        assert result is None


# ─────────────────────────────────────────────
# delete メソッド
# ─────────────────────────────────────────────

class TestDelete:
    def test_削除後にlist_allに含まれないこと(self, todo_list):
        """deleteを呼び出した後、そのTodoはlist_allに含まれない。"""
        todo = todo_list.add("タスク1")
        todo_list.delete(todo["id"])
        ids = [t["id"] for t in todo_list.list_all()]
        assert todo["id"] not in ids

    def test_削除後に他のtodoは残ること(self, todo_list):
        """1件削除しても、他のTodoは削除されずに残る。"""
        t1 = todo_list.add("タスク1")
        t2 = todo_list.add("タスク2")
        todo_list.delete(t1["id"])
        remaining = todo_list.list_all()
        assert len(remaining) == 1
        assert remaining[0]["id"] == t2["id"]

    def test_削除成功時はTrueを返すこと(self, todo_list):
        """deleteが成功するとTrueが返る。"""
        todo = todo_list.add("タスク1")
        result = todo_list.delete(todo["id"])
        assert result is True

    def test_存在しないIDはFalseを返すこと(self, todo_list):
        """存在しないIDを指定するとFalseが返る。"""
        result = todo_list.delete(9999)
        assert result is False

    def test_空リストへのdeleteはFalseを返すこと(self, todo_list):
        """Todoが0件のとき、deleteはFalseを返す。"""
        result = todo_list.delete(1)
        assert result is False


# ─────────────────────────────────────────────
# search メソッド
# ─────────────────────────────────────────────

class TestSearch:
    def test_キーワードにマッチするtodoを返すこと(self, todo_list):
        """キーワードを含むTodoのみが返される。"""
        todo_list.add("買い物リスト")
        todo_list.add("運動する")
        result = todo_list.search("買い物")
        assert len(result) == 1
        assert result[0]["title"] == "買い物リスト"

    def test_大文字小文字を区別しないこと(self, todo_list):
        """小文字キーワードで大文字を含むタイトルを検索できる（逆も同様）。"""
        todo_list.add("Python勉強")
        result = todo_list.search("python")
        assert len(result) == 1

        todo_list.add("javascript入門")
        result2 = todo_list.search("JavaScript")
        assert len(result2) == 1

    def test_空キーワードで全件返すこと(self, todo_list):
        """空文字列をキーワードに指定すると全Todoが返される。"""
        todo_list.add("タスク1")
        todo_list.add("タスク2")
        result = todo_list.search("")
        assert len(result) == 2

    def test_マッチしないキーワードは空リストを返すこと(self, todo_list):
        """どのTodoにもマッチしないキーワードを指定すると空リストが返される。"""
        todo_list.add("買い物リスト")
        result = todo_list.search("存在しないキーワード")
        assert result == []

    def test_部分一致で検索できること(self, todo_list):
        """キーワードがタイトルの一部に含まれていれば検索にヒットする。"""
        todo_list.add("Pythonの勉強をする")
        todo_list.add("Javaの勉強をする")
        result = todo_list.search("勉強")
        assert len(result) == 2


# ─────────────────────────────────────────────
# get_stats メソッド
# ─────────────────────────────────────────────

class TestGetStats:
    def test_全件完了時のrateが1_0であること(self, todo_list):
        """全Todoが完了状態のとき、rateは1.0になる。"""
        t1 = todo_list.add("タスク1")
        t2 = todo_list.add("タスク2")
        todo_list.complete(t1["id"])
        todo_list.complete(t2["id"])
        stats = todo_list.get_stats()
        assert stats["rate"] == 1.0
        assert stats["done"] == 2
        assert stats["pending"] == 0

    def test_未完了のみのrateが0_0であること(self, todo_list):
        """完了済みTodoが0件のとき、rateは0.0になる。"""
        todo_list.add("タスク1")
        todo_list.add("タスク2")
        stats = todo_list.get_stats()
        assert stats["rate"] == 0.0
        assert stats["done"] == 0
        assert stats["pending"] == 2

    def test_混在時の正確なrateが返ること(self, todo_list):
        """完了2件・未完了2件のとき、rateは0.5になる。"""
        t1 = todo_list.add("タスク1")
        t2 = todo_list.add("タスク2")
        todo_list.add("タスク3")
        todo_list.add("タスク4")
        todo_list.complete(t1["id"])
        todo_list.complete(t2["id"])
        stats = todo_list.get_stats()
        assert stats["total"] == 4
        assert stats["done"] == 2
        assert stats["pending"] == 2
        assert stats["rate"] == pytest.approx(0.5)

    def test_todoが0件のときZeroDivisionErrorが発生しないこと(self, todo_list):
        """Todoが0件のとき、get_statsはZeroDivisionErrorを発生させず、rate=0.0を返す。"""
        stats = todo_list.get_stats()
        assert stats["total"] == 0
        assert stats["done"] == 0
        assert stats["pending"] == 0
        assert stats["rate"] == 0.0

    def test_pendingが負にならないこと(self, todo_list):
        """pendingはtotal - doneで算出され、負の値にならない。"""
        t1 = todo_list.add("タスク1")
        todo_list.complete(t1["id"])
        stats = todo_list.get_stats()
        assert stats["pending"] >= 0
        assert stats["pending"] == stats["total"] - stats["done"]
