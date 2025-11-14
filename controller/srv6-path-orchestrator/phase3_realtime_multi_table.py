#!/usr/bin/env python3
"""
Phase 3 Extended: SRv6 Multi-Table Real-time Manager
RRDデータ統合 + リアルタイム監視 + 動的経路選択
phase3_multi_table_simple.py + main.py の統合拡張版
"""

import networkx as nx
import matplotlib.pyplot as plt
import subprocess
import sys
import math
import time
import paramiko
import logging
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
    """SRv6統合設定クラス"""
    # SSH接続設定
    r1_host: str = "fd02:1::2"
    r16_host: str = "fd02:1::11"
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_password: str = "@k@n@3>ki"
    device: str = "eth1"
    timeout: int = 15
    
    # ルーティング設定
    route_prefix: str = "fd03:1::/64"  # r1→r16方向
    return_route_prefix: str = "fd00:1::/64"  # r16→r1方向（復路）
    
    # テーブル定義
    tables: List[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.tables is None:
            self.tables = [
                {"name": "rt_table1", "priority": "高優先度", "description": "高優先度"},
                {"name": "rt_table2", "priority": "中優先度", "description": "中優先度"},
                {"name": "rt_table3", "priority": "低優先度", "description": "低優先度"}
            ]
    
    @property
    def rrd_paths(self) -> Dict[Tuple[int, int], str]:
        """RRDファイルパス設定"""
        return {
            (1, 2): '/opt/app/mrtg/mrtg_file/r1-r2.rrd',
            (1, 3): '/opt/app/mrtg/mrtg_file/r1-r3.rrd',
            (2, 4): '/opt/app/mrtg/mrtg_file/r2-r4.rrd',
            (2, 5): '/opt/app/mrtg/mrtg_file/r2-r5.rrd',
            (3, 5): '/opt/app/mrtg/mrtg_file/r3-r5.rrd',
            (3, 6): '/opt/app/mrtg/mrtg_file/r3-r6.rrd',
            (4, 7): '/opt/app/mrtg/mrtg_file/r4-r7.rrd',
            (4, 8): '/opt/app/mrtg/mrtg_file/r4-r8.rrd',
            (5, 8): '/opt/app/mrtg/mrtg_file/r5-r8.rrd',
            (5, 9): '/opt/app/mrtg/mrtg_file/r5-r9.rrd',
            (6, 9): '/opt/app/mrtg/mrtg_file/r6-r9.rrd',
            (6, 10): '/opt/app/mrtg/mrtg_file/r6-r10.rrd',
            (7, 11): '/opt/app/mrtg/mrtg_file/r7-r11.rrd',
            (8, 11): '/opt/app/mrtg/mrtg_file/r8-r11.rrd',
            (8, 12): '/opt/app/mrtg/mrtg_file/r8-r12.rrd',
            (9, 12): '/opt/app/mrtg/mrtg_file/r9-r12.rrd',
            (9, 13): '/opt/app/mrtg/mrtg_file/r9-r13.rrd',
            (10, 13): '/opt/app/mrtg/mrtg_file/r10-r13.rrd',
            (11, 14): '/opt/app/mrtg/mrtg_file/r11-r14.rrd',
            (12, 14): '/opt/app/mrtg/mrtg_file/r12-r14.rrd',
            (12, 15): '/opt/app/mrtg/mrtg_file/r12-r15.rrd',
            (13, 15): '/opt/app/mrtg/mrtg_file/r13-r15.rrd',
            (14, 16): '/opt/app/mrtg/mrtg_file/r14-r16.rrd',
            (15, 16): '/opt/app/mrtg/mrtg_file/r15-r16.rrd',
        }
    
    @property
    ## インタフェース名が必要なのは、r1とr16のみ
    ## 他の途中ノードのインタフェース名は適当で大丈夫
    def forward_segments(self) -> Dict[int, Dict[int, Tuple[str, str]]]:
        """往路セグメントマッピング"""
        return {
            1: {2: ("fd01:1::12", "eth1"), 3: ("fd01:16::12", "eth2")}, ## インタフェース名重要
            2: {4: ("fd01:2::12", "eth2"), 5: ("fd01:4::12", "eth3")},
            3: {5: ("fd01:17::12","eth0"), 6: ("fd01:15::12", "eth0")},
            4: {7: ("fd01:3::12", "eth2"), 8: ("fd01:6::12", "eth2")},
            5: {8: ("fd01:5::12", "eth3"), 9: ("fd01:12::12", "eth3")},
            6: {9: ("fd01:18::12", "eth3"), 10: ("fd01:14::12", "eth3")},
            7: {11: ("fd01:8::12", "eth3")},
            8: {11: ("fd01:7::12", "eth3"), 12: ("fd01:b::12", "eth3")},
            9: {12: ("fd01:11::12", "eth3"), 13: ("fd01:10::12", "eth3")},
            10: {13: ("fd01:13::12", "eth3")},
            11: {14: ("fd01:9::12", "eth3")},
            12: {14: ("fd01:c::12", "eth3"), 15: ("fd01:d::12", "eth3")},
            13: {15: ("fd01:f::12", "eth3")},
            14: {16: ("fd01:a::12", "eth3")},
            15: {16: ("fd01:e::12", "eth3")},
        }
    
    @property
    def return_segments(self) -> Dict[int, Dict[int, Tuple[str, str]]]:
        """復路セグメントマッピング"""
        return {
            16: {15: ("fd01:e::11", "eth1"), 14: ("fd01:a::11", "eth2")},  ## インタフェース名重要
            15: {13: ("fd01:f::11", "eth1"), 12: ("fd01:d::11", "eth2")},
            14: {12: ("fd01:c::11", "eth3"), 11: ("fd01:9::11", "eth3")},
            13: {10: ("fd01:13::11", "eth3"), 9: ("fd01:10::11", "eth3")},
            12: {9: ("fd01:11::11", "eth3"), 8: ("fd01:b::11", "eth3")},
            11: {8: ("fd01:7::11", "eth3"), 7: ("fd01:8::11", "eth3")},
            10: {6: ("fd01:14::11", "eth3")},
            9: {6: ("fd01:18::11", "eth3"), 5: ("fd01:12::11", "eth3")},
            8: {5: ("fd01:5::11", "eth3"), 4: ("fd01:6::11", "eth3")},
            7: {4: ("fd01:3::11", "eth3")},
            6: {3: ("fd01:15::11", "eth0")},
            5: {3: ("fd01:17::11","eth0"), 2: ("fd01:4::11", "eth3")},
            4: {2: ("fd01:2::11", "eth2")},
            3: {1: ("fd01:16::11", "eth2")},  
            2: {1: ("fd01:1::11", "eth1")},
        }

class RRDDataManager:
    """RRDデータ管理クラス"""
    
    def __init__(self, config: SRv6Config):
        self.config = config
        self.fetch_count = 0
    
    def fetch_rrd_data(self, rrd_path: str) -> Optional[float]:
        """RRDデータ取得"""
        try:
            self.fetch_count += 1
            logger.debug(f"RRDデータ取得: {rrd_path}")
            
            result = subprocess.run(
                ['rrdtool', 'fetch', rrd_path, 'AVERAGE', '--start', '-60s'],
                capture_output=True, text=True, timeout=10
            )
            
            if result.returncode != 0:
                logger.warning(f"RRD取得失敗: {rrd_path} - {result.stderr}")
                return None
            
            lines = result.stdout.strip().split('\n')
            if len(lines) < 3:
                logger.warning(f"RRDデータ不足: {rrd_path}")
                return None
            
            # 最新の有効データを検索
            data_lines = lines[2:]
            for line in reversed(data_lines):
                if ':' in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        val_str = parts[1]
                        if val_str.lower() not in ['-nan', 'nan']:
                            try:
                                val = float(val_str)
                                if not math.isnan(val):
                                    return val
                            except ValueError:
                                continue
            
            return None
            
        except Exception as e:
            logger.error(f"RRDデータ取得エラー ({rrd_path}): {e}")
            return None
    
    def update_edge_weights(self, graph: nx.Graph) -> bool:
        """エッジ重みをRRDデータで更新"""
        logger.info("RRDデータからエッジ重みを更新中...")
        update_count = 0
        
        for u, v in graph.edges():
            edge_key = (u, v) if (u, v) in self.config.rrd_paths else (v, u)
            rrd_path = self.config.rrd_paths.get(edge_key)
            
            if rrd_path:
                out_bps = self.fetch_rrd_data(rrd_path)
                if out_bps is not None:
                    weight_value = out_bps if out_bps > 0 else 0.001
                    graph[u][v]['weight'] = weight_value
                    
                    # 表示用単位変換
                    display_val = round(out_bps * 8 / 1_000_000, 2) if out_bps >= 1000 else round(out_bps, 3)
                    unit = "Mbps" if out_bps >= 1000 else "bps"
                    
                    logger.info(f"Edge r{u} <-> r{v}: {display_val} {unit}")
                    update_count += 1
                else:
                    graph[u][v]['weight'] = 0.001
            else:
                graph[u][v]['weight'] = 0.001
        
        logger.info(f"エッジ重み更新完了: {update_count}/{len(graph.edges())}")
        return update_count > 0

class SRv6PathManager:
    """SRv6双方向パス管理クラス（簡素化版）"""
    
    def __init__(self):
        self.config = SRv6Config()
        self.rrd_manager = RRDDataManager(self.config)
        self.ssh_manager = SSHConnectionManager(self.config)
        self.path_calculator = PathCalculator(self.config)
        self.table_manager = RoutingTableManager(self.config, self.ssh_manager, self.path_calculator)
    
    def get_all_traffic_data(self):
        """RRDトラフィックデータ取得（エッジ重み更新）"""
        success = self.rrd_manager.update_edge_weights(self.path_calculator.graph)
        if success:
            return {"status": "success", "graph": self.path_calculator.graph}
        return None
    
    def calculate_optimal_path(self, traffic_data):
        """最適経路計算"""
        if traffic_data and traffic_data.get("status") == "success":
            paths = self.path_calculator.calculate_multiple_paths(1, 16, 3)
            if paths:
                return paths[0][0]  # 最適経路のノードリストを返す
        return None
    
    def create_table_routes(self, optimal_path):
        """往路テーブルルート生成"""
        return self.table_manager.create_table_routes(optimal_path, is_return=False)
    
    def update_all_tables(self, table_routes):
        """往路テーブル更新"""
        return self.table_manager.update_all_tables(table_routes, is_return=False)
    
    def create_return_table_routes(self, return_optimal_path):
        """復路テーブルルート生成"""
        return self.table_manager.create_table_routes(return_optimal_path, is_return=True)
    
    def update_return_tables(self, return_table_routes):
        """復路テーブル更新"""
        return self.table_manager.update_all_tables(return_table_routes, is_return=True)
    
    def update_bidirectional_tables(self) -> bool:
        """双方向テーブル統合更新メソッド"""
        try:
            logger.info("🚀 双方向テーブル更新開始")
            
            # RRDデータ取得と経路計算
            traffic_data = self.get_all_traffic_data()
            if not traffic_data:
                logger.error("トラフィックデータ取得失敗")
                return False
            
            # 最適経路計算（往路）
            forward_optimal_path = self.calculate_optimal_path(traffic_data)
            if not forward_optimal_path:
                logger.error("往路最適経路計算失敗")
                return False
            
            # 復路最適経路計算（往路の逆順）
            return_optimal_path = forward_optimal_path[::-1]
            
            forward_path_str = ' → '.join([f'r{node}' for node in forward_optimal_path])
            return_path_str = ' → '.join([f'r{node}' for node in return_optimal_path])
            logger.info(f"往路最適経路: {forward_path_str}")
            logger.info(f"復路最適経路: {return_path_str}")
            
            # 往路テーブル生成
            forward_table_routes = self.create_table_routes(forward_optimal_path)
            if not forward_table_routes:
                logger.error("往路テーブル生成失敗")
                return False
            
            # 復路テーブル生成
            return_table_routes = self.create_return_table_routes(return_optimal_path)
            if not return_table_routes:
                logger.error("復路テーブル生成失敗")
                return False
            
            # 往路テーブル更新実行（r1）
            forward_success = self.update_all_tables(forward_table_routes)
            
            # 復路テーブル更新実行（r6）
            return_success = self.update_return_tables(return_table_routes)
            
            # 結果判定
            if forward_success and return_success:
                logger.info("✅ 双方向テーブル更新成功")
                logger.info(f"往路（r1）: {len(forward_table_routes)}テーブル更新完了")
                logger.info(f"復路（r6）: {len(return_table_routes)}テーブル更新完了")
                return True
            else:
                logger.error(f"❌ 双方向テーブル更新失敗 - 往路: {forward_success}, 復路: {return_success}")
                return False
                
        except Exception as e:
            logger.error(f"双方向テーブル更新例外: {e}")
            return False
    
class PathCalculator:
    """経路計算とSIDリスト生成クラス"""
    
    def __init__(self, config: SRv6Config):
        self.config = config
        self.graph = nx.Graph()
        self._create_topology()
    
    def _create_topology(self):
        """ネットワークトポロジ作成"""
        self.graph.add_nodes_from(range(1, 17))  # r1-r16
        edges = [
            (1, 2, {'weight': 0.001}), (1, 3, {'weight': 0.001}),
            (2, 4, {'weight': 0.001}), (2, 5, {'weight': 0.001}),
            (3, 5, {'weight': 0.001}), (3, 6, {'weight': 0.001}),
            (4, 7, {'weight': 0.001}), (4, 8, {'weight': 0.001}),
            (5, 8, {'weight': 0.001}), (5, 9, {'weight': 0.001}),
            (6, 9, {'weight': 0.001}), (6, 10, {'weight': 0.001}),
            (7, 11, {'weight': 0.001}), (8, 11, {'weight': 0.001}),
            (8, 12, {'weight': 0.001}), (9, 12, {'weight': 0.001}),
            (9, 13, {'weight': 0.001}), (10, 13, {'weight': 0.001}),
            (11, 14, {'weight': 0.001}), (12, 14, {'weight': 0.001}),
            (12, 15, {'weight': 0.001}), (13, 15, {'weight': 0.001}),
            (14, 16, {'weight': 0.001}), (15, 16, {'weight': 0.001}),
        ]
        self.graph.add_edges_from(edges)
    
    def calculate_multiple_paths(self, src: int, dst: int, num_paths: int = 3) -> List[Tuple[List[int], float]]:
        """複数経路計算"""
        paths = []
        temp_graph = self.graph.copy()
        
        for i in range(num_paths):
            try:
                path = nx.shortest_path(temp_graph, src, dst, weight='weight')
                cost = nx.shortest_path_length(temp_graph, src, dst, weight='weight')
                paths.append((path, cost))
                
                # 次の経路のためにエッジを削除または重み増加
                if i < num_paths - 1 and len(path) > 2:
                    # 全エッジをループ: 始点・終点エッジは重み1000倍、中間エッジは削除
                    for j in range(len(path) - 1):
                        u, v = path[j], path[j + 1]
                        if temp_graph.has_edge(u, v):
                            # 始点エッジ (j=0) または 終点エッジ (j=len(path)-2): 重みを1000倍
                            if j == 0 or j == len(path) - 2:
                                temp_graph[u][v]['weight'] *= 1000
                            # 中間エッジ: 削除
                            else:
                                temp_graph.remove_edge(u, v)
                elif i < num_paths - 1:
                    # 経路が短い場合は全エッジの重みを1000倍
                    for j in range(len(path) - 1):
                        u, v = path[j], path[j + 1]
                        if temp_graph.has_edge(u, v):
                            temp_graph[u][v]['weight'] *= 1000
                            
            except nx.NetworkXNoPath:
                break
            except Exception as e:
                logger.error(f"経路計算エラー: {e}")
                break
        
        return paths
    
    def path_to_sid_list(self, path: List[int], is_return: bool = False) -> Tuple[List[str], List[str], str]:
        """経路をSIDリストに変換"""
        segment_map = self.config.return_segments if is_return else self.config.forward_segments
        sid_list, interface_list = [], []
        
        for i in range(len(path) - 1):
            current_node, next_node = path[i], path[i + 1]
            if current_node in segment_map and next_node in segment_map[current_node]:
                segment, interface = segment_map[current_node][next_node]
                sid_list.append(segment)
                interface_list.append(interface)
        
        output_interface = interface_list[0] if interface_list else "eth0"
        return sid_list, interface_list, output_interface
    
class SSHConnectionManager:
    """SSH接続管理クラス"""
    
    def __init__(self, config: SRv6Config):
        self.config = config
    
    @contextmanager
    def connection(self, host: str):
        """SSH接続コンテキストマネージャー"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            logger.debug(f"SSH接続開始: {host}")
            client.connect(
                hostname=host,
                port=self.config.ssh_port,
                username=self.config.ssh_user,
                password=self.config.ssh_password,
                timeout=self.config.timeout
            )
            logger.debug(f"SSH接続成功: {host}")
            yield client
        except Exception as e:
            logger.error(f"SSH接続エラー ({host}): {e}")
            raise
        finally:
            client.close()
            logger.debug(f"SSH接続終了: {host}")
    
    @contextmanager
    def r1_connection(self):
        """r1への接続"""
        with self.connection(self.config.r1_host) as client:
            yield client
    
    @contextmanager
    def r16_connection(self):
        """r16への接続"""
        with self.connection(self.config.r16_host) as client:
            yield client
    
    def execute_command(self, client: paramiko.SSHClient, command: str) -> Tuple[int, str, str]:
        """SSHコマンド実行"""
        try:
            stdin, stdout, stderr = client.exec_command(command)
            rc = stdout.channel.recv_exit_status()
            out = stdout.read().decode('utf-8').strip()
            err = stderr.read().decode('utf-8').strip()
            return rc, out, err
        except Exception as e:
            logger.error(f"コマンド実行エラー: {e}")
            return 1, "", str(e)

@dataclass
class TableRoute:
    """テーブル経路情報"""
    table_name: str
    priority: str
    path: List[int]
    segments: List[str]
    interfaces: List[str]  # 各セグメントに対応するインターフェース
    output_interface: str  # 最初のホップで使用するインターフェース
    cost: float
    description: str

@dataclass
class PathChangeEvent:
    """経路変更イベント"""
    timestamp: str
    table_name: str
    old_path: Optional[List[int]]
    new_path: List[int]
    old_segments: Optional[List[str]]
    new_segments: List[str]
    old_interface: Optional[str]
    new_interface: str
    reason: str
    
class RoutingTableManager:
    """ルーティングテーブル管理クラス"""
    
    def __init__(self, config: SRv6Config, ssh_manager: SSHConnectionManager, path_calculator: PathCalculator):
        self.config = config
        self.ssh_manager = ssh_manager
        self.path_calculator = path_calculator
    
    def create_table_routes(self, path: List[int], is_return: bool = False) -> List[TableRoute]:
        """テーブル経路情報作成"""
        paths = self.path_calculator.calculate_multiple_paths(path[0], path[-1], 3)
        table_routes = []
        
        for i, (calculated_path, cost) in enumerate(paths):
            if i >= len(self.config.tables):
                break
            
            sid_list, interface_list, output_interface = self.path_calculator.path_to_sid_list(calculated_path, is_return)
            path_str = " → ".join([f"r{n}" for n in calculated_path])
            
            table_name = self.config.tables[i]["name"]
            if is_return:
                table_name = table_name.replace("rt_table", "rt_table_")
            
            table_route = TableRoute(
                table_name=table_name,
                priority=self.config.tables[i]["priority"],
                path=calculated_path,
                segments=sid_list,
                interfaces=interface_list,
                output_interface=output_interface,
                cost=cost,
                description=f"{path_str} (コスト: {cost:.6f})"
            )
            table_routes.append(table_route)
        
        return table_routes
    
    def clear_table_routes(self, client: paramiko.SSHClient, table_name: str) -> bool:
        """テーブル内の全経路をクリア"""
        try:
            list_cmd = f"ip -6 route show table {table_name}"
            rc, out, err = self.ssh_manager.execute_command(client, list_cmd)
            
            if rc != 0 or not out.strip():
                return True  # テーブルが空の場合は成功
            
            for route_line in out.strip().split('\n'):
                if not route_line.strip():
                    continue
                parts = route_line.strip().split()
                if len(parts) > 0:
                    prefix = parts[0]
                    if '::' in prefix and '/' in prefix:
                        del_cmd = f"ip -6 route del {prefix} table {table_name}"
                        self.ssh_manager.execute_command(client, del_cmd)
            
            return True
        except Exception as e:
            logger.error(f"テーブル {table_name} クリアエラー: {e}")
            return False
    
    def update_table_route(self, client: paramiko.SSHClient, table_route: TableRoute, is_return: bool = False) -> bool:
        """個別テーブル経路更新"""
        try:
            # テーブルクリア
            if not self.clear_table_routes(client, table_route.table_name):
                logger.warning(f"テーブル {table_route.table_name} のクリアに失敗")
            
            # 新経路追加
            if table_route.segments:
                sid_str = ",".join(table_route.segments)
                prefix = self.config.return_route_prefix if is_return else self.config.route_prefix
                add_cmd = (f"ip -6 route add {prefix} "
                          f"encap seg6 mode encap segs {sid_str} "
                          f"dev {table_route.output_interface} table {table_route.table_name}")
                
                rc, out, err = self.ssh_manager.execute_command(client, add_cmd)
                
                if rc == 0:
                    logger.debug(f"✓ {table_route.table_name} 経路更新成功")
                    return True
                else:
                    logger.error(f"✗ {table_route.table_name} 経路更新失敗: {err}")
                    return False
            
            return False
        except Exception as e:
            logger.error(f"テーブル更新エラー {table_route.table_name}: {e}")
            return False
    
    def update_all_tables(self, table_routes: List[TableRoute], is_return: bool = False) -> bool:
        """全テーブル経路更新"""
        try:
            connection_method = self.ssh_manager.r16_connection if is_return else self.ssh_manager.r1_connection
            
            with connection_method() as client:
                success_count = 0
                for table_route in table_routes:
                    if self.update_table_route(client, table_route, is_return):
                        success_count += 1
                
                return success_count == len(table_routes)
        except Exception as e:
            logger.error(f"全テーブル更新エラー: {e}")
            return False

class SRv6RealTimeMultiTableManager:
    """Phase 3拡張版: リアルタイムSRv6多テーブル管理クラス（簡素化版）"""
    
    def __init__(self):
        self.config = SRv6Config()
        self.rrd_manager = RRDDataManager(self.config)
        self.ssh_manager = SSHConnectionManager(self.config)
        self.path_calculator = PathCalculator(self.config)
        self.table_manager = RoutingTableManager(self.config, self.ssh_manager, self.path_calculator)
        
        # 経路変更履歴と統計情報
        self.path_history = []
        self.current_table_routes = {}
        self.stats = {
            'total_updates': 0,
            'path_changes': 0,
            'rrd_fetch_count': 0,
            'last_update': None
        }
        
        logger.info("SRv6リアルタイム多テーブル管理システム初期化完了")
    
    def update_edge_weights(self) -> bool:
        """全エッジの重みをRRDデータで更新"""
        self.stats['rrd_fetch_count'] += self.rrd_manager.fetch_count
        return self.rrd_manager.update_edge_weights(self.path_calculator.graph)
    
    def calculate_multiple_paths(self, src: int, dst: int, num_paths: int = 3) -> List[Tuple[List[int], float]]:
        """複数経路計算（委譲）"""
        return self.path_calculator.calculate_multiple_paths(src, dst, num_paths)
    
    def path_to_sid_list(self, path: List[int]) -> Tuple[List[str], List[str], str]:
        """経路をSIDリストに変換（委譲）"""
        return self.path_calculator.path_to_sid_list(path, is_return=False)
    
    def create_table_routes(self, src: int, dst: int) -> List[TableRoute]:
        """テーブル経路情報作成（委譲）"""
        return self.table_manager.create_table_routes([src, dst], is_return=False)
    
    def create_return_table_routes(self, return_path: List[int]) -> List[TableRoute]:
        """復路テーブル経路情報作成（委譲）"""
        return self.table_manager.create_table_routes(return_path, is_return=True)
    
    def detect_path_changes(self, new_routes: List[TableRoute]) -> List[PathChangeEvent]:
        """経路変更の検出"""
        changes = []
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        for new_route in new_routes:
            table_name = new_route.table_name
            old_route = self.current_table_routes.get(table_name)
            
            if old_route is None:
                # 初回設定
                changes.append(PathChangeEvent(
                    timestamp=timestamp,
                    table_name=table_name,
                    old_path=None,
                    new_path=new_route.path,
                    old_segments=None,
                    new_segments=new_route.segments,
                    old_interface=None,
                    new_interface=new_route.output_interface,
                    reason="初回設定"
                ))
            elif (old_route.path != new_route.path or 
                  old_route.output_interface != new_route.output_interface):
                # 経路またはインターフェース変更
                reason = []
                if old_route.path != new_route.path:
                    reason.append("経路変更")
                if old_route.output_interface != new_route.output_interface:
                    reason.append("出力IF変更")
                
                changes.append(PathChangeEvent(
                    timestamp=timestamp,
                    table_name=table_name,
                    old_path=old_route.path,
                    new_path=new_route.path,
                    old_segments=old_route.segments,
                    new_segments=new_route.segments,
                    old_interface=old_route.output_interface,
                    new_interface=new_route.output_interface,
                    reason="負荷変動による" + "・".join(reason)
                ))
        
        return changes
    
    # SSH接続は委譲
    @property
    def graph(self):
        """グラフプロパティ（後方互換性のため）"""
        return self.path_calculator.graph
    
    def update_all_tables(self, table_routes: List[TableRoute]) -> bool:
        """全テーブル経路更新（委譲）"""
        success = self.table_manager.update_all_tables(table_routes, is_return=False)
        # 現在の経路を記録
        for table_route in table_routes:
            self.current_table_routes[table_route.table_name] = table_route
        return success
    
    def update_return_tables(self, return_routes: List[TableRoute]) -> bool:
        """復路全テーブル経路更新（委譲）"""
        return self.table_manager.update_all_tables(return_routes, is_return=True)
    
    def get_all_traffic_data(self):
        """RRDトラフィックデータ取得（後方互換性のため）"""
        success = self.rrd_manager.update_edge_weights(self.path_calculator.graph)
        if success:
            return {"status": "success", "graph": self.path_calculator.graph}
        return None
    
    def calculate_optimal_path(self, traffic_data):
        """最適経路計算（後方互換性のため）"""
        if traffic_data and traffic_data.get("status") == "success":
            paths = self.path_calculator.calculate_multiple_paths(1, 16, 3)
            if paths:
                return paths[0][0]  # 最適経路のノードリストを返す
        return None
    
    def log_path_changes(self, changes: List[PathChangeEvent]):
        """経路変更ログ出力（インターフェース情報含む）"""
        for change in changes:
            self.path_history.append(change)
            self.stats['path_changes'] += 1
            
            if change.old_path is None:
                logger.info(f"🆕 {change.table_name}: 初回経路設定")
                logger.info(f"   経路: {' → '.join([f'r{n}' for n in change.new_path])}")
                logger.info(f"   SID: {' → '.join(change.new_segments)}")
                logger.info(f"   出力IF: {change.new_interface}")
            else:
                logger.info(f"🔄 {change.table_name}: 経路変更検出")
                logger.info(f"   旧: {' → '.join([f'r{n}' for n in change.old_path])} (IF: {change.old_interface})")
                logger.info(f"   新: {' → '.join([f'r{n}' for n in change.new_path])} (IF: {change.new_interface})")
                logger.info(f"   理由: {change.reason}")
    
    def display_status(self, iteration: int):
        """現在の状態表示"""
        logger.info(f"=== 更新サイクル {iteration} ===")
        logger.info(f"統計情報:")
        logger.info(f"  総更新回数: {self.stats['total_updates']}")
        logger.info(f"  経路変更回数: {self.stats['path_changes']}")
        logger.info(f"  RRD取得回数: {self.stats['rrd_fetch_count']}")
        
        # 現在のエッジ重み表示
        logger.info("現在のエッジ重み:")
        for u, v, data in self.graph.edges(data=True):
            weight = data.get('weight', 0.001)
            if weight > 0.1:
                unit = f"{weight:.1f} (高負荷)" 
            else:
                unit = f"{weight:.6f} (デフォルト)"
            logger.info(f"  r{u} <-> r{v}: {unit}")
    
    def real_time_monitor(self, src: int = 1, dst: int = 16, update_interval: int = 60):
        """リアルタイム監視メイン関数"""
        logger.info(f"リアルタイム監視開始: r{src} → r{dst} (更新間隔: {update_interval}秒)")
        logger.info(f"📊 RRDファイル更新間隔: 60秒 - 最適な監視間隔で実行中")
        
        iteration = 0
        
        try:
            while True:
                iteration += 1
                start_time = time.time()
                
                self.display_status(iteration)
                
                # RRDデータでエッジ重み更新
                if self.update_edge_weights():
                    logger.info("エッジ重み更新完了")
                else:
                    logger.warning("エッジ重み更新に失敗")
                
                # 新しい経路計算
                new_routes = self.create_table_routes(src, dst)
                
                if new_routes:
                    # 経路変更検出
                    changes = self.detect_path_changes(new_routes)
                    
                    if changes:
                        logger.info(f"📊 {len(changes)}件の経路変更を検出")
                        self.log_path_changes(changes)
                        
                        # 経路更新実行
                        if self.update_all_tables(new_routes):
                            logger.info("✅ 全テーブル経路更新成功")
                        else:
                            logger.error("❌ 一部テーブル更新失敗")
                    else:
                        logger.info("✅ 経路変更なし")
                    
                    # 現在の経路情報表示
                    logger.info("現在のテーブル経路:")
                    for route in new_routes:
                        logger.info(f"  {route.table_name}: {route.description}")
                        logger.info(f"    SID: {' → '.join(route.segments)}")
                        logger.info(f"    出力IF: {route.output_interface}")
                else:
                    logger.error("❌ 経路計算に失敗")
                
                # 統計更新
                self.stats['total_updates'] += 1
                self.stats['last_update'] = time.strftime('%Y-%m-%d %H:%M:%S')
                
                # 次回更新まで待機
                elapsed = time.time() - start_time
                sleep_time = max(0, update_interval - elapsed)
                logger.info(f"次回更新まで {sleep_time:.1f} 秒待機... (処理時間: {elapsed:.1f}秒)")
                logger.info("=" * 80)
                
                time.sleep(sleep_time)
                
        except KeyboardInterrupt:
            logger.info("監視を停止します...")
            self.display_final_stats()
        except Exception as e:
            logger.error(f"監視エラー: {e}")
    
    def display_final_stats(self):
        """最終統計表示"""
        logger.info("=== 最終統計情報 ===")
        logger.info(f"総更新回数: {self.stats['total_updates']}")
        logger.info(f"経路変更回数: {self.stats['path_changes']}")
        logger.info(f"RRD取得回数: {self.stats['rrd_fetch_count']}")
        logger.info(f"最終更新: {self.stats['last_update']}")
        
        if self.path_history:
            logger.info("経路変更履歴:")
            for change in self.path_history[-5:]:  # 最新5件
                logger.info(f"  {change.timestamp}: {change.table_name} - {change.reason}")

def main():
    """メイン関数"""
    import argparse
    
    parser = argparse.ArgumentParser(description="SRv6双方向リアルタイム多テーブル管理")
    parser.add_argument("--mode", type=str, default="bidirectional", choices=["bidirectional", "forward", "analyze"],
                        help="実行モード: bidirectional(双方向), forward(往路のみ), analyze(分析のみ)")
    parser.add_argument("--src", type=int, default=1, help="送信元ノード")
    parser.add_argument("--dst", type=int, default=16, help="宛先ノード")
    parser.add_argument("--interval", type=int, default=60, help="更新間隔（秒）- RRD更新間隔に合わせて60秒推奨")
    parser.add_argument("--once", action="store_true", help="1回のみ実行")
    
    args = parser.parse_args()
    
    logger.info("Phase 3拡張版: SRv6双方向リアルタイム多テーブル管理開始")
    
    try:
        if args.mode == "bidirectional":
            # 双方向管理（新実装）
            manager = SRv6PathManager()
            
            if args.once:
                logger.info("双方向1回のみ実行モード")
                success = manager.update_bidirectional_tables()
                if success:
                    logger.info("✅ 双方向テーブル更新成功")
                else:
                    logger.error("❌ 双方向テーブル更新失敗")
            else:
                # 双方向リアルタイム監視
                logger.info(f"双方向リアルタイム監視開始（間隔: {args.interval}秒）")
                while True:
                    success = manager.update_bidirectional_tables()
                    if success:
                        logger.info("✅ 双方向テーブル更新完了")
                    else:
                        logger.error("❌ 双方向テーブル更新失敗")
                    time.sleep(args.interval)
                    
        elif args.mode == "analyze":
            # トラフィック分析モード
            manager = SRv6PathManager()
            traffic_data = manager.get_all_traffic_data()
            if traffic_data:
                optimal_path = manager.calculate_optimal_path(traffic_data)
                if optimal_path:
                    forward_path_str = ' → '.join([f'r{node}' for node in optimal_path])
                    return_path_str = ' → '.join([f'r{node}' for node in optimal_path[::-1]])
                    logger.info(f"往路最適経路: {forward_path_str}")
                    logger.info(f"復路最適経路: {return_path_str}")
                else:
                    logger.error("最適経路計算失敗")
            else:
                logger.error("トラフィックデータ取得失敗")
                
        elif args.mode == "forward":
            # 往路のみ（従来実装との互換性）
            manager = SRv6RealTimeMultiTableManager()
            
            if args.once:
                # 往路1回のみ実行
                logger.info("往路1回のみ実行モード")
                manager.update_edge_weights()
                routes = manager.create_table_routes(args.src, args.dst)
                if routes:
                    changes = manager.detect_path_changes(routes)
                    if changes:
                        manager.log_path_changes(changes)
                    manager.update_all_tables(routes)
                logger.info("往路実行完了")
            else:
                # 往路リアルタイム監視
                manager.real_time_monitor(args.src, args.dst, args.interval)
            
    except Exception as e:
        logger.error(f"実行エラー: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
