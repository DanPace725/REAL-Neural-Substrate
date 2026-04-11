from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, Sequence, Tuple

from .models import SignalSpec

TOPOLOGY_MODES = ("legacy", "bounded_overlap_13715")


def basic_demo_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    adjacency = {
        "n0": ("n1", "n2"),
        "n1": ("n3",),
        "n2": ("n3",),
        "n3": ("sink",),
    }
    positions = {
        "n0": 0,
        "n1": 1,
        "n2": 1,
        "n3": 2,
        "sink": 3,
    }
    return adjacency, positions, "n0", "sink"


def branch_pressure_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    adjacency = {
        "n0": ("n1", "n2"),
        "n1": ("n3", "n4"),
        "n2": ("n4", "n5"),
        "n3": ("sink",),
        "n4": ("sink",),
        "n5": ("sink",),
    }
    positions = {
        "n0": 0,
        "n1": 1,
        "n2": 1,
        "n3": 2,
        "n4": 2,
        "n5": 2,
        "sink": 3,
    }
    return adjacency, positions, "n0", "sink"


def branch_pressure_workload() -> Tuple[int, int, Dict[int, int]]:
    cycles = 18
    initial_packets = 6
    packet_schedule = {
        4: 2,
        8: 2,
        12: 2,
    }
    return cycles, initial_packets, packet_schedule


def sustained_pressure_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    return branch_pressure_topology()


def sustained_pressure_workload() -> Tuple[int, int, Dict[int, int]]:
    cycles = 24
    initial_packets = 8
    packet_schedule = {
        3: 3,
        6: 3,
        9: 3,
        12: 3,
        16: 2,
        20: 2,
    }
    return cycles, initial_packets, packet_schedule


def detour_resilience_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    adjacency = {
        "n0": ("n1", "n2"),
        "n1": ("n3",),
        "n2": ("n3", "n4"),
        "n3": ("n5",),
        "n4": ("n5",),
        "n5": ("sink",),
    }
    positions = {
        "n0": 0,
        "n1": 1,
        "n2": 1,
        "n3": 2,
        "n4": 2,
        "n5": 3,
        "sink": 4,
    }
    return adjacency, positions, "n0", "sink"


def detour_resilience_workload() -> Tuple[int, int, Dict[int, int]]:
    cycles = 22
    initial_packets = 5
    packet_schedule = {
        4: 2,
        7: 1,
        11: 2,
        16: 2,
    }
    return cycles, initial_packets, packet_schedule


def bounded_ternary_overlap_topology(
    layer_widths: Sequence[int] = (3, 7, 15),
) -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    """Bounded overlap graph with widths 1,3,7,15,... and 3-child fanout."""
    source_id = "n0"
    sink_id = "sink"
    positions: Dict[str, int] = {source_id: 0}
    adjacency: Dict[str, tuple[str, ...]] = {}
    layers: list[list[str]] = []
    next_id = 1

    for layer_index, width in enumerate(layer_widths, start=1):
        layer_nodes = [f"n{next_id + offset}" for offset in range(width)]
        next_id += width
        layers.append(layer_nodes)
        for node_id in layer_nodes:
            positions[node_id] = layer_index
    positions[sink_id] = len(layer_widths) + 1

    if not layers:
        adjacency[source_id] = (sink_id,)
        adjacency[sink_id] = ()
        return adjacency, positions, source_id, sink_id

    adjacency[source_id] = tuple(layers[0])
    for current_layer, next_layer in zip(layers, layers[1:]):
        for node_index, node_id in enumerate(current_layer):
            start = min(max(0, 2 * node_index), max(len(next_layer) - 3, 0))
            adjacency[node_id] = tuple(next_layer[start:start + min(3, len(next_layer))])

    for node_id in layers[-1]:
        adjacency[node_id] = (sink_id,)
    adjacency[sink_id] = ()
    return adjacency, positions, source_id, sink_id


def scenario_with_topology_mode(
    scenario: "ScenarioSpec",
    topology_mode: str = "legacy",
) -> "ScenarioSpec":
    if topology_mode == "legacy":
        return scenario
    if topology_mode != "bounded_overlap_13715":
        raise ValueError(f"Unsupported topology mode: {topology_mode}")
    adjacency, positions, source_id, sink_id = bounded_ternary_overlap_topology()
    topology_depth = max(int(position) for position in positions.values())
    return replace(
        scenario,
        name=f"{scenario.name}_{topology_mode}",
        description=f"{scenario.description} [{topology_mode} topology]",
        adjacency=adjacency,
        positions=positions,
        source_id=source_id,
        sink_id=sink_id,
        packet_ttl=max(int(scenario.packet_ttl), topology_depth * 4),
    )


def _bits4(value: int) -> list[int]:
    return [
        (value >> 3) & 1,
        (value >> 2) & 1,
        (value >> 1) & 1,
        value & 1,
    ]


def _parity(bits: Sequence[int]) -> int:
    return sum(int(bit) for bit in bits) % 2


def cvt1_stage1_signals(task_id: str = "task_a") -> Tuple[SignalSpec, ...]:
    values = [
        0b0001,
        0b0110,
        0b1011,
        0b0101,
        0b1110,
        0b0011,
        0b1100,
        0b1001,
        0b0111,
        0b1010,
        0b0100,
        0b1111,
        0b0000,
        0b1101,
        0b0010,
        0b1000,
        0b0110,
        0b1011,
    ]
    previous_bits = [0, 0, 0, 0]
    signals = []
    for value in values:
        bits = _bits4(value)
        context_bit = _parity(previous_bits)
        signals.append(
            SignalSpec(
                input_bits=bits,
                context_bit=context_bit,
                task_id=task_id,
            )
        )
        previous_bits = bits
    return tuple(signals)


def cvt1_task_a_stage1_signals() -> Tuple[SignalSpec, ...]:
    return cvt1_stage1_signals("task_a")


def cvt1_task_b_stage1_signals() -> Tuple[SignalSpec, ...]:
    return cvt1_stage1_signals("task_b")


def cvt1_task_c_stage1_signals() -> Tuple[SignalSpec, ...]:
    return cvt1_stage1_signals("task_c")


def cvt1_large_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    """10-node branching topology with 3-way source split, two convergence layers, and 5-hop paths."""
    adjacency = {
        "n0": ("n1", "n2", "n3"),
        "n1": ("n4", "n5"),
        "n2": ("n4", "n6"),
        "n3": ("n5", "n6"),
        "n4": ("n7",),
        "n5": ("n7", "n8"),
        "n6": ("n8",),
        "n7": ("n9",),
        "n8": ("n9",),
        "n9": ("sink",),
    }
    positions = {
        "n0": 0,
        "n1": 1,
        "n2": 1,
        "n3": 1,
        "n4": 2,
        "n5": 2,
        "n6": 2,
        "n7": 3,
        "n8": 3,
        "n9": 4,
        "sink": 5,
    }
    return adjacency, positions, "n0", "sink"


def cvt1_scale_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    """30-node deep topology to test scale matching 30-hidden-unit neural models."""
    # Source is n0, sink is sink.
    # To get ~30 nodes, let's build layers.
    # L0: n0 (1)
    # L1: n1..n4 (4)
    # L2: n5..n10 (6)
    # L3: n11..n18 (8)
    # L4: n19..n24 (6)
    # L5: n25..n28 (4)
    # L6: n29, sink (2)
    # Total nodes = 1+4+6+8+6+4+1 + sink = 30 nodes + sink.

    adjacency = {
        "n0": ("n1", "n2", "n3", "n4"),

        "n1": ("n5", "n6"),
        "n2": ("n6", "n7"),
        "n3": ("n8", "n9"),
        "n4": ("n9", "n10"),

        "n5": ("n11", "n12"),
        "n6": ("n12", "n13", "n14"),
        "n7": ("n14", "n15"),
        "n8": ("n15", "n16"),
        "n9": ("n16", "n17"),
        "n10": ("n17", "n18"),

        "n11": ("n19",),
        "n12": ("n19", "n20"),
        "n13": ("n20",),
        "n14": ("n20", "n21"),
        "n15": ("n21", "n22"),
        "n16": ("n22", "n23"),
        "n17": ("n23", "n24"),
        "n18": ("n24",),

        "n19": ("n25", "n26"),
        "n20": ("n25", "n26"),
        "n21": ("n26", "n27"),
        "n22": ("n27", "n28"),
        "n23": ("n27", "n28"),
        "n24": ("n28",),

        "n25": ("n29",),
        "n26": ("n29",),
        "n27": ("n29", "sink"),
        "n28": ("sink",),

        "n29": ("sink",),
        "sink": (),
    }

    positions = {
        "n0": 0,
        "n1": 1, "n2": 1, "n3": 1, "n4": 1,
        "n5": 2, "n6": 2, "n7": 2, "n8": 2, "n9": 2, "n10": 2,
        "n11": 3, "n12": 3, "n13": 3, "n14": 3, "n15": 3, "n16": 3, "n17": 3, "n18": 3,
        "n19": 4, "n20": 4, "n21": 4, "n22": 4, "n23": 4, "n24": 4,
        "n25": 5, "n26": 5, "n27": 5, "n28": 5,
        "n29": 6,
        "sink": 7,
    }
    return adjacency, positions, "n0", "sink"


def cvt1_ceiling_topology() -> tuple[Dict[str, tuple[str, ...]], Dict[str, int], str, str]:
    """50-node deeper topology for ceiling-mapping runs with longer routing horizons."""
    adjacency = {
        "n0": ("n1", "n2", "n3", "n4"),

        "n1": ("n5", "n6"),
        "n2": ("n6", "n7", "n8"),
        "n3": ("n8", "n9", "n10"),
        "n4": ("n10", "n11"),

        "n5": ("n12", "n13"),
        "n6": ("n13", "n14"),
        "n7": ("n14", "n15"),
        "n8": ("n15", "n16", "n17"),
        "n9": ("n17", "n18"),
        "n10": ("n18", "n19"),
        "n11": ("n19", "n20"),

        "n12": ("n21",),
        "n13": ("n21", "n22"),
        "n14": ("n22", "n23"),
        "n15": ("n23", "n24"),
        "n16": ("n24", "n25"),
        "n17": ("n25", "n26"),
        "n18": ("n26", "n27"),
        "n19": ("n27", "n28"),
        "n20": ("n28",),

        "n21": ("n29", "n30"),
        "n22": ("n30", "n31"),
        "n23": ("n31", "n32"),
        "n24": ("n32", "n33"),
        "n25": ("n33", "n34"),
        "n26": ("n34", "n35"),
        "n27": ("n35", "n36"),
        "n28": ("n36", "n37"),

        "n29": ("n38",),
        "n30": ("n38", "n39"),
        "n31": ("n39", "n40"),
        "n32": ("n40", "n41"),
        "n33": ("n41", "n42"),
        "n34": ("n42", "n43"),
        "n35": ("n43", "n44"),
        "n36": ("n44", "n45"),
        "n37": ("n45",),

        "n38": ("n46", "n47"),
        "n39": ("n46", "n47"),
        "n40": ("n47", "n48"),
        "n41": ("n48",),
        "n42": ("n48", "n49"),
        "n43": ("n49", "sink"),
        "n44": ("n49", "sink"),
        "n45": ("sink",),

        "n46": ("sink",),
        "n47": ("sink",),
        "n48": ("sink",),
        "n49": ("sink",),
        "sink": (),
    }
    positions = {
        "n0": 0,
        "n1": 1, "n2": 1, "n3": 1, "n4": 1,
        "n5": 2, "n6": 2, "n7": 2, "n8": 2, "n9": 2, "n10": 2, "n11": 2,
        "n12": 3, "n13": 3, "n14": 3, "n15": 3, "n16": 3, "n17": 3, "n18": 3, "n19": 3, "n20": 3,
        "n21": 4, "n22": 4, "n23": 4, "n24": 4, "n25": 4, "n26": 4, "n27": 4, "n28": 4,
        "n29": 5, "n30": 5, "n31": 5, "n32": 5, "n33": 5, "n34": 5, "n35": 5, "n36": 5, "n37": 5,
        "n38": 6, "n39": 6, "n40": 6, "n41": 6, "n42": 6, "n43": 6, "n44": 6, "n45": 6,
        "n46": 7, "n47": 7, "n48": 7, "n49": 7,
        "sink": 8,
    }
    return adjacency, positions, "n0", "sink"


def cvt1_stage3_signals(task_id: str = "task_a") -> Tuple[SignalSpec, ...]:
    """108-packet signal set: 6 passes of the 18-packet sequence for larger scale learning."""
    base_values = [
        0b0001, 0b0110, 0b1011, 0b0101, 0b1110, 0b0011,
        0b1100, 0b1001, 0b0111, 0b1010, 0b0100, 0b1111,
        0b0000, 0b1101, 0b0010, 0b1000, 0b0110, 0b1011,
    ]
    # We want a continuous parity chain for 108 values
    values = []
    # Mix things up slightly for each pass to provide rich coverage
    masks = [0b0000, 0b1111, 0b0101, 0b1010, 0b0011, 0b1100]
    for pass_idx in range(6):
        for v in base_values:
            values.append(v ^ masks[pass_idx])

    previous_bits = [0, 0, 0, 0]
    signals = []
    for value in values:
        bits = _bits4(value)
        context_bit = _parity(previous_bits)
        signals.append(
            SignalSpec(
                input_bits=bits,
                context_bit=context_bit,
                task_id=task_id,
            )
        )
        previous_bits = bits
    return tuple(signals)


def cvt1_stage2_signals(task_id: str = "task_a") -> Tuple[SignalSpec, ...]:
    """36-packet signal set: original 18 followed by 18 new values for richer coverage."""
    values = [
        # Original stage-1 sequence
        0b0001, 0b0110, 0b1011, 0b0101, 0b1110, 0b0011,
        0b1100, 0b1001, 0b0111, 0b1010, 0b0100, 0b1111,
        0b0000, 0b1101, 0b0010, 0b1000, 0b0110, 0b1011,
        # Extended sequence — continues the parity chain from previous_bits=[1,0,1,1]
        0b0101, 0b1110, 0b0011, 0b1100, 0b1001, 0b0111,
        0b1010, 0b0100, 0b1111, 0b0000, 0b1101, 0b0010,
        0b1000, 0b0001, 0b1110, 0b0101, 0b1011, 0b0110,
    ]
    previous_bits = [0, 0, 0, 0]
    signals = []
    for value in values:
        bits = _bits4(value)
        context_bit = _parity(previous_bits)
        signals.append(
            SignalSpec(
                input_bits=bits,
                context_bit=context_bit,
                task_id=task_id,
            )
        )
        previous_bits = bits
    return tuple(signals)


def cvt1_stage4_signals(task_id: str = "task_a") -> Tuple[SignalSpec, ...]:
    """216-packet signal set: 12 passes with varied masks for ceiling mapping."""
    base_values = [
        0b0001, 0b0110, 0b1011, 0b0101, 0b1110, 0b0011,
        0b1100, 0b1001, 0b0111, 0b1010, 0b0100, 0b1111,
        0b0000, 0b1101, 0b0010, 0b1000, 0b0110, 0b1011,
    ]
    masks = [
        0b0000, 0b1111, 0b0101, 0b1010, 0b0011, 0b1100,
        0b1001, 0b0110, 0b1110, 0b0001, 0b0100, 0b1011,
    ]
    values = [value ^ masks[pass_idx] for pass_idx in range(len(masks)) for value in base_values]

    previous_bits = [0, 0, 0, 0]
    signals = []
    for value in values:
        bits = _bits4(value)
        context_bit = _parity(previous_bits)
        signals.append(
            SignalSpec(
                input_bits=bits,
                context_bit=context_bit,
                task_id=task_id,
            )
        )
        previous_bits = bits
    return tuple(signals)


@dataclass(frozen=True)
class ScenarioSpec:
    name: str
    description: str
    adjacency: Dict[str, tuple[str, ...]]
    positions: Dict[str, int]
    source_id: str
    sink_id: str
    cycles: int
    initial_packets: int
    packet_schedule: Dict[int, int]
    packet_ttl: int = 8
    source_admission_policy: str = "fixed"
    source_admission_rate: int | None = None
    source_admission_min_rate: int = 1
    source_admission_max_rate: int | None = None
    initial_signal_specs: Tuple[SignalSpec, ...] = ()
    signal_schedule_specs: Dict[int, Tuple[SignalSpec, ...]] | None = None


def phase8_scenarios() -> Dict[str, ScenarioSpec]:
    basic_adjacency, basic_positions, basic_source, basic_sink = basic_demo_topology()
    branch_adjacency, branch_positions, branch_source, branch_sink = branch_pressure_topology()
    sustained_adjacency, sustained_positions, sustained_source, sustained_sink = sustained_pressure_topology()
    detour_adjacency, detour_positions, detour_source, detour_sink = detour_resilience_topology()
    large_adjacency, large_positions, large_source, large_sink = cvt1_large_topology()
    scale_adjacency, scale_positions, scale_source, scale_sink = cvt1_scale_topology()
    ceiling_adjacency, ceiling_positions, ceiling_source, ceiling_sink = cvt1_ceiling_topology()

    cvt_a_signals = cvt1_task_a_stage1_signals()
    cvt_a_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_a_signals[1:], start=2)
    }
    cvt_b_signals = cvt1_task_b_stage1_signals()
    cvt_b_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_b_signals[1:], start=2)
    }
    cvt_c_signals = cvt1_task_c_stage1_signals()
    cvt_c_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_c_signals[1:], start=2)
    }

    cvt_a2_signals = cvt1_stage2_signals("task_a")
    cvt_a2_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_a2_signals[1:], start=2)
    }
    cvt_b2_signals = cvt1_stage2_signals("task_b")
    cvt_b2_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_b2_signals[1:], start=2)
    }
    cvt_c2_signals = cvt1_stage2_signals("task_c")
    cvt_c2_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_c2_signals[1:], start=2)
    }

    cvt_a3_signals = cvt1_stage3_signals("task_a")
    cvt_a3_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_a3_signals[1:], start=2)
    }
    cvt_b3_signals = cvt1_stage3_signals("task_b")
    cvt_b3_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_b3_signals[1:], start=2)
    }
    cvt_c3_signals = cvt1_stage3_signals("task_c")
    cvt_c3_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_c3_signals[1:], start=2)
    }

    cvt_a4_signals = cvt1_stage4_signals("task_a")
    cvt_a4_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_a4_signals[1:], start=2)
    }
    cvt_b4_signals = cvt1_stage4_signals("task_b")
    cvt_b4_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_b4_signals[1:], start=2)
    }
    cvt_c4_signals = cvt1_stage4_signals("task_c")
    cvt_c4_schedule = {
        cycle: (signal_spec,)
        for cycle, signal_spec in enumerate(cvt_c4_signals[1:], start=2)
    }

    return {
        "basic_demo": ScenarioSpec(
            name="basic_demo",
            description="Small four-hop bootstrap graph for quick smoke runs.",
            adjacency=basic_adjacency,
            positions=basic_positions,
            source_id=basic_source,
            sink_id=basic_sink,
            cycles=8,
            initial_packets=2,
            packet_schedule={4: 1},
            packet_ttl=8,
            source_admission_policy="adaptive",
            source_admission_rate=1,
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        ),
        "branch_pressure": ScenarioSpec(
            name="branch_pressure",
            description="Moderate branch competition with periodic bursts.",
            adjacency=branch_adjacency,
            positions=branch_positions,
            source_id=branch_source,
            sink_id=branch_sink,
            cycles=branch_pressure_workload()[0],
            initial_packets=branch_pressure_workload()[1],
            packet_schedule=branch_pressure_workload()[2],
            packet_ttl=8,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        ),
        "sustained_pressure": ScenarioSpec(
            name="sustained_pressure",
            description="Longer overload run that tests queueing, packet aging, and warm-start stability.",
            adjacency=sustained_adjacency,
            positions=sustained_positions,
            source_id=sustained_source,
            sink_id=sustained_sink,
            cycles=sustained_pressure_workload()[0],
            initial_packets=sustained_pressure_workload()[1],
            packet_schedule=sustained_pressure_workload()[2],
            packet_ttl=7,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        ),
        "detour_resilience": ScenarioSpec(
            name="detour_resilience",
            description="Longer path with branching detours to test persistent support beyond a single bottleneck.",
            adjacency=detour_adjacency,
            positions=detour_positions,
            source_id=detour_source,
            sink_id=detour_sink,
            cycles=detour_resilience_workload()[0],
            initial_packets=detour_resilience_workload()[1],
            packet_schedule=detour_resilience_workload()[2],
            packet_ttl=8,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
        ),
        "cvt1_task_a_stage1": ScenarioSpec(
            name="cvt1_task_a_stage1",
            description="First computational Stage 1 workload with explicit context bits and task-A target transforms.",
            adjacency=branch_adjacency,
            positions=branch_positions,
            source_id=branch_source,
            sink_id=branch_sink,
            cycles=len(cvt_a_signals) + 6,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=10,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_a_signals[0],),
            signal_schedule_specs=cvt_a_schedule,
        ),
        "cvt1_task_b_stage1": ScenarioSpec(
            name="cvt1_task_b_stage1",
            description="Related Stage 1 transfer workload where the odd-context branch switches to xor_mask_0101.",
            adjacency=branch_adjacency,
            positions=branch_positions,
            source_id=branch_source,
            sink_id=branch_sink,
            cycles=len(cvt_b_signals) + 6,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=10,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_b_signals[0],),
            signal_schedule_specs=cvt_b_schedule,
        ),
        "cvt1_task_c_stage1": ScenarioSpec(
            name="cvt1_task_c_stage1",
            description="Nearby Stage 1 variant where even-context uses xor_mask_1010 and odd-context uses xor_mask_0101.",
            adjacency=branch_adjacency,
            positions=branch_positions,
            source_id=branch_source,
            sink_id=branch_sink,
            cycles=len(cvt_c_signals) + 6,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=10,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_c_signals[0],),
            signal_schedule_specs=cvt_c_schedule,
        ),
        "cvt1_task_a_large": ScenarioSpec(
            name="cvt1_task_a_large",
            description="Task A on 10-node topology with 36 packets: 3-way source branching, 5-hop paths, extended signal set.",
            adjacency=large_adjacency,
            positions=large_positions,
            source_id=large_source,
            sink_id=large_sink,
            cycles=len(cvt_a2_signals) + 10,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=14,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_a2_signals[0],),
            signal_schedule_specs=cvt_a2_schedule,
        ),
        "cvt1_task_b_large": ScenarioSpec(
            name="cvt1_task_b_large",
            description="Task B on 10-node topology with 36 packets: ctx1 switches to xor_mask_0101.",
            adjacency=large_adjacency,
            positions=large_positions,
            source_id=large_source,
            sink_id=large_sink,
            cycles=len(cvt_b2_signals) + 10,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=14,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_b2_signals[0],),
            signal_schedule_specs=cvt_b2_schedule,
        ),
        "cvt1_task_c_large": ScenarioSpec(
            name="cvt1_task_c_large",
            description="Task C on 10-node topology with 36 packets: ctx0=xor_mask_1010, ctx1=xor_mask_0101.",
            adjacency=large_adjacency,
            positions=large_positions,
            source_id=large_source,
            sink_id=large_sink,
            cycles=len(cvt_c2_signals) + 10,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=14,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_c2_signals[0],),
            signal_schedule_specs=cvt_c2_schedule,
        ),
        "cvt1_task_a_scale": ScenarioSpec(
            name="cvt1_task_a_scale",
            description="Task A on 30-node topology with 108 packets: designed for matching scale with 30-hidden-unit networks.",
            adjacency=scale_adjacency,
            positions=scale_positions,
            source_id=scale_source,
            sink_id=scale_sink,
            cycles=len(cvt_a3_signals) + 20,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=20,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_a3_signals[0],),
            signal_schedule_specs=cvt_a3_schedule,
        ),
        "cvt1_task_b_scale": ScenarioSpec(
            name="cvt1_task_b_scale",
            description="Task B on 30-node topology with 108 packets.",
            adjacency=scale_adjacency,
            positions=scale_positions,
            source_id=scale_source,
            sink_id=scale_sink,
            cycles=len(cvt_b3_signals) + 20,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=20,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_b3_signals[0],),
            signal_schedule_specs=cvt_b3_schedule,
        ),
        "cvt1_task_c_scale": ScenarioSpec(
            name="cvt1_task_c_scale",
            description="Task C on 30-node topology with 108 packets.",
            adjacency=scale_adjacency,
            positions=scale_positions,
            source_id=scale_source,
            sink_id=scale_sink,
            cycles=len(cvt_c3_signals) + 20,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=20,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_c3_signals[0],),
            signal_schedule_specs=cvt_c3_schedule,
        ),
        "cvt1_task_a_ceiling": ScenarioSpec(
            name="cvt1_task_a_ceiling",
            description="Task A on 50-node topology with 216 packets for ceiling-mapping runs.",
            adjacency=ceiling_adjacency,
            positions=ceiling_positions,
            source_id=ceiling_source,
            sink_id=ceiling_sink,
            cycles=len(cvt_a4_signals) + 28,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=26,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_a4_signals[0],),
            signal_schedule_specs=cvt_a4_schedule,
        ),
        "cvt1_task_b_ceiling": ScenarioSpec(
            name="cvt1_task_b_ceiling",
            description="Task B on 50-node topology with 216 packets for ceiling-mapping runs.",
            adjacency=ceiling_adjacency,
            positions=ceiling_positions,
            source_id=ceiling_source,
            sink_id=ceiling_sink,
            cycles=len(cvt_b4_signals) + 28,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=26,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_b4_signals[0],),
            signal_schedule_specs=cvt_b4_schedule,
        ),
        "cvt1_task_c_ceiling": ScenarioSpec(
            name="cvt1_task_c_ceiling",
            description="Task C on 50-node topology with 216 packets for ceiling-mapping runs.",
            adjacency=ceiling_adjacency,
            positions=ceiling_positions,
            source_id=ceiling_source,
            sink_id=ceiling_sink,
            cycles=len(cvt_c4_signals) + 28,
            initial_packets=0,
            packet_schedule={},
            packet_ttl=26,
            source_admission_policy="adaptive",
            source_admission_min_rate=1,
            source_admission_max_rate=2,
            initial_signal_specs=(cvt_c4_signals[0],),
            signal_schedule_specs=cvt_c4_schedule,
        ),
    }
