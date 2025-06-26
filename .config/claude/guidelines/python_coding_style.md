# Python Coding Style Guidelines

このドキュメントは，Python開発におけるコーディングスタイルのガイドラインです．

## パッケージ管理
- パッケージ管理ツールは`uv` のみを使用し，`pip` を使用しない
- インストール：`uv add {package}`
- ツールの実行：`uv run {tool}`
- アップグレード：`uv add --dev {package} --upgrade-package {package}`
- 禁止事項：`uv pip install`, `@latest`

## リント・フォーマット
- リンタ・フォーマッタは`ruff`を使用
- チェック実行：`uv run --frozen ruff check .`
- フォーマット実行：`uv run --frozen ruff format .`
- 修正実行：`uv run --frozen ruff check . --fix`
- 重要な指摘内容：
  - 行の長さ（119文字）
  - インポートのソート（I001）
  - 未使用のインポート
  - 行の折り返し
    - 文字列は括弧を使う
    - 関数呼び出しは複数行にして適切にインデント
    - インポート文は複数行に分ける

##　静的型解析
- 静的型解析はpyrightを使用し，定期的に静的解析をして発生した警告を修正
- 型チェック：`uv run --frozen pyright`
     - Optional型には明示的なNoneチェックを入れる
     - 文字列の型は狭めて扱う
     - バージョン警告はチェックが通れば無視してよい

## テスト
- テストフレームワークは`pytest`のみを使用し，`unittest`を用いない
- テスト：`uv run --frozen pytest`
- 非同期テストは`anyio`を使用し，`asyncio`を使用しない

## pre-commit
   - 設定ファイル：`./.pre-commit-config.yaml`
     - ない場合はpre-commitしなくてよい
   - 実行タイミング：gitコミット時
   - 使用ツール：Prettier(.yml/.yaml/.json)，Ruff(.py)
   - Ruffの更新方法：
     - PyPIのバージョンを確認
     - 設定ファイルのリビジョンを更新
     - 設定ファイルをコミット

## ディレクトリ
- ./srcディレクトリにエントリポイント含むプロダクトコードを格納
- ./testsディレクトリにテストコードを格納

## ファイル
- コードは1行119字以内（PEPでは79字だが，より実用的な長さを採用）
  - URLは超過可能
- 型ヒントを必ずつける
  - 古い型ヒントを使わない
    - typing.List -> list, ...
    - typing.Iterator -> collections.abc.Iterator, ...
    - typing.Union -> |, typing.Optional -> | None, ...

## 構文規則

### クラス
- `dataclasses`や`pydantic`を使用しない場合は\__slots\__で変数を制限
- Value Object:
  - コードベースが中規模，または`dataclasses`を用いたほうがより良い実装になる場合，`dataclasses.dataclass(frozen=True)`を使用
  - コードベースが大規模になる場合，`pydantic`を使用
  - 見極めが難しいため判断に困る場合はユーザーに判断を委ねる
- `@staticmethod`は使わざるを得ない場合設計が誤っているため基本使用しない

### 関数
- Pythonicな文法を使用する（内包表記，With Statement, ...）
- `local`，`nonlocal`は使用しない（明示的でないため）

### 文字列

#### 引用符の使い分け
- 文字列中に `'` がある場合: `"` を使用
- 文字列中に `"` がある場合: `'` を使用
- 文字列中に変数を代入する場合（f-strings）: `"` を使用
- Raise文では `"` を使用（通常の文で `'` を使うため）

#### 演算子
- 演算子とオブジェクトは1文字離す
- 2個以上の演算子を用いる場合，`*`， `/`， `//`， `%`， `**` などは空白を開けない（優先度が高いため）

### ロギング

#### 基本方針
- 辞書型で書く
- システムにとって重要でトラブルが起きたら困る場所に多くロギングを書いておく
  - 例: CSVファイルの参照やraise文の前後など

#### 例
```python
logger.info({
    "action": "save"，
    "csv_file": self.csv_file，
    "status": "run"
})
```

## 命名規則

### 基本原則
- 頭文字を数字にしない

### 命名パターン
- 定数: `SCREAMING_SNAKE_CASE`
- 変数/関数/ファイル: `snake_case`
  - getter: 出力する変数名
- クラス: `UpperCamelCase`
- イテレータ引数:
  - 文が2行以内の場合: 1字
  - 3行以上の場合: 分かりやすい命名

## 空白・レイアウト

### 2行空白
- import文
- グローバル変数の定義
- オブジェクトの定義間

### 1行空白
- 関数定義の `"""`，`Args`、`Returns/Yields`、`Raises` 間
- 標準，サードパーティ、ローカル、個人ライブラリimport間
- インスタンスメソッド間

### インデント
- 多数のオブジェクトを並列して扱う場合は前の要素にインデントを合わせ改行する場合がある

## コメント

### 基本方針
- コメントは可能ならば行に独立で書く

### ドキュメンテーション
- パブリックAPIには必ずドキュメンテーション文字列（docstring）を付ける

#### ファイルレベル
```python
"""ファイルの機能を説明"""
```

#### クラス・メソッドレベル
```python
class MyClass:
    """クラスの機能説明"""

    def method(self):
        """メソッドの機能説明"""
```

#### 関数レベル
```python
def function_name(arg1， arg2):
    """関数の機能のまとめ.

    (関数の機能の詳細.)

    Args:
        arg1 (type): 引数の説明
        arg2 (type): 引数の説明

    Returns/Yields:
        type: 戻り値の説明

    Raises:
        ErrorType: エラーの説明

    (see details at: URL)
    """
```

#### インラインコメント
- 伝えたいコードの意図はコードの上に書く

## コーディングスタイル例

```python
"""ファイルの機能の説明"""

import typing


DEFAULT_NAME = 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'


x = {
    'test': 1，
    'test2': 2，
}
y = (1，)
z = x*2 - 1
a = (x + 1) * (x - 1)
b = 10000000000000000 \
    + 100000000000000


def test_func(x， y， z，
              aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa='test'):
    """関数の機能.

    Args:
        x: 引数の説明
        y: 引数の説明
        z: 引数の説明
        aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa: 引数の説明

    Returns:
        int: 戻り値の説明

    see details at:https://aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.com
    """

    if x > 0:
        return x
    else:
        return None


class Person(object):
    """Base csv model."""

    def __init__(self， user_name=''):
        # TODO (shugyo596) 変更内容
        self.__user_name = user_name

    def save(self， force=True):
        """Save data to csv file."""
        # TODO (jsakai) Use locking mechanism for avoiding dead lock issue
        logger.info({
            'action': 'save'，
            'csv_file': self.csv_file，
            'force': force，
            'status': 'run'
        })

        with open(self.csv_file， 'w+') as csv_file:
            writer = csv.DictWriter(csv_file， fieldnames=self.column)
            writer.writeheader()

            for name， count in self.data.items():
                writer.writerow({
                    RANKING_COLUMN_NAME: name，
                    RANKING_COLUMN_COUNT: count
                })

        logger.info({
            'action': 'save'，
            'csv_file': self.csv_file，
            'force': force，
            'status': 'success'
        })

    @property
    def user_name(self):
        return self._user_name


print(f"abc{word}abc")


ranking = {'a': 100， 'b': 90}
for k， v in ranking.items():
    print(k， v)


# main.py
def main():
    print("main")


if __name__ == '__main__':
    main()
```

## 補足

このガイドラインは，PEP 8を基準としつつ、実用性を重視した調整を加えています．特に1行の文字数制限を119字に設定することで、現代の開発環境により適した形にしています．
