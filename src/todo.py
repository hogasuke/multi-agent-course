from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TodoItem:
    id: int
    title: str
    completed: bool = False


class TodoList:
    """Todoリストを管理するクラス"""

    def __init__(self) -> None:
        self._items: list[TodoItem] = []
        self._next_id: int = 1

    def add(self, title: str) -> TodoItem:
        """新しいTodoを追加する"""
        item = TodoItem(id=self._next_id, title=title)
        self._items.append(item)
        self._next_id += 1
        return item

    def list_all(self) -> list[TodoItem]:
        """全Todoを返す"""
        return list(self._items)

    def complete(self, todo_id: int) -> Optional[TodoItem]:
        """指定IDのTodoを完了済みにする。見つからない場合はNoneを返す"""
        item = self._find(todo_id)
        if item is not None:
            item.completed = True
        return item

    def delete(self, todo_id: int) -> Optional[TodoItem]:
        """指定IDのTodoを削除する。見つからない場合はNoneを返す"""
        item = self._find(todo_id)
        if item is not None:
            self._items.remove(item)
        return item

    def _find(self, todo_id: int) -> Optional[TodoItem]:
        return next((item for item in self._items if item.id == todo_id), None)
