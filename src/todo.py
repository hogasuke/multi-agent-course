import json


class TodoList:
    """JSONファイルを永続化ストレージとして使うTodoリスト管理クラス。

    タスクの追加・一覧取得・完了・削除・検索・統計取得の機能を提供する。
    インスタンス生成時に指定したJSONファイルを自動的に読み込む。

    Attributes:
        filepath (str): タスクデータを保存するJSONファイルのパス。
        todos (list[dict]): 現在のタスク一覧。各要素は id・title・done を持つ辞書。
        next_id (int): 次に追加するタスクへ割り当てるID。

    Example:
        >>> tl = TodoList("my_todos.json")
        >>> todo = tl.add("牛乳を買う")
        >>> tl.complete(todo["id"])
        >>> tl.get_stats()
        {'total': 1, 'done': 1, 'pending': 0, 'rate': 1.0}
    """

    def __init__(self, filepath="todos.json"):
        """TodoListを初期化し、JSONファイルからデータを読み込む。

        Args:
            filepath (str): タスクデータを保存するJSONファイルのパス。
                デフォルトは "todos.json"。

        Raises:
            FileNotFoundError: 指定したファイルが存在しない場合に発生する。
                初回起動時はファイルを事前に作成しておく必要がある。
                （既知の問題: 自動作成は行われない）

        Note:
            filepath にパストラバーサル（例: "../../etc/passwd"）を含む値を
            渡しても入力検証は行われない。（既知の問題）
        """
        self.filepath = filepath
        self.todos = []
        self.next_id = 1
        self.load()

    def load(self):
        """JSONファイルからタスクデータを読み込み、インスタンスの状態を更新する。

        Raises:
            FileNotFoundError: self.filepath が存在しない場合に発生する。
                例外処理は実装されていないため、呼び出し元が対処する必要がある。
                （既知の問題）

        Note:
            - ファイルオープンに ``with`` 文を使用していないため、
              例外発生時にファイルディスクリプタがリークする可能性がある。
              （既知の問題）
            - ``open()`` に ``encoding`` を指定していないため、
              実行環境によっては日本語が文字化けするリスクがある。
              （既知の問題）
        """
        f = open(self.filepath, "r")
        data = json.load(f)
        self.todos = data["todos"]
        self.next_id = data["next_id"]
        f.close()

    def save(self):
        """現在のタスク一覧とnext_idをJSONファイルに書き込む。

        Note:
            - ファイルオープンに ``with`` 文を使用していないため、
              例外発生時にファイルディスクリプタがリークする可能性がある。
              （既知の問題）
            - ``open()`` に ``encoding`` を指定していないため、
              実行環境によっては日本語が文字化けするリスクがある。
              （既知の問題）
        """
        f = open(self.filepath, "w")
        json.dump({"todos": self.todos, "next_id": self.next_id}, f)
        f.close()

    def add(self, title):
        """新しいタスクを追加する。

        タスクを内部リストへ追加し、next_idを1増加させてからファイルに保存する。

        Args:
            title (str): タスクのタイトル。空文字や非常に長い文字列も受け付ける。

        Returns:
            dict: 追加されたタスクの辞書。キーは以下の通り。
                - id (int): タスクの一意なID。
                - title (str): タスクのタイトル。
                - done (bool): 完了フラグ。追加直後は必ず False。

        Example:
            >>> tl = TodoList("todos.json")
            >>> todo = tl.add("買い物をする")
            >>> todo
            {'id': 1, 'title': '買い物をする', 'done': False}

        Note:
            title の入力値検証（空文字チェック・長さ制限など）は行っていない。
            （既知の問題）
        """
        todo = {"id": self.next_id, "title": title, "done": False}
        self.todos.append(todo)
        self.next_id += 1
        self.save()
        return todo

    def list_all(self):
        """全タスクの一覧を返す。

        Returns:
            list[dict]: 全タスクを格納したリスト。
                タスクが0件の場合は空リストを返す。
                各辞書のキーは id・title・done。

        Example:
            >>> tl = TodoList("todos.json")
            >>> tl.add("タスクA")
            >>> tl.add("タスクB")
            >>> tl.list_all()
            [{'id': 1, 'title': 'タスクA', 'done': False},
             {'id': 2, 'title': 'タスクB', 'done': False}]
        """
        return self.todos

    def complete(self, todo_id):
        """指定したIDのタスクを完了状態にする。

        タスクの ``done`` フィールドを True に設定してファイルに保存する。

        Args:
            todo_id (int): 完了にするタスクのID。

        Returns:
            dict | None: 完了にしたタスクの辞書を返す。
                指定したIDのタスクが存在しない場合は暗黙的に None を返す。

        Example:
            >>> tl = TodoList("todos.json")
            >>> todo = tl.add("レポートを書く")
            >>> result = tl.complete(todo["id"])
            >>> result["done"]
            True

        Note:
            存在しないIDを指定しても例外は送出されず、戻り値として None が返る。
            呼び出し元は戻り値が None かどうかを確認して失敗を検出する必要がある。
            （既知の問題）
        """
        for todo in self.todos:
            if todo["id"] == todo_id:
                todo["done"] = True
                self.save()
                return todo

    def delete(self, todo_id):
        """指定したIDのタスクをリストから削除する。

        対象タスクを内部リストから取り除き、ファイルに保存する。

        Args:
            todo_id (int): 削除するタスクのID。

        Returns:
            bool | None: 削除に成功した場合は True を返す。
                指定したIDのタスクが存在しない場合は暗黙的に None を返す。

        Example:
            >>> tl = TodoList("todos.json")
            >>> todo = tl.add("不要なタスク")
            >>> tl.delete(todo["id"])
            True
            >>> tl.list_all()
            []

        Note:
            存在しないIDを指定しても例外は送出されず、戻り値として None が返る。
            呼び出し元は戻り値が None かどうかを確認して失敗を検出する必要がある。
            （既知の問題）
        """
        for i, todo in enumerate(self.todos):
            if todo["id"] == todo_id:
                self.todos.pop(i)
                self.save()
                return True

    def search(self, keyword):
        """タイトルにキーワードを含むタスクを検索する。

        全タスクのタイトルに対して部分一致検索を行い、マッチしたタスクを返す。

        Args:
            keyword (str): 検索するキーワード文字列。
                空文字を渡すと全タスクがヒットする。

        Returns:
            list[dict]: キーワードにマッチしたタスクのリスト。
                マッチするタスクがない場合は空リストを返す。

        Example:
            >>> tl = TodoList("todos.json")
            >>> tl.add("牛乳を買う")
            >>> tl.add("パンを買う")
            >>> tl.add("運動をする")
            >>> tl.search("買う")
            [{'id': 1, 'title': '牛乳を買う', 'done': False},
             {'id': 2, 'title': 'パンを買う', 'done': False}]

        Note:
            大文字小文字を区別する検索を行う。
            例えば ``"buy"`` を渡しても ``"Buy"`` を含むタスクはヒットしない。
            （既知の問題）
        """
        result = []
        for todo in self.todos:
            if keyword in todo["title"]:
                result.append(todo)
        return result

    def get_stats(self):
        """タスクの統計情報を返す。

        全タスク数・完了数・未完了数・完了率を計算して辞書で返す。

        Returns:
            dict: 統計情報を格納した辞書。キーは以下の通り。
                - total (int): 全タスク数。
                - done (int): 完了済みタスク数。
                - pending (int): 未完了タスク数。
                - rate (float): 完了率（0.0〜1.0）。

        Raises:
            ZeroDivisionError: タスクが0件のときに ``done / total`` の計算で発生する。
                （既知の問題: タスクが存在することを事前に確認する必要がある）

        Example:
            >>> tl = TodoList("todos.json")
            >>> tl.add("タスク1")
            >>> tl.add("タスク2")
            >>> tl.complete(1)
            >>> tl.get_stats()
            {'total': 2, 'done': 1, 'pending': 1, 'rate': 0.5}
        """
        total = len(self.todos)
        done = 0
        for todo in self.todos:
            if todo["done"]:
                done += 1
        return {"total": total, "done": done, "pending": total - done, "rate": done / total}
