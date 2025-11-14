#!/usr/bin/env python3
"""
Phase 3: SRv6 Multi-Table Network Manager - Simple Version
複数経路計算 → SIDリスト変換 → 各table更新のシンプル実装
"""

import networkx as nx
import paramiko
import logging
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass 
class SRv6Config:
    """SRv6設定"""
    r1_host: str = "fd02:1::2"
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_password: str = "@k@n@3>ki"
    device: str = "eth0"
    timeout: int = 15
    route_prefix: str = "fd01:6::/64"  # r6宛先

@dataclass
class TableRoute:
    """テーブル経路情報"""
    table_name: str
    priority: str  # "高優先度", "中優先度", "低優先度"
    path: List[int]  # ノード経路 [1, 2, 4, 6]
    segments: List[str]  # SIDリスト ["fd01:2::12", "fd01:3::12", "fd01:4::12"]
    cost: float  # 経路コスト

class SRv6MultiTableManager:
    """Phase 3: SRv6多テーブル管理クラス（シンプル版）"""
    
    def __init__(self):
        self.graph = nx.Graph()
        self.config = SRv6Config()
        
        # SRv6セグメントマッピング（main.pyから継承）
        self.srv6_segments = {
            1: {2: "fd01:2::12", 3: "fd01:8::12"},  # r1から
            2: {4: "fd01:3::12", 5: "fd01:9::12"},  # r2から
            3: {5: "fd01:7::12"},                   # r3から
            4: {6: "fd01:4::12"},                   # r4から
            5: {6: "fd01:6::12"},                   # r5から
        }
        
        # テーブル定義（Phase 1で作成済み）
        self.tables = [
            {"name": "rt_table1", "priority": "高優先度", "description": "最短経路優先"},
            {"name": "rt_table2", "priority": "中優先度", "description": "代替経路優先"},
            {"name": "rt_table3", "priority": "低優先度", "description": "バックアップ経路"}
        ]
        
        self._create_topology()
    
    def _create_topology(self):
        """ネットワークトポロジ作成（main.pyと同じ構成）"""
        logger.info("SRv6ネットワークトポロジ作成中...")
        
        # ノード追加 (r1=1, r2=2, r3=3, r4=4, r5=5, r6=6)
        self.graph.add_nodes_from([1, 2, 3, 4, 5, 6])
        
        # エッジ追加（docker-compose.ymlのネットワーク構成）
        edges = [
            (1, 2, {'weight': 1.0}),  # r1-r2
            (1, 3, {'weight': 1.0}),  # r1-r3
            (2, 4, {'weight': 1.0}),  # r2-r4
            (2, 5, {'weight': 1.0}),  # r2-r5
            (3, 5, {'weight': 1.0}),  # r3-r5
            (4, 6, {'weight': 1.0}),  # r4-r6
            (5, 6, {'weight': 1.0}),  # r5-r6
        ]
        
        self.graph.add_edges_from(edges)
        logger.info(f"トポロジ作成完了: {len(self.graph.nodes())}ノード, {len(self.graph.edges())}エッジ")
    
    def calculate_multiple_paths(self, src: int, dst: int, num_paths: int = 3) -> List[Tuple[List[int], float]]:
        """複数経路計算（Dijkstra + エッジ除去法）"""
        logger.info(f"複数経路計算開始: r{src} → r{dst}")
        
        paths = []
        temp_graph = self.graph.copy()
        
        for i in range(num_paths):
            try:
                # 最短経路計算
                path = nx.shortest_path(temp_graph, src, dst, weight='weight')
                cost = nx.shortest_path_length(temp_graph, src, dst, weight='weight')
                
                paths.append((path, cost))
                logger.info(f"経路{i+1}: {' → '.join([f'r{n}' for n in path])} (コスト: {cost:.1f})")
                
                # 次の経路を見つけるため、現在の経路の一部エッジを削除
                if i < num_paths - 1 and len(path) > 1:
                    # 経路の中間エッジを削除（最初のエッジを削除）
                    u, v = path[0], path[1]
                    if temp_graph.has_edge(u, v):
                        temp_graph.remove_edge(u, v)
                        logger.debug(f"エッジ削除: r{u}-r{v}")
                
            except nx.NetworkXNoPath:
                logger.warning(f"経路{i+1}が見つかりません")
                break
            except Exception as e:
                logger.error(f"経路計算エラー: {e}")
                break
        
        return paths
    
    def path_to_sid_list(self, path: List[int]) -> List[str]:
        """経路をSIDリストに変換"""
        sid_list = []
        
        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]
            
            # 現在のノードから次のノードへのセグメントを取得
            if current_node in self.srv6_segments:
                if next_node in self.srv6_segments[current_node]:
                    segment = self.srv6_segments[current_node][next_node]
                    sid_list.append(segment)
                    logger.debug(f"セグメント追加: r{current_node}→r{next_node} = {segment}")
                else:
                    logger.error(f"セグメントが見つかりません: r{current_node}→r{next_node}")
            else:
                logger.error(f"ノード{current_node}のセグメント定義がありません")
        
        return sid_list
    
    def create_table_routes(self, src: int, dst: int) -> List[TableRoute]:
        """複数経路を計算してテーブル経路情報を作成"""
        logger.info(f"=== テーブル経路作成: r{src} → r{dst} ===")
        
        # 複数経路計算
        paths = self.calculate_multiple_paths(src, dst, 3)
        
        table_routes = []
        for i, (path, cost) in enumerate(paths):
            if i >= len(self.tables):
                break
                
            # SIDリスト変換
            sid_list = self.path_to_sid_list(path)
            
            # テーブル経路情報作成
            table_route = TableRoute(
                table_name=self.tables[i]["name"],
                priority=self.tables[i]["priority"],
                path=path,
                segments=sid_list,
                cost=cost
            )
            
            table_routes.append(table_route)
            
            # ログ出力
            path_str = " → ".join([f"r{n}" for n in path])
            logger.info(f"{table_route.table_name} ({table_route.priority}): {path_str}")
            logger.info(f"  SIDリスト: {' → '.join(sid_list)}")
            logger.info(f"  コスト: {cost:.1f}")
        
        return table_routes
    
    @contextmanager
    def ssh_connection(self):
        """SSH接続のコンテキストマネージャー"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            logger.info(f"SSH接続開始: {self.config.r1_host}:{self.config.ssh_port}")
            client.connect(
                hostname=self.config.r1_host,
                port=self.config.ssh_port,
                username=self.config.ssh_user,
                password=self.config.ssh_password,
                timeout=self.config.timeout
            )
            logger.info("r1への SSH接続成功")
            yield client
            
        except Exception as e:
            logger.error(f"SSH接続エラー: {e}")
            raise
        finally:
            client.close()
            logger.info("SSH接続を終了しました")
    
    def execute_command(self, client: paramiko.SSHClient, command: str) -> Tuple[int, str, str]:
        """SSHコマンド実行"""
        try:
            stdin, stdout, stderr = client.exec_command(command)
            rc = stdout.channel.recv_exit_status()
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            
            logger.debug(f"コマンド実行: {command}")
            logger.debug(f"結果 RC={rc}")
            if out:
                logger.debug(f"STDOUT: {out}")
            if err and rc != 0:
                logger.debug(f"STDERR: {err}")
                
            return rc, out, err
            
        except Exception as e:
            logger.error(f"コマンド実行エラー: {e}")
            return 1, "", str(e)
    
    def update_table_route(self, client: paramiko.SSHClient, table_route: TableRoute) -> bool:
        """指定テーブルにSRv6経路を更新"""
        logger.info(f"テーブル経路更新: {table_route.table_name}")
        
        # 既存経路削除（エラーは無視）
        del_cmd = f"ip -6 route del {self.config.route_prefix} table {table_route.table_name}"
        self.execute_command(client, del_cmd)
        
        # 新経路追加
        sid_str = ",".join(table_route.segments)
        add_cmd = (f"ip -6 route add {self.config.route_prefix} "
                  f"encap seg6 mode encap segs {sid_str} "
                  f"dev {self.config.device} table {table_route.table_name}")
        
        rc, out, err = self.execute_command(client, add_cmd)
        
        if rc == 0:
            logger.info(f"✓ {table_route.table_name} 経路更新成功")
            logger.info(f"  SIDリスト: {sid_str}")
            return True
        else:
            logger.error(f"✗ {table_route.table_name} 経路更新失敗: {err}")
            return False
    
    def update_all_tables(self, table_routes: List[TableRoute]) -> bool:
        """全テーブルの経路を更新"""
        logger.info("=== 全テーブル経路更新開始 ===")
        
        try:
            with self.ssh_connection() as client:
                success_count = 0
                
                for table_route in table_routes:
                    if self.update_table_route(client, table_route):
                        success_count += 1
                
                logger.info(f"経路更新完了: {success_count}/{len(table_routes)} 成功")
                return success_count == len(table_routes)
                
        except Exception as e:
            logger.error(f"全テーブル更新エラー: {e}")
            return False
    
    def verify_table_routes(self) -> None:
        """各テーブルの経路確認"""
        logger.info("=== テーブル経路確認 ===")
        
        try:
            with self.ssh_connection() as client:
                for table in self.tables:
                    cmd = f"ip -6 route show table {table['name']}"
                    rc, out, err = self.execute_command(client, cmd)
                    
                    if rc == 0:
                        logger.info(f"{table['name']} ({table['priority']}):")
                        if out.strip():
                            for line in out.split('\n'):
                                if line.strip():
                                    logger.info(f"  {line}")
                        else:
                            logger.info("  経路なし")
                    else:
                        logger.error(f"{table['name']} 確認失敗: {err}")
                        
        except Exception as e:
            logger.error(f"経路確認エラー: {e}")

def main():
    """メイン関数"""
    logger.info("Phase 3: SRv6多テーブル管理（シンプル版）開始")
    
    try:
        # マネージャー初期化
        manager = SRv6MultiTableManager()
        
        # r1からr6への複数経路計算とSIDリスト変換
        table_routes = manager.create_table_routes(src=1, dst=6)
        
        if not table_routes:
            logger.error("経路計算に失敗しました")
            sys.exit(1)
        
        # 各テーブルの経路更新
        if manager.update_all_tables(table_routes):
            logger.info("🎯 Phase 3完了: 全テーブルの経路更新に成功")
            
            # 結果確認
            manager.verify_table_routes()
            
        else:
            logger.error("❌ 一部のテーブル更新に失敗")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Phase 3実行エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
