#!/usr/bin/env python3
"""
SRv6 Network Topology Manager - Phase 2
docker-compose.ymlのr1～r6ルーターのトポロジをNetworkXで管理
RRDデータ統合と動的重み更新機能付き
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
from typing import Optional, Tuple, List

# RRDファイルのパス設定（リンク単位で管理）
RRD_PATHS = {
    (1, 2): '/opt/app/mrtg/mrtg_file/r1-r2.rrd',  # r1→r2リンク
    (1, 3): '/opt/app/mrtg/mrtg_file/r1-r3.rrd',  # r1→r3リンク  
    (2, 4): '/opt/app/mrtg/mrtg_file/r2-r4.rrd',  # r2→r4リンク
    (2, 5): '/opt/app/mrtg/mrtg_file/r2-r5.rrd',  # r2→r5リンク
    (3, 5): '/opt/app/mrtg/mrtg_file/r3-r5.rrd',  # r3→r5リンク
    (4, 6): '/opt/app/mrtg/mrtg_file/r4-r6.rrd',  # r4→r6リンク
    (5, 6): '/opt/app/mrtg/mrtg_file/r5-r6.rrd',  # r5→r6リンク
}

# SRv6ノードのアドレスマッピング（ホップ毎のSRv6セグメントアドレス）
SRV6_SEGMENT_MAP = {
    1: {  # r1から出る場合のセグメント
        2: "fd01:2::12",  # r1→r2へのセグメント
        3: "fd01:8::12",  # r1→r3へのセグメント
    },
    2: {  # r2から出る場合のセグメント
        4: "fd01:3::12",  # r2→r4へのセグメント
        5: "fd01:9::12",  # r2→r5へのセグメント
    },
    3: {  # r3から出る場合のセグメント
        5: "fd01:7::12",  # r3→r5へのセグメント
    },
    4: {  # r4から出る場合のセグメント
        6: "fd01:4::12",  # r4→r6へのセグメント
    },
    5: {  # r5から出る場合のセグメント
        6: "fd01:6::12",  # r5→r6へのセグメント
    }
}

# SRv6ルート管理設定
@dataclass
class SRv6RouteConfig:
    """SRv6ルート設定"""
    r1_host: str = "fd02:1::2"  # r1のIPアドレス
    ssh_port: int = 22
    ssh_user: str = "root"
    ssh_password: str = "@k@n@3>ki"
    device: str = "eth0"
    timeout: int = 15
    route_prefix: str = "fd01:6::/64"  # r6宛先のプレフィックス

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
srv6_logger = logging.getLogger('srv6_route')

# ノードの固定位置（6ノードのレイアウト）
NODE_POSITIONS = {
    1: (0, 2),    # r1 - 左上
    2: (1, 1),    # r2 - 中央左
    3: (1, 3),    # r3 - 中央上
    4: (2, 0),    # r4 - 右下
    5: (2, 2),    # r5 - 右中央
    6: (3, 1),    # r6 - 右
}

class SRv6NetworkTopology:
    """SRv6ネットワークトポロジ管理クラス - Phase 2（RRDデータ統合版）"""
    
    def __init__(self):
        self.graph = nx.Graph()
        self.srv6_config = SRv6RouteConfig()
        self._create_topology()
        
    def _create_topology(self):
        """docker-compose.ymlに基づいてトポロジを作成"""
        print("Creating SRv6 network topology...")
        
        # 実装内容1: ノード（ルーター）を追加
        # 1=r1, 2=r2, 3=r3, 4=r4, 5=r5, 6=r6
        self.graph.add_nodes_from([1, 2, 3, 4, 5, 6])
        print(f"Added nodes: {list(self.graph.nodes())}")
        
        # 実装内容3: エッジ（ネットワーク接続）を追加
        # docker-compose.ymlのnetworks設定に基づく
        edges = [
            (1, 2),  # r1-r2: fd01:2::/64
            (1, 3),  # r1-r3: fd01:8::/64
            (2, 4),  # r2-r4: fd01:3::/64
            (2, 5),  # r2-r5: fd01:9::/64
            (3, 5),  # r3-r5: fd01:7::/64
            (4, 6),  # r4-r6: fd01:4::/64
            (5, 6),  # r5-r6: fd01:6::/64
        ]
        
        # 初期重みを0.0として追加（RRDデータで更新される）
        self.graph.add_weighted_edges_from([(u, v, 0.0) for u, v in edges])
        print(f"Added edges: {list(self.graph.edges())}")
        
        print(f"Topology created with {self.graph.number_of_nodes()} nodes and {self.graph.number_of_edges()} edges")

    def fetch_rrd_data(self, rrd_path):
        """RRDファイルから最新の有効なアウトプットデータを取得
        main_node_num_3.pyのfetch_last_valid_out関数を参考
        """
        print(f"  DEBUG: Fetching data from {rrd_path}")
        try:
            output = subprocess.check_output(
                ['rrdtool', 'fetch', rrd_path, 'LAST', '-s', '-120'],
                stderr=subprocess.STDOUT,
                text=True
            )
        except subprocess.CalledProcessError as e:
            print(f"rrdtool error for {rrd_path}:\n{e.output}", file=sys.stderr)
            return None

        print(f"  DEBUG: RRD output preview:")
        lines = output.splitlines()
        for i, line in enumerate(lines[:5]):  # 最初の5行を表示
            print(f"    Line {i}: {line}")
        
        # タイムスタンプ行だけ抽出
        data_lines = [line for line in output.splitlines() if line and line[0].isdigit()]
        print(f"  DEBUG: Found {len(data_lines)} data lines")
        
        if data_lines:
            print(f"  DEBUG: Last few data lines:")
            for line in data_lines[-3:]:  # 最後の3行を表示
                print(f"    {line}")

        # 末尾からさかのぼって最初に nan でない out 値を探す
        for line in reversed(data_lines):
            val_str = line.split()[-1]
            print(f"  DEBUG: Checking value: '{val_str}'")
            try:
                val = float(val_str)
            except ValueError:
                print(f"  DEBUG: Could not convert '{val_str}' to float")
                continue
            if not math.isnan(val):
                print(f"  DEBUG: Found valid value: {val}")
                return val
            else:
                print(f"  DEBUG: Value is NaN: {val}")

        # 有効なデータ見つからず
        print(f"  DEBUG: No valid data found in {rrd_path}")
        return None

    def update_edge_weights(self):
        """全エッジの重みをRRDデータで更新
        新方式: 各リンク専用のRRDファイルから重みを取得
        """
        print("Updating edge weights from link-specific RRD data...")
        
        # 各エッジに対して対応するRRDファイルから重みを取得
        for u, v in self.graph.edges():
            # エッジに対応するRRDファイルを取得
            edge_key = (u, v) if (u, v) in RRD_PATHS else (v, u)
            rrd_path = RRD_PATHS.get(edge_key)
            
            if rrd_path:
                out_bps = self.fetch_rrd_data(rrd_path)
                if out_bps is not None:
                    print(f"  DEBUG: Raw RRD value for edge r{u}<->r{v}: {out_bps} (from {rrd_path})")
                    
                    # 単位を確認して適切に変換
                    if out_bps < 1000:
                        # 小さい値の場合は、そのまま表示
                        mbps = round(out_bps, 3)
                        unit = "bps"
                    else:
                        # 大きい値はMbpsに変換
                        mbps = round(out_bps * 8 / 1_000_000, 2)
                        unit = "Mbps"
                    
                    # エッジの重みを更新（計算に使用するための値）
                    weight_value = out_bps if out_bps > 0 else 0.001  # 0を避けるため
                    self.graph[u][v]['weight'] = weight_value
                    print(f"Edge r{u} <-> r{v} weight updated to: {mbps} {unit} (internal: {weight_value})")
                else:
                    print(f"Failed to get RRD data for edge r{u} <-> r{v} from {rrd_path}")
            else:
                print(f"No RRD path configured for edge r{u} <-> r{v}")
                # デフォルト値を設定
                self.graph[u][v]['weight'] = 0.001

    def find_shortest_path(self, source, target):
        """指定されたノード間の最短経路を計算
        
        Args:
            source (int): 送信元ノード（1-6）
            target (int): 宛先ノード（1-6）
            
        Returns:
            tuple: (経路のノードリスト, 総コスト)
        """
        try:
            path = nx.shortest_path(self.graph, source, target, weight='weight')
            cost = nx.shortest_path_length(self.graph, source, target, weight='weight')
            return path, cost
        except nx.NetworkXNoPath:
            print(f"No path found between r{source} and r{target}")
            return None, None
        except nx.NodeNotFound as e:
            print(f"Node not found: {e}")
            return None, None

    def calculate_all_shortest_paths(self):
        """全ノードペア間の最短経路を計算
        
        Returns:
            dict: {(source, target): (path, cost)} の辞書
        """
        all_paths = {}
        all_costs = {}
        
        try:
            # 全ペア間の最短経路を計算
            paths = dict(nx.all_pairs_dijkstra_path(self.graph, weight='weight'))
            costs = dict(nx.all_pairs_dijkstra_path_length(self.graph, weight='weight'))
            
            # 結果を整理
            for source in self.graph.nodes():
                for target in self.graph.nodes():
                    if source != target:
                        all_paths[(source, target)] = (paths[source][target], costs[source][target])
                        
        except Exception as e:
            print(f"Error calculating shortest paths: {e}")
            
        return all_paths

    def print_shortest_path_info(self, source=None, target=None):
        """最短経路情報を表示
        
        Args:
            source (int, optional): 特定の送信元。Noneの場合は全ペア表示
            target (int, optional): 特定の宛先。Noneの場合は全ペア表示
        """
        print("\n=== Shortest Path Analysis ===")
        
        if source is not None and target is not None:
            # 特定のペアの経路を表示
            path, cost = self.find_shortest_path(source, target)
            if path:
                path_str = " -> ".join([f"r{node}" for node in path])
                print(f"r{source} to r{target}: {path_str}")
                print(f"Total cost: {cost:.3f}")
                print(f"Hops: {len(path) - 1}")
            else:
                print(f"No path available between r{source} and r{target}")
        else:
            # 全ペアの経路を表示
            all_paths = self.calculate_all_shortest_paths()
            
            if not all_paths:
                print("No paths calculated")
                return
                
            print("All pairs shortest paths:")
            print("-" * 60)
            
            for (src, dst), (path, cost) in sorted(all_paths.items()):
                path_str = " -> ".join([f"r{node}" for node in path])
                print(f"r{src} to r{dst}: {path_str} (cost: {cost:.3f}, hops: {len(path)-1})")

    def get_path_statistics(self):
        """ネットワーク全体の経路統計を計算
        
        Returns:
            dict: 統計情報の辞書
        """
        all_paths = self.calculate_all_shortest_paths()
        
        if not all_paths:
            return {}
            
        costs = [cost for (path, cost) in all_paths.values()]
        hops = [len(path) - 1 for (path, cost) in all_paths.values()]
        
        stats = {
            'total_pairs': len(all_paths),
            'avg_cost': sum(costs) / len(costs) if costs else 0,
            'min_cost': min(costs) if costs else 0,
            'max_cost': max(costs) if costs else 0,
            'avg_hops': sum(hops) / len(hops) if hops else 0,
            'min_hops': min(hops) if hops else 0,
            'max_hops': max(hops) if hops else 0,
        }
        
        return stats

    def print_path_statistics(self):
        """経路統計情報を表示"""
        stats = self.get_path_statistics()
        
        if not stats:
            print("No path statistics available")
            return
            
        print("\n=== Network Path Statistics ===")
        print(f"Total node pairs: {stats['total_pairs']}")
        print(f"Average path cost: {stats['avg_cost']:.3f}")
        print(f"Cost range: {stats['min_cost']:.3f} - {stats['max_cost']:.3f}")
        print(f"Average hops: {stats['avg_hops']:.1f}")
        print(f"Hop range: {stats['min_hops']} - {stats['max_hops']}")

    def path_to_srv6_segments(self, path: List[int]) -> Optional[str]:
        """経路をSRv6セグメントリストに変換
        
        Args:
            path (List[int]): ノードの経路リスト（例: [1, 2, 5, 6]）
            
        Returns:
            Optional[str]: SRv6セグメントリスト（例: "fd01:2::12,fd01:9::12,fd01:6::12"）
        """
        if not path or len(path) < 2:
            srv6_logger.warning(f"Invalid path for SRv6 conversion: {path}")
            return None
            
        segments = []
        
        # 各ホップでのセグメントを生成
        for i in range(len(path) - 1):
            current_node = path[i]
            next_node = path[i + 1]
            
            # SRv6セグメントマップから対応するセグメントを取得
            if current_node in SRV6_SEGMENT_MAP and next_node in SRV6_SEGMENT_MAP[current_node]:
                segment = SRV6_SEGMENT_MAP[current_node][next_node]
                segments.append(segment)
                srv6_logger.debug(f"r{current_node}→r{next_node}: {segment}")
            else:
                srv6_logger.error(f"No SRv6 segment mapping for r{current_node}→r{next_node}")
                return None
        
        if segments:
            segment_list = ",".join(segments)
            srv6_logger.info(f"Path {path} converted to SRv6 segments: {segment_list}")
            return segment_list
        
        srv6_logger.error(f"Failed to convert path {path} to SRv6 segments")
        return None
    
    @contextmanager
    def ssh_connection_to_r1(self):
        """r1へのSSH接続コンテキストマネージャー"""
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            srv6_logger.info(f"SSH接続開始: {self.srv6_config.r1_host}:{self.srv6_config.ssh_port}")
            client.connect(
                hostname=self.srv6_config.r1_host,
                port=self.srv6_config.ssh_port,
                username=self.srv6_config.ssh_user,
                password=self.srv6_config.ssh_password,
                timeout=self.srv6_config.timeout
            )
            srv6_logger.info("r1への SSH接続成功")
            yield client
                
        except Exception as e:
            srv6_logger.error(f"SSH接続失敗: {e}")
            raise
        finally:
            client.close()
            srv6_logger.debug("SSH接続を閉じました")
    
    def execute_ssh_command(self, client: paramiko.SSHClient, cmd: str) -> Tuple[int, str, str]:
        """SSHコマンドを実行"""
        srv6_logger.debug(f"コマンド実行: {cmd}")
        stdin, stdout, stderr = client.exec_command(cmd)
        
        out = stdout.read().decode("utf-8", errors="replace").strip()
        err = stderr.read().decode("utf-8", errors="replace").strip()
        rc = stdout.channel.recv_exit_status()
        
        srv6_logger.debug(f"実行結果: RC={rc}, OUT='{out}', ERR='{err}'")
        return rc, out, err
    
    def check_existing_srv6_route(self, client: paramiko.SSHClient) -> Optional[str]:
        """既存のSRv6経路をチェック"""
        show_cmd = f"ip -6 route show {self.srv6_config.route_prefix}"
        rc, out, err = self.execute_ssh_command(client, show_cmd)
        
        if rc != 0 or not out:
            srv6_logger.info(f"既存のSRv6経路なし: {self.srv6_config.route_prefix}")
            return None
            
        # SRv6経路の検証
        normalized = " ".join(out.split())
        required_tokens = ["seg6", "segs", "dev", self.srv6_config.device]
        
        if all(token in normalized for token in required_tokens):
            srv6_logger.info(f"既存のSRv6経路を検出: {out}")
            return out
        
        srv6_logger.warning(f"予期しない経路形式: {out}")
        return out
    
    def delete_existing_srv6_route(self, client: paramiko.SSHClient) -> bool:
        """既存のSRv6経路を削除"""
        del_cmd = f"ip -6 route del {self.srv6_config.route_prefix}"
        rc, out, err = self.execute_ssh_command(client, del_cmd)
        
        if rc == 0:
            srv6_logger.info("既存のSRv6経路を削除しました")
            return True
        
        if "No such file or directory" in err or "not found" in err.lower():
            srv6_logger.info("削除対象のSRv6経路が見つかりませんでした")
            return True
        
        srv6_logger.error(f"SRv6経路削除失敗 (RC={rc}): {err}")
        return False
    
    def apply_srv6_route_to_r1(self, path: List[int], force_update: bool = True) -> bool:
        """r1にSRv6経路を適用
        
        Args:
            path (List[int]): 適用する経路のノードリスト
            force_update (bool): 既存経路を強制更新するか
            
        Returns:
            bool: 成功/失敗
        """
        if not path or path[0] != 1:
            srv6_logger.error(f"Invalid path for r1: {path} (must start with node 1)")
            return False
        
        # 経路をSRv6セグメントに変換
        segment_list = self.path_to_srv6_segments(path)
        if not segment_list:
            srv6_logger.error(f"Failed to convert path to SRv6 segments: {path}")
            return False
        
        try:
            with self.ssh_connection_to_r1() as client:
                # 既存経路をチェック
                existing_route = self.check_existing_srv6_route(client)
                
                if existing_route and not force_update:
                    srv6_logger.info("既存のSRv6経路が存在します。force_update=Falseのため、スキップします")
                    return True
                
                if existing_route and force_update:
                    srv6_logger.info("既存のSRv6経路を削除してから新しい経路を追加します")
                    if not self.delete_existing_srv6_route(client):
                        srv6_logger.error("既存のSRv6経路削除に失敗")
                        return False
                
                # 新しいSRv6経路を追加
                add_cmd = (
                    f"ip -6 route add {self.srv6_config.route_prefix} "
                    f"encap seg6 mode encap segs {segment_list} "
                    f"dev {self.srv6_config.device}"
                )
                
                srv6_logger.info(f"SRv6経路を追加中: {add_cmd}")
                rc, out, err = self.execute_ssh_command(client, add_cmd)
                
                if rc == 0:
                    srv6_logger.info(f"✓ SRv6経路を正常に追加しました")
                    srv6_logger.info(f"  経路: {' -> '.join([f'r{n}' for n in path])}")
                    srv6_logger.info(f"  セグメント: {segment_list}")
                    
                    # 追加後の確認
                    verification = self.check_existing_srv6_route(client)
                    if verification:
                        srv6_logger.info(f"✓ SRv6経路設定確認済み: {verification}")
                        return True
                    else:
                        srv6_logger.error("SRv6経路の設定確認に失敗")
                        return False
                
                # エラーハンドリング
                if "File exists" in err or "exists" in err.lower():
                    srv6_logger.info("SRv6経路は既に存在します")
                    return True
                
                srv6_logger.error(f"✗ SRv6経路追加失敗 (RC={rc}): {err}")
                return False
                
        except Exception as e:
            srv6_logger.error(f"SRv6経路適用中にエラー: {e}")
            return False
    
    def draw_topology(self, save_path=None, highlight_path=None):
        """ネットワークトポロジを描画（更新版）
        
        Args:
            save_path (str, optional): 保存パス
            highlight_path (list, optional): ハイライトする経路のノードリスト
        """
        plt.figure(figsize=(12, 8))
        plt.clf()  # 図をクリア
        
        # ノードを描画
        nx.draw_networkx_nodes(
            self.graph, 
            NODE_POSITIONS, 
            node_size=1000, 
            node_color='lightblue',
            edgecolors='black',
            linewidths=2
        )
        
        # 通常のエッジを描画
        edge_colors = []
        edge_widths = []
        
        for u, v in self.graph.edges():
            if highlight_path and len(highlight_path) > 1:
                # ハイライト経路のエッジかチェック
                is_highlight = False
                for i in range(len(highlight_path) - 1):
                    if (u == highlight_path[i] and v == highlight_path[i+1]) or \
                       (v == highlight_path[i] and u == highlight_path[i+1]):
                        is_highlight = True
                        break
                
                if is_highlight:
                    edge_colors.append('red')
                    edge_widths.append(4)
                else:
                    edge_colors.append('gray')
                    edge_widths.append(2)
            else:
                edge_colors.append('gray')
                edge_widths.append(2)
        
        nx.draw_networkx_edges(
            self.graph, 
            NODE_POSITIONS, 
            width=edge_widths,
            edge_color=edge_colors
        )
        
        # 実装内容2: ノードラベル（r1, r2, ...）を描画
        node_labels = {i: f"r{i}" for i in self.graph.nodes()}
        nx.draw_networkx_labels(
            self.graph, 
            NODE_POSITIONS, 
            labels=node_labels,
            font_size=14,
            font_weight='bold'
        )
        
        # エッジラベル（重み）を描画 - RRDデータを反映
        edge_labels = {}
        for u, v, d in self.graph.edges(data=True):
            weight = d['weight']
            if weight < 1000:
                edge_labels[(u, v)] = f"{weight:.3f}"
            else:
                # 大きい値はMbpsに変換して表示
                mbps = round(weight * 8 / 1_000_000, 2)
                edge_labels[(u, v)] = f"{mbps} Mbps"
        
        nx.draw_networkx_edge_labels(
            self.graph, 
            NODE_POSITIONS, 
            edge_labels=edge_labels,
            font_size=10
        )
        
        # タイトルを更新（ハイライト情報含む）
        title = "SRv6 Network Topology (r1-r6) - Phase 2 with RRD Data"
        if highlight_path:
            path_str = " -> ".join([f"r{node}" for node in highlight_path])
            title += f"\nHighlighted Path: {path_str}"
        
        plt.title(title, fontsize=16, fontweight='bold')
        plt.axis('off')
        
        if save_path:
            plt.savefig(save_path, dpi=300, bbox_inches='tight')
            print(f"Topology saved to: {save_path}")
        
        plt.pause(0.1)  # 描画を更新

    def print_topology_info(self):
        """トポロジ情報を表示（更新版）"""
        print("\n=== SRv6 Network Topology Information ===")
        print(f"Nodes: {self.graph.number_of_nodes()}")
        print(f"Edges: {self.graph.number_of_edges()}")
        
        print("\nNode mappings:")
        for i in range(1, 7):
            print(f"  Node {i} -> r{i}")
            
        print("\nCurrent edge weights (from RRD data):")
        for u, v, d in self.graph.edges(data=True):
            weight = d['weight']
            if weight < 1000:
                print(f"  r{u} <-> r{v}: {weight:.3f}")
            else:
                mbps = round(weight * 8 / 1_000_000, 2)
                print(f"  r{u} <-> r{v}: {mbps} Mbps (raw: {weight})")

def main():
    """メイン実行関数 - Phase 2（RRDデータ統合版）"""
    print("Starting SRv6 Network Topology Manager - Phase 2...")
    
    # トポロジインスタンスを作成
    topology = SRv6NetworkTopology()
    
    # 初期トポロジ情報を表示
    topology.print_topology_info()
    
    # 初回のRRDデータ更新
    print("\n=== Initial RRD Data Update ===")
    topology.update_edge_weights()
    
    # 初期描画
    plt.ion()  # インタラクティブモードON
    topology.draw_topology(save_path="/opt/app/mrtg/mrtg_file/srv6_network_topology_phase2.png")
    
    # 更新後の情報を表示
    topology.print_topology_info()
    
    # Phase 1: 最短経路機能のデモンストレーション
    print("\n=== Phase 1: r1 to r6 Path Analysis Demo ===")
    
    # r1からr6の最短経路を表示
    print("\n--- r1 to r6 Path Analysis ---")
    topology.print_shortest_path_info(1, 6)
    
    print("\nPhase 2 initial setup complete!")
    print("Starting r1 to r6 path monitoring (updates every 60 seconds)...")
    print("Press Ctrl+C to stop...")
    
    try:
        iteration = 1
        # r1からr6の前回経路情報を保存（変化検出用）
        previous_r1_to_r6_path = None
        previous_r1_to_r6_cost = None
        
        while True:
            print(f"\n=== Update Iteration {iteration} ===")
            
            # エッジ重みをRRDデータで更新
            topology.update_edge_weights()
            
            # 更新されたトポロジ情報を表示
            topology.print_topology_info()
            
            # r1からr6の最短経路を監視
            print("\n--- r1 to r6 Path Monitoring ---")
            current_path, current_cost = topology.find_shortest_path(1, 6)
            
            if current_path:
                current_path_str = " -> ".join([f"r{node}" for node in current_path])
                print(f"Current r1 to r6 path: {current_path_str}")
                print(f"Current cost: {current_cost:.6f}")
                print(f"Current hops: {len(current_path) - 1}")
                
                # 経路変化の検出
                path_changed = False
                cost_changed = False
                
                if previous_r1_to_r6_path is not None:
                    if current_path != previous_r1_to_r6_path:
                        path_changed = True
                        print("\n🔄 r1 to r6 PATH CHANGE DETECTED!")
                        prev_path_str = " -> ".join([f"r{node}" for node in previous_r1_to_r6_path])
                        print(f"  Previous: {prev_path_str} (cost: {previous_r1_to_r6_cost:.6f})")
                        print(f"  Current:  {current_path_str} (cost: {current_cost:.6f})")
                        cost_diff = current_cost - previous_r1_to_r6_cost
                        print(f"  Cost change: {cost_diff:+.6f}")
                        
                        # 変更された経路をハイライト表示
                        print("  📊 Generating highlighted topology...")
                        topology.draw_topology(
                            save_path="/opt/app/srv6_network_topology_r1_to_r6_NEW.png",
                            highlight_path=current_path
                        )
                        print(f"  💾 New path saved as: srv6_network_topology_r1_to_r6_NEW.png")
                        
                    elif abs(current_cost - previous_r1_to_r6_cost) > 0.001:
                        cost_changed = True
                        print(f"\n📈 r1 to r6 COST CHANGE DETECTED!")
                        cost_diff = current_cost - previous_r1_to_r6_cost
                        print(f"  Path: {current_path_str}")
                        print(f"  Previous cost: {previous_r1_to_r6_cost:.6f}")
                        print(f"  Current cost:  {current_cost:.6f}")
                        print(f"  Cost change: {cost_diff:+.6f}")
                    else:
                        print("✅ r1 to r6 path unchanged")
                else:
                    print("🎯 Initial r1 to r6 path recorded")
                    path_changed = True  # 初回は更新する
                
                # SRv6経路をr1に適用（経路変化時のみ）
                if path_changed:
                    print("\n--- SRv6 Route Application ---")
                    srv6_success = topology.apply_srv6_route_to_r1(current_path, force_update=True)
                    if srv6_success:
                        print("🚀 SRv6 route successfully applied to r1!")
                    else:
                        print("❌ Failed to apply SRv6 route to r1")
                
                # 常にr1→r6経路をハイライト表示
                topology.draw_topology(
                    save_path="/opt/app/srv6_network_topology_r1_to_r6.png",
                    highlight_path=current_path
                )
                
                # 経路情報を保存
                previous_r1_to_r6_path = current_path.copy()
                previous_r1_to_r6_cost = current_cost
                
            else:
                print("❌ No path available from r1 to r6")
            
            # 詳細な経路分析を定期的に表示
            if iteration % 2 == 1:  # 2回に1回詳細表示
                print("\n--- Detailed r1 to r6 Analysis ---")
                if current_path:
                    print("Path breakdown:")
                    total_cost = 0
                    for i in range(len(current_path) - 1):
                        u, v = current_path[i], current_path[i+1]
                        edge_weight = topology.graph[u][v]['weight']
                        total_cost += edge_weight
                        print(f"  Hop {i+1}: r{u} -> r{v} (weight: {edge_weight:.6f})")
                    print(f"  Total calculated cost: {total_cost:.6f}")
                    
                    # エッジ重み情報も表示
                    print("\nCurrent edge weights affecting r1 to r6:")
                    for u, v, d in topology.graph.edges(data=True):
                        weight = d['weight']
                        if weight > 0.001:  # デフォルト以外の重み
                            print(f"  r{u} <-> r{v}: {weight:.6f} (active)")
                        else:
                            print(f"  r{u} <-> r{v}: {weight:.6f} (default)")
            
            print(f"\nNext update in 60 seconds... (Iteration {iteration+1})")
            print("="*60)
            
            time.sleep(60)
            iteration += 1
            
    except KeyboardInterrupt:
        print("\nStopping topology manager...")
        plt.close('all')

if __name__ == "__main__":
    main()