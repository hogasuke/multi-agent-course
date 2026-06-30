import json
from typing import Optional


class TodoList:
    """JSONファイルを永続化ストレージとするTodoリスト管理クラス。

    インスタンス化と同時に指定されたJSONファイルを読み込む。
    追加・完了・削除などの書き込み操作は都度ファイルに保存されるため、
    プロセスを再起動してもデータが失われない。

    Attributes:
        filepath: データを保存するJSONファイルのパス。
        todos: Todoの辞書リスト。各辞書はid(int)、title(str)、done(bool)を持つ。
        next_id: 次に付与するTodoのID（削除されても再利用しない連番）。

    Note:
        ファイルが存在しない場合は空のリストで初期化される。
        ファイルが破損しているか必要なキーが欠落している場合も
        同様に初期状態（空リスト・next_id=1）にフォールバックする。

    Example:
        >>> todo_list = TodoList("my_todos.json")
        >>> item = todo_list.add("牛乳を買う")
        >>> print(item)
        {'id': 1, 'title': '牛乳を買う', 'done': False}
    """

    def __init__(self, filepath: str = "todos.json") -> None:
        self.filepath = filepath
        self.todos: list[dict] = []
        self.next_id: int = 1
        self.load()

    def load(self) -> None:
        """ファイルからTodoリストを読み込む。ファイルが存在しない・壊れている場合は初期状態にフォールバックする。

        FileNotFoundError、json.JSONDecodeError、KeyError が発生した場合は
        例外を握り潰し、todos を空リスト・next_id を 1 にリセットする。
        このメソッドは __init__ から自動的に呼ばれるため、通常は直接呼び出す必要はない。
        """
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.todos = data["todos"]
                self.next_id = data["next_id"]
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # ファイルが存在しない・JSONが壊れている・キーが欠落している場合は初期状態にする
            self.todos = []
            self.next_id = 1

    def save(self) -> None:
        """TodoリストをJSONファイルに保存する。

        todos と next_id を JSON 形式でファイルに書き出す。
        日本語タイトルを正しく保存するため ensure_ascii=False を指定している。
        このメソッドは書き込み操作（add・complete・delete）から自動的に呼ばれる。
        """
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump({"todos": self.todos, "next_id": self.next_id}, f, ensure_ascii=False)

    def add(self, title: str) -> dict:
        """新しいTodoを追加する。

        Args:
            title: Todoのタイトル。前後の空白は自動的に除去される。
                空文字・空白のみ・None・201文字以上は受け付けない。

        Returns:
            追加されたTodoの辞書。キーは id(int)、title(str)、done(bool=False)。

        Raises:
            TypeError: titleがstr型でない場合（Noneを含む）。
            ValueError: titleが空文字（空白のみも含む）または200文字を超える場合。

        Example:
            >>> todo_list = TodoList()
            >>> item = todo_list.add("買い物リストを作る")
            >>> print(item)
            {'id': 1, 'title': '買い物リストを作る', 'done': False}
        """
        if not isinstance(title, str):
            raise TypeError("titleはstr型でなければなりません")

        # 前後の空白を除去してから検証する
        title = title.strip()

        if not title:
            raise ValueError("titleは空文字にできません")

        if len(title) > 200:
            raise ValueError("titleは200文字以内でなければなりません")

        todo = {"id": self.next_id, "title": title, "done": False}
        self.todos.append(todo)
        self.next_id += 1
        self.save()
        return todo

    def list_all(self) -> list[dict]:
        """全Todoのコピーを返す。内部リストへの直接参照は返さない。

        Returns:
            全Todoを含む辞書のリスト。リストは内部データのシャローコピーであり、
            返却されたリスト自体への変更は内部状態に影響しない。
            Todoが0件のときは空リストを返す。

        Example:
            >>> todo_list = TodoList()
            >>> todo_list.add("タスクA")
            {'id': 1, 'title': 'タスクA', 'done': False}
            >>> print(todo_list.list_all())
            [{'id': 1, 'title': 'タスクA', 'done': False}]
        """
        return list(self.todos)

    def complete(self, todo_id: int) -> Optional[dict]:
        """指定IDのTodoを完了状態にする。

        Args:
            todo_id: 完了にするTodoのID（正の整数を想定）。

        Returns:
            完了状態になったTodoの辞書。IDが見つからない場合はNone。
            すでに完了済みのTodoに対して呼び出しても done=True のまま正常に返す。

        Example:
            >>> todo_list = TodoList()
            >>> todo_list.add("レポートを提出する")
            {'id': 1, 'title': 'レポートを提出する', 'done': False}
            >>> result = todo_list.complete(1)
            >>> print(result["done"])
            True
            >>> print(todo_list.complete(999))  # 存在しないID
            None
        """
        for todo in self.todos:
            if todo["id"] == todo_id:
                todo["done"] = True
                self.save()
                return todo
        # IDが見つからない場合は明示的にNoneを返す
        return None

    def delete(self, todo_id: int) -> bool:
        """指定IDのTodoを削除する。

        Args:
            todo_id: 削除するTodoのID（正の整数を想定）。

        Returns:
            削除成功時はTrue、IDが見つからない場合はFalse。
            削除済みのIDや負のIDを指定した場合もFalseを返す。

        Example:
            >>> todo_list = TodoList()
            >>> todo_list.add("不要なタスク")
            {'id': 1, 'title': '不要なタスク', 'done': False}
            >>> print(todo_list.delete(1))
            True
            >>> print(todo_list.delete(1))  # 削除済みのID
            False
        """
        for i, todo in enumerate(self.todos):
            if todo["id"] == todo_id:
                self.todos.pop(i)
                self.save()
                return True
        # IDが見つからない場合はFalseを返す
        return False

    def search(self, keyword: str) -> list[dict]:
        """キーワードでTodoを検索する（大文字小文字を区別しない）。

        Args:
            keyword: 検索キーワード。大文字・小文字の区別なく部分一致で検索する。
                空文字を指定すると全件が返る。

        Returns:
            キーワードにマッチするTodoの辞書リスト。一致するものがなければ空リスト。

        Example:
            >>> todo_list = TodoList()
            >>> todo_list.add("Python学習")
            {'id': 1, 'title': 'Python学習', 'done': False}
            >>> todo_list.add("python環境構築")
            {'id': 2, 'title': 'python環境構築', 'done': False}
            >>> results = todo_list.search("python")
            >>> print(len(results))  # 大文字小文字問わず2件マッチ
            2
        """
        keyword_lower = keyword.lower()
        return [todo for todo in self.todos if keyword_lower in todo["title"].lower()]

    def get_stats(self) -> dict:
        """Todoリストの統計情報を返す。

        Returns:
            以下のキーを持つ辞書。

            - total (int): Todoの総数。
            - done (int): 完了済みTodoの件数。
            - pending (int): 未完了Todoの件数（total - done）。
            - rate (float): 完了率（0.0〜1.0）。Todoが0件のときは0.0を返し、
              ZeroDivisionErrorは発生しない。

        Example:
            >>> todo_list = TodoList()
            >>> todo_list.add("タスク1")
            {'id': 1, 'title': 'タスク1', 'done': False}
            >>> todo_list.add("タスク2")
            {'id': 2, 'title': 'タスク2', 'done': False}
            >>> todo_list.complete(1)
            {'id': 1, 'title': 'タスク1', 'done': True}
            >>> print(todo_list.get_stats())
            {'total': 2, 'done': 1, 'pending': 1, 'rate': 0.5}
        """
        total = len(self.todos)
        done = sum(1 for todo in self.todos if todo["done"])
        return {
            "total": total,
            "done": done,
            "pending": total - done,
            # Todoが0件のときはゼロ除算を避けて0.0を返す
            "rate": done / total if total > 0 else 0.0,
        }
