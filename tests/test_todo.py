"""
src/todo.py の TodoList クラスに対するテスト

正常系・異常系・エッジケースを網羅する。
各テストは tmp_path フィクスチャを使い、ファイルシステムへの副作用を避ける。
"""
import json
import pytest

from src.todo import TodoList


# ---------------------------------------------------------------------------
# ヘルパー
# ---------------------------------------------------------------------------

def make_todo_list(tmp_path, todos=None, next_id=1):
    """テスト用の TodoList インスタンスを生成するヘルパー。

    指定した初期データで JSON ファイルを作成してから TodoList を返す。
    """
    filepath = tmp_path / "todos.json"
    initial = {"todos": todos if todos is not None else [], "next_id": next_id}
    filepath.write_text(json.dumps(initial), encoding="utf-8")
    return TodoList(str(filepath))


# ===========================================================================
# 正常系テスト
# ===========================================================================

class TestAdd:
    """add() メソッドの正常系テスト"""

    def test_タスクを追加できる(self, tmp_path):
        """add() でタスクを追加し、返り値に id・title・done が含まれることを確認する"""
        tl = make_todo_list(tmp_path)
        todo = tl.add("牛乳を買う")
        assert todo["title"] == "牛乳を買う"
        assert todo["done"] is False
        assert todo["id"] == 1

    def test_複数タスクを追加するとIDが連番になる(self, tmp_path):
        """add() を複数回呼ぶと ID が 1, 2, 3 ... と自動採番されることを確認する"""
        tl = make_todo_list(tmp_path)
        t1 = tl.add("タスク1")
        t2 = tl.add("タスク2")
        t3 = tl.add("タスク3")
        assert t1["id"] == 1
        assert t2["id"] == 2
        assert t3["id"] == 3

    def test_追加したタスクがlist_allに含まれる(self, tmp_path):
        """add() 後に list_all() が追加したタスクを返すことを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("朝食を食べる")
        all_todos = tl.list_all()
        assert len(all_todos) == 1
        assert all_todos[0]["title"] == "朝食を食べる"

    def test_タスクを追加するとファイルに保存される(self, tmp_path):
        """add() 後にファイルの内容が更新されることを確認する"""
        filepath = tmp_path / "todos.json"
        initial = {"todos": [], "next_id": 1}
        filepath.write_text(json.dumps(initial), encoding="utf-8")
        tl = TodoList(str(filepath))
        tl.add("保存確認タスク")
        data = json.loads(filepath.read_text(encoding="utf-8"))
        assert len(data["todos"]) == 1
        assert data["todos"][0]["title"] == "保存確認タスク"


class TestListAll:
    """list_all() メソッドの正常系テスト"""

    def test_空のリストを返す(self, tmp_path):
        """タスクが 0 件のとき list_all() は空リストを返すことを確認する"""
        tl = make_todo_list(tmp_path)
        assert tl.list_all() == []

    def test_追加した全タスクを返す(self, tmp_path):
        """追加した件数分のタスクが list_all() で取得できることを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("タスクA")
        tl.add("タスクB")
        assert len(tl.list_all()) == 2


class TestComplete:
    """complete() メソッドの正常系テスト"""

    def test_タスクを完了にできる(self, tmp_path):
        """complete() を呼ぶと done が True になることを確認する"""
        tl = make_todo_list(tmp_path)
        todo = tl.add("報告書を書く")
        result = tl.complete(todo["id"])
        assert result is not None
        assert result["done"] is True

    def test_complete後に他タスクはdoneのままでない(self, tmp_path):
        """complete() は指定 ID のタスクのみ完了にすることを確認する"""
        tl = make_todo_list(tmp_path)
        t1 = tl.add("タスク1")
        t2 = tl.add("タスク2")
        tl.complete(t1["id"])
        assert tl.todos[0]["done"] is True
        assert tl.todos[1]["done"] is False


class TestDelete:
    """delete() メソッドの正常系テスト"""

    def test_タスクを削除できる(self, tmp_path):
        """delete() が True を返し、リストから対象タスクが消えることを確認する"""
        tl = make_todo_list(tmp_path)
        todo = tl.add("削除するタスク")
        result = tl.delete(todo["id"])
        assert result is True
        assert len(tl.list_all()) == 0

    def test_中間タスクを削除しても残りが保持される(self, tmp_path):
        """3 件中の 2 件目を削除したとき、残り 2 件が保持されることを確認する"""
        tl = make_todo_list(tmp_path)
        t1 = tl.add("タスク1")
        t2 = tl.add("タスク2")
        t3 = tl.add("タスク3")
        tl.delete(t2["id"])
        remaining = tl.list_all()
        assert len(remaining) == 2
        ids = [t["id"] for t in remaining]
        assert t1["id"] in ids
        assert t3["id"] in ids
        assert t2["id"] not in ids


class TestSearch:
    """search() メソッドの正常系テスト"""

    def test_キーワードにマッチするタスクを返す(self, tmp_path):
        """search() がキーワードを含むタスクのみ返すことを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("牛乳を買う")
        tl.add("パンを買う")
        tl.add("運動をする")
        results = tl.search("買う")
        assert len(results) == 2

    def test_マッチしない場合は空リスト(self, tmp_path):
        """search() でマッチしないキーワードを渡すと空リストが返ることを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("牛乳を買う")
        results = tl.search("存在しないキーワード")
        assert results == []


class TestGetStats:
    """get_stats() メソッドの正常系テスト"""

    def test_統計情報が正しく返る(self, tmp_path):
        """タスクが複数件あるとき get_stats() の total / done / pending / rate が正しいことを確認する"""
        tl = make_todo_list(tmp_path)
        t1 = tl.add("タスク1")
        t2 = tl.add("タスク2")
        tl.add("タスク3")
        tl.complete(t1["id"])
        tl.complete(t2["id"])
        stats = tl.get_stats()
        assert stats["total"] == 3
        assert stats["done"] == 2
        assert stats["pending"] == 1
        assert pytest.approx(stats["rate"]) == 2 / 3

    def test_全件完了時にrateが1_0になる(self, tmp_path):
        """全タスクを完了にしたとき rate が 1.0 になることを確認する"""
        tl = make_todo_list(tmp_path)
        t = tl.add("唯一のタスク")
        tl.complete(t["id"])
        stats = tl.get_stats()
        assert stats["rate"] == 1.0


# ===========================================================================
# 異常系・エッジケーステスト
# ===========================================================================

class TestEdgeCases:
    """コードレビューで指摘されたエッジケースのテスト"""

    # ------------------------------------------------------------------
    # エッジケース 1: load() のファイル未存在
    # ------------------------------------------------------------------
    def test_ファイルが存在しない場合にFileNotFoundErrorが発生する(self, tmp_path):
        """初回起動時（JSON ファイルなし）に FileNotFoundError が送出されるバグを確認する"""
        non_existent = str(tmp_path / "not_exists.json")
        with pytest.raises(FileNotFoundError):
            TodoList(non_existent)

    # ------------------------------------------------------------------
    # エッジケース 2: get_stats() のゼロ除算
    # ------------------------------------------------------------------
    def test_タスクが0件のときget_statsはZeroDivisionErrorになる(self, tmp_path):
        """タスクが 0 件のとき get_stats() が ZeroDivisionError を送出するバグを確認する"""
        tl = make_todo_list(tmp_path)
        with pytest.raises(ZeroDivisionError):
            tl.get_stats()

    # ------------------------------------------------------------------
    # エッジケース 3: complete() の存在しない ID
    # ------------------------------------------------------------------
    def test_存在しないIDのcompleteはNoneを返す(self, tmp_path):
        """complete() に存在しない ID を渡すと暗黙的に None が返るバグ相当の挙動を確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("タスク")
        result = tl.complete(9999)
        assert result is None

    def test_空リストでcompleteはNoneを返す(self, tmp_path):
        """タスクが 0 件の状態で complete() を呼ぶと None が返ることを確認する"""
        tl = make_todo_list(tmp_path)
        result = tl.complete(1)
        assert result is None

    # ------------------------------------------------------------------
    # エッジケース 4: delete() の存在しない ID
    # ------------------------------------------------------------------
    def test_存在しないIDのdeleteはNoneを返す(self, tmp_path):
        """delete() に存在しない ID を渡すと暗黙的に None が返るバグ相当の挙動を確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("タスク")
        result = tl.delete(9999)
        assert result is None

    def test_空リストでdeleteはNoneを返す(self, tmp_path):
        """タスクが 0 件の状態で delete() を呼ぶと None が返ることを確認する"""
        tl = make_todo_list(tmp_path)
        result = tl.delete(1)
        assert result is None

    def test_存在しないIDのdeleteはリストを変化させない(self, tmp_path):
        """存在しない ID への delete() 後もリストの件数が変わらないことを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("タスク1")
        tl.add("タスク2")
        tl.delete(9999)
        assert len(tl.list_all()) == 2

    # ------------------------------------------------------------------
    # エッジケース 5: search() の大文字小文字
    # ------------------------------------------------------------------
    def test_検索は大文字小文字を区別するため異なるケースはヒットしない(self, tmp_path):
        """search() は大文字小文字を区別するため、"buy" で "Buy" はヒットしないバグを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("Buy milk")
        results = tl.search("buy")
        # 大文字小文字を区別するため "buy" では "Buy" がヒットしないことを確認する
        assert len(results) == 0

    def test_完全一致するケースはヒットする(self, tmp_path):
        """search() でタイトルと同じ大文字小文字のキーワードならヒットすることを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("Buy milk")
        results = tl.search("Buy")
        assert len(results) == 1


# ===========================================================================
# 境界値テスト
# ===========================================================================

class TestBoundary:
    """境界値テスト"""

    def test_空文字タイトルのタスクを追加できる(self, tmp_path):
        """title が空文字でも add() でタスクを追加できることを確認する"""
        tl = make_todo_list(tmp_path)
        todo = tl.add("")
        assert todo["title"] == ""
        assert todo["id"] == 1

    def test_空文字キーワードで全タスクがヒットする(self, tmp_path):
        """search("") は全タスクのタイトルにマッチするため全件返ることを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("タスクA")
        tl.add("タスクB")
        results = tl.search("")
        assert len(results) == 2

    def test_非常に長いタイトルのタスクを追加できる(self, tmp_path):
        """非常に長い title 文字列でも add() がエラーなく動作することを確認する"""
        tl = make_todo_list(tmp_path)
        long_title = "あ" * 10000
        todo = tl.add(long_title)
        assert todo["title"] == long_title

    def test_1件だけ完了のrateが1_0(self, tmp_path):
        """1 件追加して完了にした場合に rate が 1.0 になることを確認する"""
        tl = make_todo_list(tmp_path)
        t = tl.add("タスク")
        tl.complete(t["id"])
        stats = tl.get_stats()
        assert stats["rate"] == 1.0

    def test_1件だけ未完了のrateが0_0(self, tmp_path):
        """1 件追加して未完了の場合に rate が 0.0 になることを確認する"""
        tl = make_todo_list(tmp_path)
        tl.add("タスク")
        stats = tl.get_stats()
        assert stats["rate"] == 0.0

    def test_次IDが引き継がれてファイル再読み込み後も連番になる(self, tmp_path):
        """ファイルに保存後、別インスタンスで読み込んでも next_id が継続されることを確認する"""
        filepath = tmp_path / "todos.json"
        initial = {"todos": [], "next_id": 1}
        filepath.write_text(json.dumps(initial), encoding="utf-8")
        tl1 = TodoList(str(filepath))
        tl1.add("タスク1")
        # 別インスタンスで読み込む
        tl2 = TodoList(str(filepath))
        t2 = tl2.add("タスク2")
        assert t2["id"] == 2
