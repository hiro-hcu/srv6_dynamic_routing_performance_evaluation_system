# SRv6 Multi-Table Manager 関数分析（最適化版）

## 📊 プログラム構造概要（最適化後）

### 🏗️ クラス設計 - 単一責任原則に基づく分離

#### データクラス
- **SRv6Config**: 統合設定管理（SSH、セグメント、テーブル定義）
- **TableRoute**: テーブル経路情報（パス、SID、コスト）
- **PathChangeEvent**: 経路変更イベント記録

#### 機能別クラス（最適化により新設）
- **RRDDataManager**: RRDデータ取得とエッジ重み更新
- **PathCalculator**: 経路計算とSIDリスト生成
- **SSHConnectionManager**: SSH接続とコマンド実行
- **RoutingTableManager**: ルーティングテーブル更新

#### メインクラス
- **SRv6PathManager**: 双方向パス管理（簡素化版）
- **SRv6RealTimeMultiTableManager**: リアルタイム監視（簡素化版）

## 🔄 最適化後の関数依存関係図

```
main()
├── SRv6PathManager (双方向モード)
│   ├── RRDDataManager.update_edge_weights()
│   │   └── fetch_rrd_data() [複数回呼び出し]
│   ├── PathCalculator.calculate_multiple_paths()
│   ├── PathCalculator.path_to_sid_list()
│   ├── RoutingTableManager.create_table_routes()
│   ├── SSHConnectionManager.r1_connection()
│   ├── SSHConnectionManager.r6_connection()
│   └── RoutingTableManager.update_all_tables()
│       └── SSHConnectionManager.execute_command()
│
└── SRv6RealTimeMultiTableManager (往路のみモード)
    └── real_time_monitor()
        ├── display_status()
        ├── detect_path_changes()
        ├── log_path_changes()
        └── [上記機能クラスを委譲して使用]
```

## 📋 クラス別機能解析

### � RRDDataManager

#### `__init__(config)`
- **目的**: RRDファイルパス設定とネットワークトポロジー構築
- **依存**: SRv6Config（設定データ）
- **初期化**: NetworkXグラフと重みマッピング

#### `update_edge_weights()`
- **目的**: RRDデータに基づくエッジ重み更新
- **依存関数**: `fetch_rrd_data()`
- **影響**: グラフ全体の最短経路計算に影響
- **実行頻度**: 60秒間隔のリアルタイム更新

#### `fetch_rrd_data(rrd_file, latest_seconds=120)`
- **目的**: RRDファイルからトラフィック情報取得
- **戻り値**: 平均トラフィック値（Kbps）
- **エラーハンドリング**: デフォルト値1000で継続

### 🧮 PathCalculator

#### `__init__(config)`
- **目的**: 経路計算用の設定とセグメント情報管理
- **依存**: SRv6Config（セグメント→ノードマッピング）

#### `calculate_multiple_paths(graph, source, target, k=3)`
- **目的**: 複数経路候補の生成
- **アルゴリズム**: NetworkXの最短パス＋代替パス
- **戻り値**: パスリスト（コスト順ソート）
- **依存**: 更新されたグラフトポロジーとエッジ重み

#### `path_to_sid_list(path)`
- **目的**: ノードパスをSRv6セグメントIDリストに変換
- **変換ルール**: 中間ノードのセグメントのみ含める
- **戻り値**: カンマ区切りSIDリスト

### 🔗 SSHConnectionManager

#### `__init__(config)`
- **目的**: SSH接続情報の設定管理
- **依入**: SRv6Config（ホスト、ユーザー、パスワード）

#### `r1_connection()` / `r6_connection()`
- **目的**: コンテキストマネージャーによる安全なSSH接続
- **戻り値**: paramiko.SSHClientインスタンス
- **エラーハンドリング**: 接続失敗時の適切なクリーンアップ

#### `execute_command(ssh, command)`
- **目的**: SSHコマンド実行と結果取得
- **戻り値**: (stdout, stderr, exit_status)タプル
- **ログ出力**: コマンドと実行結果の詳細

### 📋 RoutingTableManager

#### `__init__(config)`
- **目的**: ルーティングテーブル操作の設定管理
- **依存**: SRv6Config（テーブル定義）

#### `create_table_routes(paths, source, target)`
- **目的**: 複数パスからTableRouteオブジェクト生成
- **変換処理**: パス→SIDリスト→nftablesコマンド
- **戻り値**: TableRouteリスト

#### `update_all_tables(table_routes, ssh_manager)`
- **目的**: 全テーブルルートの一括更新
- **引数**: ルートリスト、SSH接続マネージャー
- **処理**: 各ルートを順次nftablesで更新
- **エラーハンドリング**: 失敗時ログ出力

### 🎯 メインクラス

#### `SRv6PathManager.__init__(config)`
- **目的**: 双方向パス管理の初期化
- **依存**: 上記4つの機能クラスのインスタンス化
- **設定**: 双方向モード（r1⇔r6）

#### `SRv6PathManager.manage_bidirectional_paths()`
- **目的**: 双方向の動的パス管理実行
- **処理フロー**: 
  1. RRDデータ更新
  2. 往路・復路の経路計算
  3. ルーティングテーブル更新
- **実行間隔**: 60秒

#### `SRv6RealTimeMultiTableManager.real_time_monitor()`
- **目的**: 従来の往路のみリアルタイム監視（互換性）
- **処理**: 上記機能クラスに処理を委譲
- **変更検出**: detect_path_changes()による差分監視

## 🔄 最適化による改善点

### ✅ コードの改善
- **責任分離**: 単一責任原則に基づくクラス分割
- **重複排除**: 同一機能の重複実装を統合
- **保守性向上**: 各クラスが独立してテスト可能
- **拡張性**: 新機能追加時の影響範囲を限定

### 🚀 実行効率の向上
- **メモリ効率**: 設定情報の一元管理
- **接続管理**: SSH接続のコンテキストマネージャー化
- **エラーハンドリング**: 各層での適切な例外処理

### 🔧 運用モード
- **双方向モード**: SRv6PathManagerによる完全なr1⇔r6管理
- **従来モード**: SRv6RealTimeMultiTableManagerによる互換性維持
- **解析モード**: テーブル更新なしでの経路計算確認

## 💾 主要データ構造（最適化後）

### 🏗️ 設定クラス: SRv6Config
```python
@dataclass
class SRv6Config:
    rrd_paths: Dict[Tuple[int, int], str]
    segment_to_node: Dict[str, int] 
    forward_tables: Dict[int, str]
    return_tables: Dict[int, str]
    ssh_host: str = "172.18.0.3"
    ssh_user: str = "user"
    ssh_password: str = "user"
    1: {2: "fd01:2::12", 3: "fd01:8::12"},
    # ... 他のセグメント
}
```

```

### 📊 データクラス
```python
@dataclass
class TableRoute:
    path: List[int]          # ノード経路
    sid_list: str           # SRv6セグメントIDリスト
    cost: float             # 経路コスト
    table_name: str         # nftablesテーブル名

@dataclass
class PathChangeEvent:
    timestamp: float
    old_path: List[int]
    new_path: List[int]
    cost_change: float
```

### 🌐 ネットワークトポロジー構造
```python
# NetworkXグラフのエッジ定義
edges = [
    (1, 2), (1, 3), (2, 4), (2, 5),
    (3, 5), (4, 6), (5, 6)
]

# RRDファイルマッピング
rrd_paths = {
    (1, 2): '/opt/app/mrtg/mrtg_file/r1-r2.rrd',
    (1, 3): '/opt/app/mrtg/mrtg_file/r1-r3.rrd',
    # ...他のリンク
}
```

## 🔄 最適化後の実行フロー

### 双方向モード（SRv6PathManager）
1. **初期化** → 各機能クラスのインスタンス化
2. **リアルタイムループ**
   - RRDDataManager → エッジ重み更新
   - PathCalculator → r1→r6, r6→r1経路計算
   - RoutingTableManager → TableRouteオブジェクト生成
   - SSHConnectionManager → r1, r6への安全な接続
   - 各ルーターのnftablesテーブル更新
   - 60秒待機 → 次サイクル

### 従来モード（SRv6RealTimeMultiTableManager）
1. **互換性維持** → 既存インターフェース保持
2. **処理委譲** → 各機能を新クラスに委譲
3. **変更検出** → detect_path_changes()による差分管理

## 🎯 最適化されたアルゴリズム

### 責任分離による効果
- **RRDDataManager**: データ取得ロジックの独立性
- **PathCalculator**: 経路計算アルゴリズムの専門化
- **SSHConnectionManager**: 接続管理の安全性向上
- **RoutingTableManager**: テーブル操作の統一化

### エラーハンドリング戦略
- 各クラスレベルでの例外処理
- SSH接続の確実なクリーンアップ
- RRDデータ取得失敗時のフォールバック
