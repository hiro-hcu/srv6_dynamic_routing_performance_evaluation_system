# SRv6 Dynamic Routing Prototype System

A comprehensive Docker-based SRv6 (Segment Routing over IPv6) dynamic routing system with real-time traffic monitoring, multi-table routing, and automatic path orchestration capabilities.

## 🌟 Key Features

- **🚀 Dynamic Path Orchestration**: Real-time optimal path calculation based on network conditions
- **🔄 Bidirectional Control**: Independent forward (r1→r6) and return (r6→r1) path management with synchronized flow label handling
- **📊 Multi-Table Routing**: QoS-aware routing with 3 priority tiers (high/medium/low) using fwmark-based classification
- **⚡ Real-time Monitoring**: MRTG-based traffic analysis with 60-second RRD data polling
- **🧠 Intelligent Switching**: Automatic path switching based on link utilization thresholds
- **🔧 Auto-Configuration**: Automated Phase 1 & 2 setup on container startup (nftables + routing tables + fwmark rules)
- **📈 Performance Analytics**: RRD-based edge weight calculation and NetworkX shortest path optimization
- **🐳 Full Containerization**: Complete Docker-based deployment with automatic dependency management
- **🌐 External Node Support**: Macvlan-based connection for real-world UPF/Server integration with low-latency communication
- **✅ Verified Flow Label Mapping**: Consistent 0xfffc1/0xfffc2/0xfffc3 → mark 1/2/3 across all routers

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                 SRv6 Dynamic Routing System                        │
│                                                                     │
│  UPF ───── r1 ─────── r2 ─────── r4 ─────── r6 ───── Server      │
│  (external) │         │         │         │         │  (external)   │
│          fd00:1    fd01:2    fd01:3    fd01:4    fd03:1           │
│             │         │         │         │         │               │
│          fd01:8    fd01:9  (Alt Paths) fd01:6                      │
│             │         │         │         │                         │
│             r3 ─────── r5 ──────────────────┘                      │
│          fd01:7                                                     │
│                                                                     │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │                    Controller System                        │   │
│  │  ┌──────────────────┐  ┌──────────────────────────────┐   │   │
│  │  │ Auto Init        │  │    Real-time Components       │   │   │
│  │  │ (on startup)     │  │  ┌────────┐  ┌──────────────┐│   │   │
│  │  │ ┌──────────────┐ │  │  │ MRTG   │  │ Phase3 RT    ││   │   │
│  │  │ │ Phase1       │ │  │  │ Poller │  │ Manager      ││   │   │
│  │  │ │ - r1 tables  │ │  │  │ (60s)  │  │ - Bidirect.  ││   │   │
│  │  │ │ - r6 tables  │◄┼──┼──┤ RRD    │◄─┤ - Multi-tbl  ││   │   │
│  │  │ │ - fwmark→tbl │ │  │  │ Data   │  │ - Dyn Paths  ││   │   │
│  │  │ └──────────────┘ │  │  └────────┘  │ - nft+rules  ││   │   │
│  │  │ ┌──────────────┐ │  │               └──────────────┘│   │   │
│  │  │ │ Phase2       │ │  │                                │   │   │
│  │  │ │ - r1 nftables│ │  │   Flow Label → Mark Mapping:  │   │   │
│  │  │ │ - r6 nftables│ │  │   0xfffc1 → 1 → rt_table1     │   │   │
│  │  │ │ - flowlabel  │ │  │   0xfffc2 → 2 → rt_table2     │   │   │
│  │  │ │   →mark (1/2)│ │  │   0xfffc3 → 3 → rt_table3     │   │   │
│  │  │ └──────────────┘ │  │                                │   │   │
│  │  └──────────────────┘  └──────────────────────────────┘   │   │
│  └────────────────────────────────────────────────────────────┘   │
│           │ SSH Auto-Config              │ RT Updates            │
│           ▼                              ▼                        │
│  ┌─────────────────┐           ┌─────────────────┐               │
│  │ r1 (Forward)    │           │ r6 (Return)     │               │
│  │ fd02:1::2       │           │ fd02:1::7       │               │
│  │ ┌─────────────┐ │           │ ┌─────────────┐ │               │
│  │ │ nftables    │ │           │ │ nftables    │ │               │
│  │ │ flowlabel→  │ │           │ │ flowlabel→  │ │               │
│  │ │ mark 1/2/3  │ │           │ │ mark 1/2/3  │ │               │
│  │ └─────────────┘ │           │ └─────────────┘ │               │
│  │ ┌─────────────┐ │           │ ┌─────────────┐ │               │
│  │ │ rt_table1/2 │ │           │ │ rt_table_1/2│ │               │
│  │ │ (Priority)  │ │           │ │ (Priority)  │ │               │
│  │ │ fwmark 1/2→ │ │           │ │ fwmark 1/2→ │ │               │
│  │ │ SRv6 routes │ │           │ │ SRv6 routes │ │               │
│  │ └─────────────┘ │           │ └─────────────┘ │               │
│  └─────────────────┘           └─────────────────┘               │
└─────────────────────────────────────────────────────────────────────┘

Verified Configuration (Fixed 2025-11-04):
✅ r1/r6: flowlabel 0xfffc1/2/3 → mark 0x1/0x2/0x3
✅ r1/r6: fwmark 0x1/0x2/0x3 → rt_table1/2/3
✅ Bidirectional path independence maintained
```

## 📁 Project Structure

```
srv6_dynamic_routing_prototype_system/
├── 📋 README.md                           # Project documentation
├── 🐳 docker-compose.yml                  # Main configuration with dependency management
├── � EXTERNAL_CONNECTION.md              # External UPF/Server connection guide
│
├── 🌐 router/                             # SRv6 router infrastructure
│   ├── Dockerfile                        # Base router image
│   ├── Dockerfile_r1                     # R1 (ingress) with SSH
│   ├── Dockerfile_r6                     # R6 (egress) with SSH
│   ├── scripts/                          # Router initialization
│   │   ├── srv6_setup.sh                 # SRv6 kernel configuration
│   │   ├── r1_startup.sh                 # R1 specialized startup
│   │   └── r6_startup.sh                 # R6 specialized startup
│   ├── docs/                             # Technical documentation
│   │   ├── advanced-routing-setup.md     # nftables + fwmark guide
│   │   └── srv6-end-functions.md         # SRv6 function reference
│   └── snmpd/
│       └── snmpd.conf                    # SNMP monitoring config
│
├── 📊 scripts/                            # Utility scripts
│   ├── cleanup_host.sh                   # Cleanup script
│   ├── setup_all.sh                      # Setup script
│   └── README.md                         # Script documentation
│
└── 🎛️ controller/                         # Control plane system
    ├── Dockerfile                        # Auto-initializing controller
    ├── init_setup.py                     # 🆕 Automated Phase1&2 setup
    ├── test_ssh.py                       # SSH connection testing
    │
    ├── 📊 mrtg/                          # Traffic monitoring
    │   ├── mrtg_kurage.conf              # Link-specific MRTG config
    │   ├── mrtg_kurage.ok                # Status indicator
    │   ├── mrtg_file/                    # RRD data storage
    │   └── rrdtool_shell/
    │       └── create_rrd.sh             # RRD database initialization
    │
    ├── 📊 presentation/                   # Research presentation materials
    │   ├── README.md                     # Presentation guide
    │   ├── diagrams/                     # System architecture diagrams
    │   ├── docs/                         # Documentation exports
    │   └── scripts/                      # Diagram generation scripts
    │
    └── � srv6-path-orchestrator/         # Core orchestration system
        ├── function_analysis.md          # System function analysis
        │
        ├── 🔧 Phase 1&2 Setup Scripts (Auto-executed):
        ├── r1_phase1_table_setup.py      # R1 routing tables + rules
        ├── r1_phase2_nftables_setup.py   # R1 nftables + flow marking
        ├── r6_phase1_table_setup.py      # R6 routing tables + rules  
        ├── r6_phase2_nftables_setup.py   # R6 nftables + flow marking
        │
        ├── 🚀 Phase 3 Main System:
        ├── phase3_realtime_multi_table.py # 🌟 Main orchestrator
        │                                  # - Bidirectional control
        │                                  # - Real-time monitoring  
        │                                  # - Dynamic path switching
        │                                  # - Multi-table management
        │
        └── � backup/                     # Legacy implementations
            ├── main.py                   # Basic topology manager
            └── phase3_multi_table_simple.py # Simple multi-table version
```

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose v2.0+
- Linux environment with IPv6 support (tested on Ubuntu 20.04+)
- Root privileges for container networking


### 1. Clone and Deploy
```bash
git clone https://github.com/hiro-hcu/srv6_dynamic_routing_prototype_system.git
cd srv6_dynamic_routing_prototype_system

# Deploy all containers with automatic initialization
sudo docker compose up -d
```

### 2. Verify Auto-Initialization
The controller automatically performs Phase 1 & 2 setup on startup:
```bash
# Monitor initialization progress (wait ~30 seconds)
sudo docker logs -f controller

# Expected output sequence:
# 2025-11-04 08:30:15 - INFO - SRv6システム初期化開始...
# 2025-11-04 08:30:45 - INFO - ✅ SSH準備完了 (r1: fd02:1::2, r6: fd02:1::7)
# 2025-11-04 08:30:50 - INFO - ✅ r1_phase1_table_setup.py 実行成功
# 2025-11-04 08:30:55 - INFO - ✅ r1_phase2_nftables_setup.py 実行成功
# 2025-11-04 08:31:00 - INFO - ✅ r6_phase1_table_setup.py 実行成功
# 2025-11-04 08:31:05 - INFO - ✅ r6_phase2_nftables_setup.py 実行成功
# 2025-11-04 08:31:10 - INFO - 🎉 初期化完了: システムは運用可能です
```

**Verification Commands**:
```bash
# Verify nftables configuration (r1)
sudo docker exec -it r1 nft list table ip6 mangle

# Expected: flowlabel 1048513/14/15 → mark set 0x00000001/2/3

# Verify routing rules (r6)
sudo docker exec -it r6 ip -6 rule list

# Expected: fwmark 0x1/0x2/0x3 lookup rt_table_1/2/3

# Check routing tables
sudo docker exec -it r1 ip -6 route show table rt_table1
sudo docker exec -it r6 ip -6 route show table rt_table_1
```

### 3. Start Real-time Orchestration (Phase 3)
```bash
# Run bidirectional real-time management (continuous mode)
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py

# Alternative: One-time execution for testing
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --once

# Expected output:
# 2025-11-04 08:35:56 - INFO - 🚀 双方向テーブル更新開始
# 2025-11-04 08:35:56 - INFO - Edge r1 <-> r2: 9.633 bps
# 2025-11-04 08:35:57 - INFO - 往路最適経路: r1 → r2 → r4 → r6
# 2025-11-04 08:35:57 - INFO - 復路最適経路: r6 → r4 → r2 → r1
# 2025-11-04 08:35:57 - INFO - ✅ 双方向テーブル更新成功
```

### 4. Verify End-to-End Connectivity
```bash
# Test forward path (UPF/client → Server)
# Note: Requires external UPF setup or internal client container
ping6 -c 5 fd03:1::2  # From UPF (fd00:1::1)

# Test return path (Server → UPF/client)
ping6 -c 5 fd00:1::1  # From Server (fd03:1::2)

# Monitor packet flow on r1 (UPF-side interface)
sudo docker exec -it r1 tcpdump -i eth3 -n icmp6

# Monitor packet flow on r6 (Server-side interface)
sudo docker exec -it r6 tcpdump -i eth1 -n icmp6
```

## 🌐 External PC Connection (Advanced)

For real-world testing with physical UPF/Server nodes:

🏠 **System Modes**:
- **Container Mode**: Self-contained testing environment (default)
- **External Node Mode**: Macvlan-based connection to real hardware

### 3. Start Real-time Orchestration
```bash
# Run bidirectional real-time management
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py

# Alternative: One-time execution
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --once
```

### 4. Generate Traffic and Observe Path Changes
```bash
# Terminal 1: Generate traffic (UPF → server)
sudo docker exec -it client ping6 -i 0.1 fd01:5::12

# Terminal 2: Generate reverse traffic (server → UPF)  
sudo docker exec -it server ping6 -i 0.1 fd01:1::11

# Terminal 3: Watch dynamic path switching
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py
```

## � External PC Connection (Advanced)

For real-world testing with physical UPF/Server nodes:

🏠 **System Modes**:
- **Container Mode**: Self-contained testing environment
- **External Node Mode**: Bridge physical interfaces to real UPF/Server nodes

### **External PC Setup**
```bash
# 1. Host bridge configuration
sudo ./scripts/external_connection/setup_host_bridge.sh

# 2. External PC manual configuration (see EXTERNAL_CONNECTION.md)
# UPF: sudo ip -6 addr add fd01:1::100/64 dev <interface>
# Server PC: sudo ip -6 addr add fd01:5::100/64 dev <interface>
```

### **Benefits of External PC Mode**
- **Real Latency**: Physical network delays and realistic RTT
- **Performance Testing**: Actual hardware throughput measurements
- **Multi-PC Scenarios**: Complex traffic patterns across multiple machines
- **Production-like Environment**: Real-world application testing

📖 **Detailed Guide**: See [EXTERNAL_CONNECTION.md](EXTERNAL_CONNECTION.md) for complete setup instructions.

---

## �🎯 System Phases Overview

### Phase 1: Infrastructure Setup (Auto-executed)
- **Routing Tables**: Creates `rt_table1`, `rt_table2`, `rt_table3` for QoS tiers
- **Rule Configuration**: Sets up `fwmark`-based routing rules
- **Targets**: Both r1 (forward) and r6 (return) routers

### Phase 2: Traffic Classification (Auto-executed)  
- **nftables Setup**: IPv6 flow label → firewall mark conversion
- **Flow Mapping** (⚠️ Fixed 2025-11-04): 
  - `0xfffc1` (1048513) → mark **1** → High Priority (rt_table1)
  - `0xfffc2` (1048514) → mark **2** → Medium Priority (rt_table2) 
  - `0xfffc3` (1048515) → mark **3** → Low Priority (rt_table3)
- **Bidirectional**: Independent forward (r1) and return (r6) classification
- **Automatic**: Executes during container startup via `init_setup.py`

### Phase 3: Real-time Orchestration (Manual/Automated)
- **Traffic Monitoring**: RRD-based link utilization analysis (60-second intervals)
- **Dynamic Paths**: Automatic optimal path calculation using NetworkX shortest path
- **Bidirectional Control**: Simultaneous r1→r6 (forward) and r6→r1 (return) path management
- **SRv6 Encapsulation**: Dynamic SID list generation based on calculated paths
- **Route Updates**: SSH-based automated route installation to r1 and r6
- **Multi-Table**: 3-priority system with independent path optimization per table

## 📊 Technical Implementation

### nftables + fwmark Integration (Corrected Configuration)
```bash
# Phase 2: Flow Label Detection (nftables)
# Creates mangle table and sets marks based on IPv6 flow labels
nft 'add table ip6 mangle'
nft 'add chain ip6 mangle prerouting { type filter hook prerouting priority mangle; }'
nft 'add rule ip6 mangle prerouting ip6 flowlabel 1048513 mark set 0x00000001'  # 0xfffc1
nft 'add rule ip6 mangle prerouting ip6 flowlabel 1048514 mark set 0x00000002'  # 0xfffc2
nft 'add rule ip6 mangle prerouting ip6 flowlabel 1048515 mark set 0x00000003'  # 0xfffc3

# Phase 1: Routing Rule Application (fwmark-based table selection)
ip -6 rule add pref 1000 fwmark 0x1 table rt_table1  # High priority
ip -6 rule add pref 1001 fwmark 0x2 table rt_table2  # Medium priority
ip -6 rule add pref 1002 fwmark 0x3 table rt_table3  # Low priority

# Phase 3: SRv6 Route Installation (dynamic, per-table)
# Example: Forward path r1→r2→r4→r6 in rt_table1
ip -6 route add fd03:1::/64 encap seg6 mode encap \
    segs fd01:2::12,fd01:3::12,fd01:4::12 dev eth1 table rt_table1

# Example: Return path r6→r4→r2→r1 in rt_table_1
ip -6 route add fd00:1::/64 encap seg6 mode encap \
    segs fd01:4::11,fd01:3::11,fd01:2::11 dev eth2 table rt_table_1
```

### Flow Label → Mark → Table Flow
```
User Packet with flowlabel 0xfffc1 (high priority)
    ↓
[nftables mangle prerouting]
    ↓ (flowlabel 1048513 detected)
Packet marked with fwmark=1
    ↓
[ip -6 rule lookup]
    ↓ (fwmark 1 matches)
Routing table rt_table1 selected
    ↓
[SRv6 encapsulation route in rt_table1]
    ↓
Packet encapsulated with SID list [fd01:2::12, fd01:3::12, fd01:4::12]
    ↓
Forwarded to next hop
```

### Real-time Monitoring Pipeline
- **MRTG**: 60-second SNMP polling → RRD storage 
- **Phase3 Manager**: RRD fetch → Traffic analysis → Graph edge weight update
- **Path Calculator**: NetworkX Dijkstra shortest path → Multiple path options
- **Route Installer**: SSH automation (paramiko) → Live route updates to r1/r6
- **Bidirectional**: Independent optimization for forward and return paths

## 🔗 Network Topology & Addressing

### Physical Topology
```
Client ─── r1 ─────── r2 ─────── r4 ─────── r6 ─── Server
           │         │         │         │
           │         │         │         │
           r3 ─────── r5 ──────────────────┘

Links with RRD Monitoring:
├── r1 ↔ r2 (fd01:2::/64) → r1-r2.rrd
├── r1 ↔ r3 (fd01:8::/64) → r1-r3.rrd  
├── r2 ↔ r4 (fd01:3::/64) → r2-r4.rrd
├── r2 ↔ r5 (fd01:9::/64) → r2-r5.rrd
├── r3 ↔ r5 (fd01:7::/64) → r3-r5.rrd
├── r4 ↔ r6 (fd01:4::/64) → r4-r6.rrd
└── r5 ↔ r6 (fd01:6::/64) → r5-r6.rrd
```

### IP Addressing Scheme
```
Management Network (SSH & Control):
├── Controller: fd02:1::10
├── r1: fd02:1::2 (SSH enabled)
├── r2: fd02:1::3  
├── r3: fd02:1::4
├── r4: fd02:1::5
├── r5: fd02:1::6
└── r6: fd02:1::7 (SSH enabled)

Data Networks:
├── UPF-R1: fd01:1::/64 (UPF: ::11, R1: ::12)
├── R1-R2: fd01:2::/64 (R1: ::11, R2: ::12)  
├── R1-R3: fd01:8::/64 (R1: ::11, R3: ::12)
├── R2-R4: fd01:3::/64 (R2: ::11, R4: ::12)
├── R2-R5: fd01:9::/64 (R2: ::11, R5: ::12)
├── R3-R5: fd01:7::/64 (R3: ::11, R5: ::12)
├── R4-R6: fd01:4::/64 (R4: ::11, R6: ::12)
├── R5-R6: fd01:6::/64 (R5: ::11, R6: ::12)
└── R6-Server: fd01:5::/64 (R6: ::11, Server: ::12)
```

### Path Examples
**High Priority Path (rt_table1)**: 
- Forward: UPF → r1 → r2 → r4 → r6 → Server
- SID List: `[fd01:2::12, fd01:3::12, fd01:4::12]`

**Alternative Path (rt_table2)**:
- Forward: UPF → r1 → r3 → r5 → r6 → Server  
- SID List: `[fd01:8::12, fd01:7::12, fd01:6::12]`

## 🛠️ Advanced Usage

### Manual Phase Execution
```bash
# Run individual setup phases
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/r1_phase1_table_setup.py
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/r1_phase2_nftables_setup.py
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/r6_phase1_table_setup.py
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/r6_phase2_nftables_setup.py
```

### Real-time Orchestration Modes
```bash
# Bidirectional monitoring (recommended)
python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --mode bidirectional

# Forward path only
python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --mode forward

# Traffic analysis only
python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --mode analyze --once

# Custom update interval  
python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --interval 30
```

### Testing & Debugging
```bash
# Test SSH connectivity
sudo docker exec -it controller python3 /opt/app/test_ssh.py

# Verify nftables rules
sudo docker exec -it r1 nft list table ip6 mangle

# Check routing tables
sudo docker exec -it r1 ip -6 route show table rt_table1

# Monitor RRD data
sudo docker exec -it controller rrdtool fetch /opt/app/mrtg/mrtg_file/r1-r2.rrd AVERAGE --start -60s

# Real-time traffic monitoring
sudo docker exec -it controller watch -n 5 'cat /opt/app/mrtg/mrtg_file/r*.rrd | head -20'
```

### Performance Tuning
```bash
# Adjust MRTG polling interval (default: 60s)
# Edit: controller/mrtg/mrtg_kurage.conf

# Modify path calculation sensitivity
# Edit: phase3_realtime_multi_table.py → PathCalculator class

# Configure route update thresholds
# Edit: SRv6Config → weight calculation parameters
```

## � System Monitoring & Analytics

### Real-time Metrics Collection
- **Link Utilization**: Per-link traffic analysis via SNMP/RRD
- **Path Performance**: Latency and throughput per routing table
- **Route Changes**: Automatic logging of path switching events
- **Load Distribution**: Traffic distribution across multiple tables

### Observable Behaviors
```bash
# Expected system responses to traffic:
1. High traffic on r1→r2 → System switches to r1→r3→r5→r6
2. Link congestion detected → Alternative paths activated
3. Path oscillation → System stabilizes on optimal route
4. Bidirectional independence → Forward/return paths optimized separately
```

## 🔬 Research Applications

### Academic Use Cases
- **SRv6 Performance Analysis**: Real network behavior under dynamic conditions
- **Traffic Engineering**: Multi-path routing optimization algorithms  
- **SDN Integration**: Centralized control plane with distributed data plane
- **Network Simulation**: Realistic testbed for routing protocol research

### Key Research Features
- **Reproducible Results**: Containerized environment ensures consistency
- **Comprehensive Logging**: Detailed path change and performance logs
- **Flexible Configuration**: Easy modification of routing policies
- **Standards Compliance**: Pure IPv6 + SRv6 implementation

## 🚨 Troubleshooting

### Common Issues
```bash
# Check auto-initialization logs
sudo docker logs controller

# Look for:
# - SSH connection errors (wait 30-60 seconds for routers to start SSH)
# - Phase execution failures (check Python tracebacks)

# Manual retry if auto-init failed
sudo docker exec -it controller python3 /opt/app/init_setup.py
```

#### 3. SSH Connection Failures  
```bash
# Test SSH connectivity
sudo docker exec -it controller python3 /opt/app/test_ssh.py

# Check SSH service on routers
sudo docker exec -it r1 service ssh status
sudo docker exec -it r6 service ssh status

# Restart SSH if needed
sudo docker exec -it r1 service ssh restart
sudo docker exec -it r6 service ssh restart
```

#### 4. nftables Rule Conflicts
```bash
# View current rules
sudo docker exec -it r1 nft list ruleset | grep -A 20 mangle

# Flush and recreate (caution: removes all rules)
sudo docker exec -it r1 nft flush table ip6 mangle
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/r1_phase2_nftables_setup.py --setup
```

#### 5. Route Installation Failures
```bash
# Check current routes in table
sudo docker exec -it r1 ip -6 route show table rt_table1

# Flush specific table
sudo docker exec -it r1 ip -6 route flush table rt_table1

# Re-run Phase 3 to reinstall routes
sudo docker exec -it controller python3 /opt/app/srv6-path-orchestrator/phase3_realtime_multi_table.py --once
```

#### 6. RRD Data Collection Issues
```bash
# Check RRD file existence
sudo docker exec -it controller ls -la /opt/app/mrtg/mrtg_file/
# Should show: r1-r2.rrd, r1-r3.rrd, r2-r4.rrd, r2-r5.rrd, r3-r5.rrd, r4-r6.rrd, r5-r6.rrd

# Manually create RRD files if missing
sudo docker exec -it controller /opt/app/mrtg/rrdtool_shell/create_rrd.sh

# Check MRTG cron job
sudo docker exec -it controller crontab -l
# Should show: * * * * * env LANG=C /usr/bin/mrtg /opt/app/mrtg/mrtg_kurage.conf

# Test RRD data fetch
sudo docker exec -it controller rrdtool fetch /opt/app/mrtg/mrtg_file/r1-r2.rrd AVERAGE --start -60s
```

#### 7. No Packets Forwarded (r1 receives but doesn't forward)
```bash
# Check IPv6 forwarding
sudo docker exec -it r1 sysctl net.ipv6.conf.all.forwarding
# Should be: 1

# Check SRv6 enabled
sudo docker exec -it r1 sysctl net.ipv6.conf.all.seg6_enabled
# Should be: 1

# Check neighbor entries
sudo docker exec -it r1 ip -6 neigh show

# Verify SRv6 local SIDs
sudo docker exec -it r1 ip -6 route show table local | grep fd01
```

### System Reset
```bash
# Complete environment reset (removes all containers and data)
sudo docker compose down
sudo docker system prune -f
sudo docker volume prune -f
sudo docker compose up -d

# Wait for auto-initialization (30-60 seconds)
sudo docker logs -f controller
```

### Diagnostic Commands Cheat Sheet
```bash
# Quick health check
sudo docker exec -it r1 nft list table ip6 mangle | grep flowlabel
sudo docker exec -it r6 nft list table ip6 mangle_r6 | grep flowlabel
sudo docker exec -it r1 ip -6 rule list | grep fwmark
sudo docker exec -it r6 ip -6 rule list | grep fwmark

# Verify Phase 1 & 2 completion
sudo docker logs controller | grep "✅"

# Test end-to-end (from external UPF/Server)
ping6 -c 3 fd03:1::2   # UPF → Server
ping6 -c 3 fd00:1::1   # Server → UPF

# Monitor live packet flow
sudo docker exec -it r1 tcpdump -i eth3 -n -c 10 icmp6
sudo docker exec -it r6 tcpdump -i eth1 -n -c 10 icmp6
```

## 🤝 Contributing

1. Fork the repository
2. Create feature branches for new routing algorithms
3. Test in containerized environment
4. Document performance improvements
5. Submit pull requests with test results

## � License & Citation

This project is developed for academic research on SRv6 dynamic routing systems.

```bibtex
@misc{srv6_dynamic_routing_2025,
  title={SRv6 Dynamic Routing Prototype System with Real-time Path Orchestration},
  author={[Author]},
  year={2025},
  howpublished={\\url{https://github.com/hiro-hcu/srv6_dynamic_routing_prototype_system}},
  note={Docker-based SRv6 testbed with automatic multi-table routing}
}
```

## 🔍 Technical References

### Standards & Protocols
- [RFC 8754: IPv6 Segment Routing Header (SRH)](https://tools.ietf.org/html/rfc8754)
- [RFC 8986: Segment Routing over IPv6 (SRv6) Network Programming](https://tools.ietf.org/html/rfc8986)
- [Linux SRv6 Implementation Guide](https://www.kernel.org/doc/html/latest/networking/seg6-sysctl.html)

### Implementation Tools  
- [iproute2: Linux Advanced Routing](https://wiki.linuxfoundation.org/networking/iproute2)
- [nftables: Linux Firewall Framework](https://netfilter.org/projects/nftables/)
- [MRTG: Network Traffic Monitoring](https://oss.oetiker.ch/mrtg/)
- [NetworkX: Network Analysis in Python](https://networkx.org/)

---

**System Status**: ✅ Production Ready | 🔄 Real-time Monitoring Active | 🚀 Auto-Initialization Enabled | ✅ Mark Mapping Verified (2025-11-04)
